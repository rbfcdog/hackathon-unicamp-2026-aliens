import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from app.config import Settings
from app.documents import DOCUMENT_TOOLS, DocumentRepository, ProcessDataRepository
from app.domain import SettlementPolicy
from app.graph.judge import JUDGE_TOOLS, JudgeState
from app.graph.nodes import estimate_risk
from app.main import app
from app.ml.tools import (
    estimate_case_risk,
    estimate_case_risk_payload,
    inspect_risk_model_card,
)
from app.schemas.analysis import AnalysisRequest, EvidenceInput, ResolvedAnalysisInput
from app.schemas.judge import JudgeReviewRequest, ProcessDataRecord, ProcessDataReference
from app.services.judge import JudgeService

CASE_ONE_PATHS = (
    "cases/Caso_01_0801234-56-2024-8-10-0001/01_Autos_Processo_0801234-56-2024-8-10-0001.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/02_Contrato_502348719.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/03_Extrato_Bancario.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/04_Comprovante_de_Credito_BACEN.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/05_Dossie_Veritas.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/06_Demonstrativo_Evolucao_Divida.pdf",
    "cases/Caso_01_0801234-56-2024-8-10-0001/07_Laudo_Referenciado.pdf",
)
PDF_PATH = CASE_ONE_PATHS[0]
WORKBOOK_PATH = "datasets/Hackaton_Enter_Base_Candidatos.xlsx"
PROCESS_NUMBER = "1764352-89.2025.8.06.1818"


def test_openai_key_is_required() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        Settings(_env_file=None, openai_api_key="")


def test_repository_reads_supplied_pdf_and_workbook_and_blocks_escape() -> None:
    repository = DocumentRepository("../data")

    pdf = repository.read_pdf(PDF_PATH)
    workbook = repository.read_spreadsheet(WORKBOOK_PATH, max_rows=3)

    assert pdf["status"] == "ok"
    assert pdf["total_pages"] == 8
    assert "--- página 1 ---" in pdf["content"]
    assert pdf["end_page"] == 8
    assert pdf["truncated"] is False
    assert pdf["extraction_engine"] == "pymupdf4llm"
    assert pdf["ocr_mode"] == "select_keep_old"
    assert workbook["status"] == "ok"
    assert workbook["sheet_name"] == "Resultados dos processos"
    assert workbook["total_rows"] == 60_001
    assert "[linha 1]" in workbook["content"]

    with pytest.raises(ValueError, match="escapes"):
        repository.resolve("../backend/pyproject.toml", expected_suffixes={".toml"})


def test_tool_schemas_do_not_expose_runtime_state() -> None:
    for document_tool in DOCUMENT_TOOLS:
        assert "runtime" not in document_tool.args
        assert "start_page" not in document_tool.args
        assert "max_pages" not in document_tool.args
        assert "start_row" not in document_tool.args
        assert "max_rows" not in document_tool.args


def test_ml_tools_return_versioned_prediction_and_model_card() -> None:
    prediction = json.loads(
        estimate_case_risk.invoke(
            {
                "uf": "MG",
                "sub_subject": "generic",
                "claim_amount": 10_000,
                "contract": True,
                "bank_statement": True,
                "credit_proof": True,
                "dossier": True,
                "debt_evolution": True,
                "referenced_report": True,
            }
        )
    )
    model_card = json.loads(inspect_risk_model_card.invoke({}))

    assert prediction["status"] == "ok"
    assert prediction["estimate"]["loss_probability"] < 0.1
    assert (
        prediction["estimate"]["condemnation_q10"]
        <= prediction["estimate"]["condemnation_q50"]
        <= prediction["estimate"]["condemnation_q90"]
    )
    assert prediction["estimate"]["model_version"] == "judicial-risk-v5"
    components = prediction["estimate"]["component_probabilities"]
    expected_blend = 0.7 * components["logistic_regression"] + 0.3 * components["xgboost"]
    assert prediction["estimate"]["loss_probability"] == pytest.approx(
        expected_blend,
        abs=1e-6,
    )
    assert "claim_amount" in estimate_case_risk.args
    assert prediction["inputs"]["claim_amount_usage"] == "severity_only"
    policy = model_card["feature_policy"]
    assert "Valor da causa" not in policy["classification_input_features"]
    assert "Valor da causa" in policy["severity_input_features"]
    assert "Valor da condenação/indenização" not in policy["severity_input_features"]
    assert model_card["status"] == "ok"
    assert model_card["selection"]["champion"] == "logistic_xgboost_ensemble"
    assert model_card["selection"]["ensemble_weights"] == {
        "logistic_regression": 0.7,
        "xgboost": 0.3,
    }
    assert model_card["held_out_classification"]["roc_auc"] > 0.9
    assert "inspect_risk_model_card" in {tool.name for tool in JUDGE_TOOLS}
    assert "estimate_case_risk" not in {tool.name for tool in JUDGE_TOOLS}


