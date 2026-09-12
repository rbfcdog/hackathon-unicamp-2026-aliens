import asyncio
import unicodedata
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ProcessDocument
from app.documents import DocumentRepository, canonical_process_number
from app.schemas.chat import ProcessDocumentListResponse, ProcessDocumentResponse
from app.schemas.documents import EvidenceDocumentType


class ProcessDocumentService:
    @staticmethod
    def _validate_case_number(case_number: str) -> str:
        normalized = case_number.strip()
        if not normalized or len(normalized) > 64:
            raise ValueError("case_number must contain between 1 and 64 characters")
        canonical_process_number(normalized)
        return normalized

    @staticmethod
    def _document_type(path: str) -> EvidenceDocumentType:
        name = Path(path).name.casefold()
        name = "".join(
            character
            for character in unicodedata.normalize("NFKD", name)
            if not unicodedata.combining(character)
        )
        if "autos" in name or "peticao" in name:
            return "case_record"
        if "contrato" in name:
            return "contract"
        if "extrato" in name:
            return "bank_statement"
        if "comprovante" in name or "bacen" in name:
            return "credit_proof"
        if "dossie" in name:
            return "dossier"
        if "evolucao" in name or "divida" in name:
            return "debt_evolution"
        if "laudo" in name or "referenciado" in name:
            return "referenced_report"
        return "other"

    @staticmethod
    def _uploaded_response(document: ProcessDocument) -> ProcessDocumentResponse:
        return ProcessDocumentResponse(
            id=document.id,
            case_number=document.case_number,
            path=document.path,
            original_filename=document.original_filename,
            document_type=document.document_type,
            kind=document.kind,
            source="upload",
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            created_at=document.created_at,
        )

    async def list(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> ProcessDocumentListResponse:
        normalized_case = self._validate_case_number(case_number)
        result = await session.execute(
            select(ProcessDocument)
            .where(ProcessDocument.case_number == normalized_case)
            .order_by(ProcessDocument.created_at, ProcessDocument.id)
        )
        uploaded = [self._uploaded_response(document) for document in result.scalars()]

        repository = DocumentRepository(get_settings().document_root)
        canonical_case = canonical_process_number(normalized_case)
        bundled = []
        uploaded_paths = {document.path for document in uploaded}
        for document in repository.list_documents():
            if document.kind not in {"pdf", "csv"} or not document.path.startswith("cases/"):
                continue
            if document.path in uploaded_paths:
                continue
            if canonical_case not in canonical_process_number(document.path):
                continue
            bundled.append(
                ProcessDocumentResponse(
                    id=None,
                    case_number=normalized_case,
                    path=document.path,
                    original_filename=Path(document.path).name,
                    document_type=self._document_type(document.path),
                    kind=document.kind,
                    source="bundled",
                    size_bytes=document.size_bytes,
                    sha256=None,
                    created_at=None,
                )
            )
        return ProcessDocumentListResponse(
            case_number=normalized_case,
            documents=[*bundled, *uploaded],
        )
    async def resolve_content(
        self,
        session: AsyncSession,
        case_number: str,
        document_path: str,
    ) -> tuple[Path, str]:
        documents = await self.list(session, case_number)
        authorized = next(
            (document for document in documents.documents if document.path == document_path),
            None,
        )
        if authorized is None:
            raise LookupError("document not found for this process")

        path, _ = DocumentRepository(get_settings().document_root).resolve(
            document_path,
            expected_suffixes={".pdf", ".csv"},
        )
        media_type = "application/pdf" if authorized.kind == "pdf" else "text/csv"
        return path, media_type


    async def upload(
        self,
        session: AsyncSession,
        case_number: str,
        filename: str,
        source: BinaryIO,
        document_type: EvidenceDocumentType,
    ) -> ProcessDocumentResponse:
        normalized_case = self._validate_case_number(case_number)
        repository = DocumentRepository(get_settings().document_root)
        count_result = await session.execute(
            select(func.count())
            .select_from(ProcessDocument)
            .where(ProcessDocument.case_number == normalized_case)
        )
        if count_result.scalar_one() >= 50:
            raise ValueError("A process can contain at most 50 uploaded documents")
        stored = await asyncio.to_thread(repository.store_upload, filename, source)
        try:
            existing_result = await session.execute(
                select(ProcessDocument).where(
                    ProcessDocument.case_number == normalized_case,
                    ProcessDocument.sha256 == stored["sha256"],
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                await asyncio.to_thread(repository.delete_upload, str(stored["path"]))
                return self._uploaded_response(existing)

            document = ProcessDocument(
                case_number=normalized_case,
                path=stored["path"],
                original_filename=filename.strip(),
                document_type=document_type,
                kind=stored["kind"],
                size_bytes=stored["size_bytes"],
                sha256=stored["sha256"],
            )
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return self._uploaded_response(document)
        except Exception:
            await session.rollback()
            path = str(stored["path"])
            try:
                await asyncio.to_thread(repository.delete_upload, path)
            except (OSError, ValueError):
                pass
            raise

    async def delete(
        self,
        session: AsyncSession,
        case_number: str,
        document_id: uuid.UUID,
    ) -> bool:
        normalized_case = self._validate_case_number(case_number)
        result = await session.execute(
            select(ProcessDocument).where(
                ProcessDocument.id == document_id,
                ProcessDocument.case_number == normalized_case,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            return False
        await asyncio.to_thread(
            DocumentRepository(get_settings().document_root).delete_upload,
            document.path,
        )
        await session.delete(document)
        await session.commit()
        return True


process_document_service = ProcessDocumentService()
