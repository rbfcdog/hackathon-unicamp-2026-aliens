import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Analysis
from app.documents import DocumentRepository
from app.documents.repository import SUPPORTED_DOCUMENT_SUFFIXES
from app.graph import analysis_graph
from app.graph.nodes import AnalysisInputResolutionError
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, AnalysisResult, EvidenceInput
from app.schemas.documents import DocumentReference
from app.schemas.processes import LegalProcessCreate
from app.services.process_documents import process_document_service
from app.services.processes import legal_process_service

logger = logging.getLogger(__name__)


class AnalysisExecutionError(RuntimeError):
    pass


class AnalysisInputError(ValueError):
    pass


class AnalysisService:
    async def create(self, session: AsyncSession, request: AnalysisRequest) -> AnalysisResponse:
        settings = get_settings()
        repository = DocumentRepository(settings.document_root)
        try:
            process = (
                await legal_process_service.upsert_from_analysis(session, request)
                if request.state is not None and request.claim_amount is not None
                else await legal_process_service.get_by_case_number(session, request.case_number)
            )
            persisted_documents = await process_document_service.list(
                session,
                process.case_number if process is not None else request.case_number,
            )
            documents_by_path = {
                document.path: DocumentReference(
                    path=document.path,
                    document_type=document.document_type,
                )
                for document in persisted_documents.documents
            }
            documents_by_path.update({document.path: document for document in request.documents})
            context_values = {
                **request.model_dump(mode="python"),
                "documents": list(documents_by_path.values()),
            }
            if process is not None:
                process_claim_amount = float(process.claim_amount)
                context_values.update(
                    {
                        "state": request.state or (
                            process.state if process.state.strip().upper() != "NA" else None
                        ),
                        "sub_subject": request.sub_subject or process.sub_subject,
                        "claim_amount": (
                            request.claim_amount
                            if request.claim_amount is not None
                            else (
                                process_claim_amount
                                if process_claim_amount > 0.01
                                else None
                            )
                        ),
                        "evidence": request.evidence or EvidenceInput.model_validate(
                            process.evidence
                        ),
                    }
                )
            context_request = AnalysisRequest.model_validate(context_values)
            normalized_documents = [
                document.model_copy(
                    update={
                        "path": repository.resolve(
                            document.path,
                            expected_suffixes=set(SUPPORTED_DOCUMENT_SUFFIXES),
                        )[1]
                    }
                )
                for document in context_request.documents
            ]
        except ValueError as exc:
            raise AnalysisInputError(str(exc)) from exc
        normalized_request = context_request.model_copy(update={"documents": normalized_documents})
        request_payload = normalized_request.model_dump(mode="json")
        analysis = Analysis(
            case_number=normalized_request.case_number,
            status="processing",
            request_payload=request_payload,
        )
        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)

        try:
            graph_result = await analysis_graph.ainvoke(
                {"request": request_payload},
                config={
                    "run_id": analysis.id,
                    "run_name": "settlement-analysis",
                    "tags": ["analysis", settings.environment],
                    "metadata": {
                        "case_reference": hashlib.sha256(
                            normalized_request.case_number.encode()
                        ).hexdigest()[:16],
                        "document_count": len(normalized_documents),
                        "model": settings.openai_model,
                    },
                },
            )
            result = AnalysisResult.model_validate(graph_result)
            analysis.status = "completed"
            analysis.result_payload = result.model_dump(mode="json")
            if (
                result.model_inputs is not None
                and result.model_inputs.claim_amount is not None
            ):
                await legal_process_service.upsert(
                    session,
                    LegalProcessCreate(
                        case_number=normalized_request.case_number,
                        state=result.model_inputs.state,
                        sub_subject=result.model_inputs.sub_subject,
                        claim_amount=result.model_inputs.claim_amount,
                        evidence=result.model_inputs.evidence,
                    ),
                )
        except AnalysisInputResolutionError as exc:
            message = str(exc)
            analysis.status = "failed"
            analysis.error_message = message
            await session.commit()
            raise AnalysisInputError(message) from exc
        except Exception as exc:
            message = "LLM analysis failed"
            logger.exception(
                "Analysis execution failed for case %s",
                normalized_request.case_number,
            )
            analysis.status = "failed"
            analysis.error_message = message
            await session.commit()
            raise AnalysisExecutionError(message) from exc

        await session.commit()
        await session.refresh(analysis)
        return self.to_response(analysis)

    async def refresh_for_process(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> AnalysisResponse:
        documents = await process_document_service.list(session, case_number)
        process = await legal_process_service.get_by_case_number(
            session,
            documents.case_number,
        )
        document_references = [
            DocumentReference(
                path=document.path,
                document_type=document.document_type,
            )
            for document in documents.documents
        ]
        request_values: dict[str, object] = {
            "case_number": documents.case_number,
            "documents": document_references,
        }
        if not document_references:
            if process is None:
                raise AnalysisInputError(
                    "Cannot refresh analysis without a process or attached documents"
                )
            request_values.update(
                {
                    "state": process.state,
                    "sub_subject": process.sub_subject,
                    "claim_amount": float(process.claim_amount),
                    "evidence": EvidenceInput.model_validate(process.evidence),
                }
            )
        return await self.create(
            session,
            AnalysisRequest.model_validate(request_values),
        )

    async def get(self, session: AsyncSession, analysis_id: uuid.UUID) -> AnalysisResponse | None:
        result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        return self.to_response(analysis) if analysis else None

    async def latest_for_case(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> AnalysisResponse | None:
        result = await session.execute(
            select(Analysis)
            .where(Analysis.case_number == case_number)
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(1)
        )
        analysis = result.scalar_one_or_none()
        return self.to_response(analysis) if analysis else None

    @staticmethod
    def to_response(analysis: Analysis) -> AnalysisResponse:
        return AnalysisResponse(
            id=analysis.id,
            case_number=analysis.case_number,
            status=analysis.status,
            request=AnalysisRequest.model_validate(analysis.request_payload),
            result=(
                AnalysisResult.model_validate(analysis.result_payload)
                if analysis.result_payload
                else None
            ),
            error_message=analysis.error_message,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
        )


analysis_service = AnalysisService()