def test_claim_amount_affects_only_severity_prediction() -> None:
    evidence = EvidenceInput(
        contract=True,
        bank_statement=True,
        credit_proof=True,
        dossier=True,
        debt_evolution=True,
        referenced_report=True,
    )
    base = {
        "case_number": "LEAKAGE-REGRESSION",
        "state": "MG",
        "sub_subject": "generic",
        "evidence": evidence,
    }
    low_amount = AnalysisRequest(**base, claim_amount=1)
    high_amount = AnalysisRequest(**base, claim_amount=1_000_000_000)

    low_estimate = estimate_risk(
        {
            "model_inputs": ResolvedAnalysisInput(
                state=low_amount.state,
                sub_subject=low_amount.sub_subject,
                claim_amount=low_amount.claim_amount,
                evidence=low_amount.evidence,
                input_source="request_fields",
            ).model_dump(mode="json")
        }
    )
    high_estimate = estimate_risk(
        {
            "model_inputs": ResolvedAnalysisInput(
                state=high_amount.state,
                sub_subject=high_amount.sub_subject,
                claim_amount=high_amount.claim_amount,
                evidence=high_amount.evidence,
                input_source="request_fields",
            ).model_dump(mode="json")
        }
    )

    for field in (
        "loss_probability",
        "model_disagreement",
        "requires_model_review",
        "model_version",
    ):
        assert low_estimate[field] == high_estimate[field]
    assert low_estimate["expected_condemnation"] != high_estimate["expected_condemnation"]


def test_decision_tree_thresholds_and_economic_comparison() -> None:
    request = AnalysisRequest(
        case_number="POLICY-BOUNDARIES",
        state="MA",
        sub_subject="generic",
        claim_amount=20_000,
        evidence=EvidenceInput(),
    )
    policy = SettlementPolicy()

    low = policy.evaluate(request, loss_probability=0.3999, expected_condemnation=10_000)
    medium_floor = policy.evaluate(request, loss_probability=0.40, expected_condemnation=10_000)
    medium_ceiling = policy.evaluate(request, loss_probability=0.60, expected_condemnation=10_000)
    high_defense = policy.evaluate(request, loss_probability=0.80, expected_condemnation=1_000)
    high_agreement = policy.evaluate(request, loss_probability=0.80, expected_condemnation=20_000)

    assert (low.risk_band, low.recommendation) == ("low", "defense")
    assert medium_floor.recommendation == medium_ceiling.recommendation == "human_review"
    assert medium_floor.human_review_reason
    assert (high_defense.risk_band, high_defense.recommendation) == ("high", "defense")
    assert high_defense.agreement_cheaper is False
    assert high_agreement.recommendation == "agreement"
    assert high_agreement.agreement_cheaper is True
    assert high_agreement.next_action == "propose_agreement"


def test_document_tool_rejects_file_not_supplied_to_review() -> None:
    repository = DocumentRepository("../data")
    unauthorized_path = (
        "cases/Caso_02_0654321-09-2024-8-04-0001/01_Autos_Processo_0654321-09-2024-8-04-0001.pdf"
    )
    builder = StateGraph(JudgeState)
    builder.add_node("tools", ToolNode(DOCUMENT_TOOLS))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    result = builder.compile().invoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_pdf_document",
                            "args": {"document_path": unauthorized_path},
                            "id": "unauthorized-read",
                        }
                    ],
                )
            ],
            "document_root": str(repository.root),
            "allowed_document_paths": [PDF_PATH],
        }
    )
    payload = json.loads(result["messages"][-1].content)

    assert payload["status"] == "error"
    assert "not supplied" in payload["error"]


@pytest.mark.asyncio
async def test_judge_reference_endpoints_list_documents_and_process_data() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        catalog_response = await client.get("/v1/documents")
        process_response = await client.get(f"/v1/process-data/{PROCESS_NUMBER}")

    assert catalog_response.status_code == 200
    paths = {document["path"] for document in catalog_response.json()["documents"]}
    assert PDF_PATH in paths
    assert WORKBOOK_PATH in paths
    assert process_response.status_code == 200
    assert process_response.json()["process_number"] == PROCESS_NUMBER
    assert process_response.json()["state"] == "CE"
    assert process_response.json()["claim_amount"] == 13_534
    assert process_response.json()["source_rows"] == {
        "Resultados dos processos": 2,
        "Subsídios disponibilizados": 3,
    }


