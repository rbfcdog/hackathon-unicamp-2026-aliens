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
            raise ValueError("Document was not supplied for this judge review")
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
    start_page: int = 1,
    max_pages: int = 5,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read text from an allowed PDF, with 1-based page pagination and source markers."""
    return _execute_document_read(
        document_path,
        runtime,
        {".pdf"},
        lambda repository, normalized: repository.read_pdf(
            normalized,
            start_page=start_page,
            max_pages=max_pages,
        ),
    )


@tool
def read_spreadsheet_document(
    document_path: str,
    sheet_name: str | None = None,
    start_row: int = 1,
    max_rows: int = 50,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read rows from an allowed XLSX or XLSM workbook, with sheet and row pagination."""
    return _execute_document_read(
        document_path,
        runtime,
        {".xlsx", ".xlsm"},
        lambda repository, normalized: repository.read_spreadsheet(
            normalized,
            sheet_name=sheet_name,
            start_row=start_row,
            max_rows=max_rows,
        ),
    )


@tool
def read_csv_document(
    document_path: str,
    start_row: int = 1,
    max_rows: int = 50,
    *,
    runtime: ToolRuntime,
) -> str:
    """Read rows from an allowed CSV file, with row pagination and source markers."""
    return _execute_document_read(
        document_path,
        runtime,
        {".csv"},
        lambda repository, normalized: repository.read_csv(
            normalized,
            start_row=start_row,
            max_rows=max_rows,
        ),
    )


DOCUMENT_TOOLS = [read_pdf_document, read_spreadsheet_document, read_csv_document]
