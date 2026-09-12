import hashlib
import logging
import uuid
from functools import lru_cache
from typing import BinaryIO

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.documents import DocumentRepository, ProcessDataRepository
from app.documents.repository import SUPPORTED_DOCUMENT_SUFFIXES
from app.graph.judge import JUDGE_TOOLS, build_judge_graph, build_judge_prompt
from app.schemas.analysis import EvidenceInput
from app.schemas.documents import EvidenceDocumentType, UploadedDocumentResponse
from app.schemas.judge import (
    DocumentCatalogItem,
    DocumentCatalogResponse,
    JudgeDecision,
    JudgeMLInputs,
    JudgeReviewRequest,
    JudgeReviewResponse,
    ProcessDataRecord,
    ProcessDataReference,
)

logger = logging.getLogger(__name__)


class JudgeExecutionError(RuntimeError):
    pass


class JudgeOutputError(RuntimeError):
    pass


@lru_cache
def get_compiled_judge_graph():
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    agent_model = model.bind_tools(JUDGE_TOOLS, parallel_tool_calls=True)
    decision_model = model.with_structured_output(JudgeDecision, method="json_schema")
    return build_judge_graph(agent_model, decision_model)


class JudgeService:
    def catalog(self) -> DocumentCatalogResponse:
        settings = get_settings()
        repository = DocumentRepository(settings.document_root)
        return DocumentCatalogResponse(
            document_root=settings.document_root,
            documents=[
                DocumentCatalogItem.model_validate(document.as_dict())
                for document in repository.list_documents()
            ],
        )

    def upload_document(
        self,
        filename: str,
        source: BinaryIO,
        document_type: EvidenceDocumentType,
    ) -> UploadedDocumentResponse:
        settings = get_settings()
        repository = DocumentRepository(settings.document_root)
        stored = repository.store_upload(filename, source)
        return UploadedDocumentResponse.model_validate({**stored, "document_type": document_type})

    def process_data(self, reference: ProcessDataReference) -> ProcessDataRecord:
        settings = get_settings()
        repository = DocumentRepository(settings.document_root)
        record = ProcessDataRepository(repository).find(
            reference.workbook_path,
            reference.process_number,
        )
        return ProcessDataRecord.model_validate(record)

    @staticmethod
    def _resolve_model_inputs(
        request: JudgeReviewRequest,
        process_data: ProcessDataRecord | None,
    ) -> JudgeMLInputs:
        evidence_fields = (
            "contract",
            "bank_statement",
            "credit_proof",
            "dossier",
            "debt_evolution",
            "referenced_report",
        )
        evidence_document_paths = {
            field: [
                document.path for document in request.documents if document.document_type == field
            ]
            for field in evidence_fields
        }
        submitted_evidence = EvidenceInput(
            **{field: bool(evidence_document_paths[field]) for field in evidence_fields}
        )
        if process_data:
            evidence = EvidenceInput(
                **{
                    field: getattr(process_data.evidence, field)
                    or getattr(submitted_evidence, field)
                    for field in evidence_fields
                }
            )
            has_submitted_evidence = any(
                getattr(submitted_evidence, field) for field in evidence_fields
            )
            input_source = (
                "workbook_row_and_submitted_documents" if has_submitted_evidence else "workbook_row"
            )
            state = process_data.state
            sub_subject = process_data.sub_subject
            claim_amount = process_data.claim_amount
        else:
            if request.new_case_data is None:
                raise ValueError("new_case_data is required when no workbook row is referenced")
            evidence = submitted_evidence
            input_source = "submitted_documents"
            state = request.new_case_data.state
            sub_subject = request.new_case_data.sub_subject
            claim_amount = request.new_case_data.claim_amount
        return JudgeMLInputs(
            uf=state,
            sub_subject=sub_subject,
            claim_amount=claim_amount,
            claim_amount_usage="severity_only",
            input_source=input_source,
            evidence_document_paths=evidence_document_paths,
            evidence=evidence,
        )

    async def review(self, request: JudgeReviewRequest) -> JudgeReviewResponse:
        settings = get_settings()

        repository = DocumentRepository(settings.document_root)
        normalized_documents = []
        for document in request.documents:
            _, normalized = repository.resolve(
                document.path,
                expected_suffixes=set(SUPPORTED_DOCUMENT_SUFFIXES),
            )
            normalized_documents.append(document.model_copy(update={"path": normalized}))
        normalized_request = request.model_copy(update={"documents": normalized_documents})
        normalized_paths = [document.path for document in normalized_documents]
        process_data = (
            self.process_data(normalized_request.process_data_reference)
            if normalized_request.process_data_reference
            else None
        )
        process_payload = process_data.model_dump(mode="json") if process_data else None
        model_inputs = self._resolve_model_inputs(normalized_request, process_data)

        trace_id = uuid.uuid4()
        case_reference = hashlib.sha256(request.case_number.encode()).hexdigest()[:16]
        try:
            result = await get_compiled_judge_graph().ainvoke(
                {
                    "request": normalized_request.model_dump(mode="json"),
                    "document_root": str(repository.root),
                    "allowed_document_paths": normalized_paths,
                    "agent_turns": 0,
                    "process_data": process_payload,
                    "document_types": {
                        document.path: document.document_type for document in normalized_documents
                    },
                    "model_inputs": model_inputs.model_dump(mode="json"),
                    "messages": [build_judge_prompt(normalized_request, process_payload)],
                },
                config={
                    "run_id": trace_id,
                    "run_name": "judge-document-review",
                    "tags": ["judge-review", settings.environment],
                    "metadata": {
                        "case_reference": case_reference,
                        "document_count": len(normalized_paths),
                        "model": settings.openai_model,
                        "has_process_data": process_data is not None,
                    },
                    "recursion_limit": 100,
                },
            )
        except Exception as exc:
            logger.exception("Judge document review failed", extra={"trace_id": str(trace_id)})
            raise JudgeExecutionError("Judge document review failed") from exc

        decision = JudgeDecision.model_validate(result["decision"])
        consulted = result["consulted_documents"]
        unreadable = result["unreadable_documents"]
        consulted_set = set(consulted)
        invalid_citations = {
            citation.document_path
            for finding in decision.findings
            for citation in finding.citations
            if citation.document_path not in consulted_set
        }
        if invalid_citations:
            invalid = ", ".join(sorted(invalid_citations))
            raise JudgeOutputError(
                f"Model cited documents that were not successfully read: {invalid}"
            )

        return JudgeReviewResponse(
            **decision.model_dump(mode="python"),
            case_number=request.case_number,
            consulted_documents=consulted,
            unreadable_documents=unreadable,
            model=settings.openai_model,
            trace_id=trace_id,
            langsmith_project=settings.langsmith_project,
            tracing_enabled=settings.langsmith_enabled,
            ml_analysis=result["ml_analysis"],
            ml_tool_errors=result["ml_tool_errors"],
            model_card_consulted=result["model_card_consulted"],
            strategy=result["strategy"],
            document_node_reads=result["document_node_reads"],
            process_data=process_data,
        )


judge_service = JudgeService()
