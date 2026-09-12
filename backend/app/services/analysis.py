import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Analysis
from app.documents import DocumentRepository
from app.documents.repository import SUPPORTED_DOCUMENT_SUFFIXES
from app.graph import analysis_graph
from app.graph.nodes import AnalysisInputResolutionError
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, AnalysisResult


class AnalysisExecutionError(RuntimeError):
    pass


class AnalysisInputError(ValueError):
    pass


class AnalysisService:
    async def create(self, session: AsyncSession, request: AnalysisRequest) -> AnalysisResponse:
        settings = get_settings()
        repository = DocumentRepository(settings.document_root)
        try:
            normalized_documents = [
                document.model_copy(
                    update={
                        "path": repository.resolve(
                            document.path,
                            expected_suffixes=set(SUPPORTED_DOCUMENT_SUFFIXES),
                        )[1]
                    }
                )
                for document in request.documents
            ]
        except ValueError as exc:
            raise AnalysisInputError(str(exc)) from exc
        normalized_request = request.model_copy(update={"documents": normalized_documents})
        request_payload = normalized_request.model_dump(mode="json")
        analysis = Analysis(
            case_number=request.case_number,
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
                            request.case_number.encode()
                        ).hexdigest()[:16],
                        "document_count": len(normalized_documents),
                        "model": settings.openai_model,
                    },
                },
            )
            result = AnalysisResult.model_validate(graph_result)
            analysis.status = "completed"
            analysis.result_payload = result.model_dump(mode="json")
        except AnalysisInputResolutionError as exc:
            message = str(exc)
            analysis.status = "failed"
            analysis.error_message = message
            await session.commit()
            raise AnalysisInputError(message) from exc
        except Exception as exc:
            message = "LLM analysis failed"
            analysis.status = "failed"
            analysis.error_message = message
            await session.commit()
            raise AnalysisExecutionError(message) from exc

        await session.commit()
        await session.refresh(analysis)
        return self.to_response(analysis)

    async def get(self, session: AsyncSession, analysis_id: uuid.UUID) -> AnalysisResponse | None:
        result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
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
