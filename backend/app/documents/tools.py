import json
from collections.abc import Callable
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from app.documents.repository import DocumentRepository


def _execute_document_read(
    document_path: str,
    runtime: ToolRuntime,
    expected_suffixes: set[str],
    operation: Callable[[DocumentRepository, str], dict[str, Any]],
) -> str:
    try:
        state = runtime.state
        repository = DocumentRepository(state["document_root"])
        _, normalized = repository.resolve(
            document_path,
            expected_suffixes=expected_suffixes,
        )
        allowed_paths = set(state["allowed_document_paths"])
        if normalized not in allowed_paths:
            raise ValueError("Document was not supplied for this process interaction")
        payload = operation(repository, normalized)
    except Exception as exc:
        payload = {
            "status": "error",
            "document_path": document_path,
            "error": str(exc),
        }
    return json.dumps(payload, ensure_ascii=False)


@tool
def read_pdf_document(
    document_path: str,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read an allowed PDF completely with hybrid OCR and page source markers."""
    return _execute_document_read(
        document_path,
        runtime,
        {".pdf"},
        lambda repository, normalized: repository.read_pdf(normalized),
    )


@tool
def read_spreadsheet_document(
    document_path: str,
    sheet_name: str | None = None,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read an allowed spreadsheet sheet completely with row source markers."""
    return _execute_document_read(
        document_path,
        runtime,
        {".xlsx", ".xlsm"},
        lambda repository, normalized: repository.read_spreadsheet(
            normalized,
            sheet_name=sheet_name,
        ),
    )


@tool
def read_csv_document(
    document_path: str,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read an allowed CSV completely with row source markers."""
    return _execute_document_read(
        document_path,
        runtime,
        {".csv"},
        lambda repository, normalized: repository.read_csv(normalized),
    )


DOCUMENT_TOOLS = [read_pdf_document, read_spreadsheet_document, read_csv_document]