@pytest.mark.asyncio
async def test_uploaded_pdf_and_csv_are_stored_and_invalid_pdf_is_rejected() -> None:
    source_bytes = (Path("../data") / PDF_PATH).read_bytes()
    csv_bytes = (
        b"case_number,state,sub_subject,claim_amount,contract\nCSV-CASE-1,MG,fraud,12500,true\n"
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pdf_response = await client.post(
            "/v1/documents/uploads",
            data={"document_type": "case_record"},
            files={"file": ("petition.pdf", source_bytes, "application/pdf")},
        )
        csv_response = await client.post(
            "/v1/documents/uploads",
            data={"document_type": "other"},
            files={"file": ("case.csv", csv_bytes, "text/csv")},
        )
        invalid_response = await client.post(
            "/v1/documents/uploads",
            data={"document_type": "case_record"},
            files={"file": ("invalid.pdf", b"not a pdf", "application/pdf")},
        )

    pdf_path = pdf_response.json()["path"]
    csv_path = csv_response.json()["path"]
    assert pdf_response.status_code == 201
    assert pdf_response.json()["kind"] == "pdf"
    assert pdf_response.json()["document_type"] == "case_record"
    assert pdf_response.json()["size_bytes"] == len(source_bytes)
    assert pdf_path.startswith("uploads/")
    assert csv_response.status_code == 201
    assert csv_response.json()["kind"] == "csv"
    assert csv_response.json()["document_type"] == "other"
    csv_payload = DocumentRepository("../data").read_csv(csv_path)
    assert csv_payload["status"] == "ok"
    assert csv_payload["total_rows"] == 2
    assert "[linha 2] CSV-CASE-1" in csv_payload["content"]
    assert invalid_response.status_code == 422

    for uploaded_path in (pdf_path, csv_path):
        uploaded_file = Path("../data") / uploaded_path
        uploaded_file.unlink()
        uploaded_file.parent.rmdir()


def test_workbook_and_submitted_documents_produce_identical_ensemble_inputs() -> None:
    process_data = ProcessDataRecord.model_validate(
        ProcessDataRepository(DocumentRepository("../data")).find(
            WORKBOOK_PATH,
            PROCESS_NUMBER,
        )
    )
    workbook_request = JudgeReviewRequest(
        case_number=PROCESS_NUMBER,
        documents=[{"path": PDF_PATH, "document_type": "case_record"}],
        process_data_reference=ProcessDataReference(
            workbook_path=WORKBOOK_PATH,
            process_number=PROCESS_NUMBER,
        ),
    )
    document_request = JudgeReviewRequest(
        case_number="NEW-CASE-1",
        documents=[
            {"path": CASE_ONE_PATHS[4], "document_type": "dossier"},
            {"path": CASE_ONE_PATHS[5], "document_type": "debt_evolution"},
            {"path": CASE_ONE_PATHS[6], "document_type": "referenced_report"},
        ],
        new_case_data={
            "state": process_data.state,
            "sub_subject": process_data.sub_subject,
            "claim_amount": process_data.claim_amount,
        },
    )

    workbook_inputs = JudgeService._resolve_model_inputs(
        workbook_request,
        process_data,
    )
    document_inputs = JudgeService._resolve_model_inputs(
        document_request,
        None,
    )
    assert workbook_inputs.evidence == document_inputs.evidence
    assert workbook_inputs.input_source == "workbook_row"
    assert document_inputs.input_source == "submitted_documents"

    merged_request = JudgeReviewRequest(
        case_number=PROCESS_NUMBER,
        documents=[{"path": CASE_ONE_PATHS[1], "document_type": "contract"}],
        process_data_reference=ProcessDataReference(
            workbook_path=WORKBOOK_PATH,
            process_number=PROCESS_NUMBER,
        ),
    )
    merged_inputs = JudgeService._resolve_model_inputs(
        merged_request,
        process_data,
    )
    assert merged_inputs.input_source == "workbook_row_and_submitted_documents"
    assert merged_inputs.evidence.contract is True
    assert merged_inputs.evidence.dossier is True

    workbook_prediction = estimate_case_risk_payload(
        uf=workbook_inputs.uf,
        sub_subject=workbook_inputs.sub_subject,
        claim_amount=workbook_inputs.claim_amount,
        evidence=workbook_inputs.evidence,
        input_source=workbook_inputs.input_source,
    )
    document_prediction = estimate_case_risk_payload(
        uf=document_inputs.uf,
        sub_subject=document_inputs.sub_subject,
        claim_amount=document_inputs.claim_amount,
        evidence=document_inputs.evidence,
        input_source=document_inputs.input_source,
        evidence_document_paths=document_inputs.evidence_document_paths,
    )

    assert workbook_prediction["estimate"] == document_prediction["estimate"]
    assert set(document_prediction["estimate"]["component_probabilities"]) == {
        "logistic_regression",
        "xgboost",
    }
