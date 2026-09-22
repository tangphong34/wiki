import re
import tempfile
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyMuPDFLoader


class ParserService:
    """Extract and normalize PDF content before Dify ingestion."""

    TABLE_LINE_PATTERN = re.compile(r"^\s*\|.+\|\s*$")

    def parse_pdf_bytes(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        suffix = Path(filename).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            loader = PyMuPDFLoader(file_path=tmp_path)
            pages = loader.load()

            formatted_pages: list[str] = []
            for page in pages:
                page_number = page.metadata.get("page", "unknown")
                cleaned_text = self._format_tables(page.page_content.strip())
                formatted_pages.append(
                    f"## Page {page_number + 1 if isinstance(page_number, int) else page_number}\n\n{cleaned_text}"
                )

            markdown_body = "\n\n".join(formatted_pages)
            title = Path(filename).stem

            return {
                "title": title,
                "markdown": markdown_body,
                "page_count": len(pages),
                "metadata": {
                    "source_filename": filename,
                    "page_count": len(pages),
                },
            }
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _format_tables(self, text: str) -> str:
        """
        Heuristic table formatter:
        - Detect pipe-delimited rows
        - Ensure markdown table separator row exists
        """
        lines = text.splitlines()
        output: list[str] = []
        table_buffer: list[str] = []

        def flush_table() -> None:
            if not table_buffer:
                return
            normalized = self._normalize_markdown_table(table_buffer)
            output.extend(normalized)
            output.append("")
            table_buffer.clear()

        for line in lines:
            if self.TABLE_LINE_PATTERN.match(line):
                table_buffer.append(line.strip())
            else:
                flush_table()
                output.append(line)

        flush_table()
        return "\n".join(output).strip()

    def _normalize_markdown_table(self, rows: list[str]) -> list[str]:
        if not rows:
            return []

        parsed_rows = [
            [cell.strip() for cell in row.strip("|").split("|")]
            for row in rows
        ]
        col_count = max(len(r) for r in parsed_rows)

        normalized_rows = []
        for row in parsed_rows:
            padded = row + [""] * (col_count - len(row))
            normalized_rows.append("| " + " | ".join(padded) + " |")

        if len(normalized_rows) == 1:
            separator = "| " + " | ".join(["---"] * col_count) + " |"
            normalized_rows.append(separator)

        return normalized_rows


parser_service = ParserService()
