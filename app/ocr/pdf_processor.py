from pathlib import Path


def extract_pdf_text(path):
    """
    Extract text from a PDF using PyMuPDF.

    This function is responsible only for extracting an existing text layer.
    Scanned-PDF OCR fallback is handled by the document processing service.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a PDF file, received: {file_path.suffix}"
        )

    try:
        import fitz

        with fitz.open(str(file_path)) as document:
            pages = [
                page.get_text("text")
                for page in document
            ]

        return "\n".join(pages).strip()

    except Exception as exc:
        raise RuntimeError(
            f"PDF extraction failed: {exc}"
        ) from exc