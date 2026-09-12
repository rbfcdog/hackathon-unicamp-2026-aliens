import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LegalProcess
from app.documents import canonical_process_number
from app.schemas.analysis import AnalysisRequest, EvidenceInput
from app.schemas.processes import LegalProcessCreate, LegalProcessResponse

DEFAULT_QUESTION = (
    "Analise a existência da contratação, do crédito e da dívida e apresente uma decisão "
    "fundamentada."
)


class LegalProcessService:
    async def list(self, session: AsyncSession) -> list[LegalProcessResponse]:
        result = await session.execute(
            select(LegalProcess).order_by(
                LegalProcess.updated_at.desc(), LegalProcess.created_at.desc()
            )
        )
        return [LegalProcessResponse.model_validate(process) for process in result.scalars()]

    async def get_by_case_number(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> LegalProcess | None:
        canonical_number = canonical_process_number(case_number)
        result = await session.execute(
            select(LegalProcess).where(LegalProcess.canonical_number == canonical_number)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        payload: LegalProcessCreate,
    ) -> LegalProcess:
        process = await self.get_by_case_number(session, payload.case_number)
        values = {
            "case_number": payload.case_number,
            "canonical_number": canonical_process_number(payload.case_number),
            "state": payload.state,
            "sub_subject": payload.sub_subject,
            "claim_amount": payload.claim_amount,
            "evidence": payload.evidence.model_dump(mode="json"),
        }
        if process is None:
            process = LegalProcess(
                **values,
                title=payload.title or payload.subject or payload.case_number,
                location=payload.location or payload.state,
                subject=payload.subject or "Processo jurídico",
                default_question=payload.default_question or DEFAULT_QUESTION,
            )
            session.add(process)
        else:
            for field, value in values.items():
                setattr(process, field, value)
            if payload.title:
                process.title = payload.title
            if payload.location:
                process.location = payload.location
            if payload.subject:
                process.subject = payload.subject
            if payload.default_question:
                process.default_question = payload.default_question

        await session.commit()
        await session.refresh(process)
        return process

    async def create_draft(self, session: AsyncSession) -> LegalProcess:
        draft_number = f"RASCUNHO-{uuid.uuid4().int % 10**20:020d}"
        process = LegalProcess(
            case_number=draft_number,
            canonical_number=canonical_process_number(draft_number),
            title="Novo processo",
            location="Sem informações",
            state="NA",
            subject="Sem informações",
            sub_subject="generic",
            claim_amount=0.01,
            evidence=EvidenceInput().model_dump(mode="json"),
            default_question="O que você precisa para analisar este processo?",
        )
        session.add(process)
        await session.commit()
        await session.refresh(process)
        return process

    async def upsert_from_analysis(
        self,
        session: AsyncSession,
        request: AnalysisRequest,
    ) -> LegalProcess:
        if request.state is None or request.claim_amount is None:
            existing = await self.get_by_case_number(session, request.case_number)
            if existing is None:
                raise ValueError("Persist the process before analyzing document-only input")
            return existing
        return await self.upsert(
            session,
            LegalProcessCreate(
                case_number=request.case_number,
                state=request.state,
                sub_subject=request.sub_subject or "generic",
                claim_amount=request.claim_amount,
                evidence=request.evidence or EvidenceInput(),
            ),
        )


legal_process_service = LegalProcessService()
