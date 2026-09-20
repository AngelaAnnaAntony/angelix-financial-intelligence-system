from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from ..extensions import db
from ..models.document_extraction import DocumentExtraction
from ..models.extraction_candidate import ExtractionCandidate
from ..models.upload import Upload
from ..ocr.financial_entity_extractor import extract_candidates
from ..ocr.pdf_processor import extract_pdf_text
from ..ocr.text_cleaner import clean_text
from ..ocr.tesseract_engine import extract_text as tesseract_extract


class DocumentProcessingService:
    """
    Processes uploaded financial documents and stores extraction results.

    The service deliberately separates extracted candidates from trusted
    financial transactions. Candidates must be reviewed before they can
    become Transaction records.
    """

    SUPPORTED_TABULAR_EXTENSIONS = {
        ".csv",
        ".xlsx",
        ".xls",
    }

    SUPPORTED_IMAGE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
    }

    SUPPORTED_DOCUMENT_EXTENSIONS = {
        ".pdf",
        ".csv",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg",
    }

    @classmethod
    def process_upload(cls, upload):
        """
        Process an Upload model instance.

        Returns:
            DocumentExtraction: The resulting extraction record.

        Raises:
            ValueError: If the upload is invalid or unsupported.
            RuntimeError: If document processing fails.
        """
        if not isinstance(upload, Upload):
            raise ValueError("A valid Upload record is required.")

        if upload.is_deleted:
            raise ValueError("Deleted uploads cannot be processed.")

        file_path = Path(upload.file_path)

        if not file_path.exists() or not file_path.is_file():
            error_message = "The uploaded file could not be found."

            upload.processing_status = "failed"
            upload.processing_error = error_message

            db.session.commit()

            raise RuntimeError(error_message)

        extension = file_path.suffix.lower()

        if extension not in cls.SUPPORTED_DOCUMENT_EXTENSIONS:
            error_message = (
                f"Unsupported document type: {extension or 'unknown'}"
            )

            upload.processing_status = "failed"
            upload.processing_error = error_message

            db.session.commit()

            raise ValueError(error_message)

        upload.processing_status = "processing"
        upload.processing_error = None

        db.session.flush()

        extraction = None

        try:
            text, method, document_type = cls._extract_document(
                file_path
            )

            cleaned_text = clean_text(text or "")

            candidates = extract_candidates(cleaned_text)

            extraction_confidence = cls._calculate_extraction_confidence(
                candidates
            )

            extraction = DocumentExtraction(
                upload_id=upload.id,
                organization_id=upload.organization_id,
                extracted_text=cleaned_text or None,
                document_type=document_type,
                extraction_method=method,
                processing_status="completed",
                confidence_score=extraction_confidence,
                processed_at=datetime.utcnow(),
            )

            db.session.add(extraction)
            db.session.flush()

            for candidate_data in candidates:
                candidate = cls._build_candidate(
                    extraction=extraction,
                    organization_id=upload.organization_id,
                    candidate_data=candidate_data,
                )

                db.session.add(candidate)

            upload.processing_status = "completed"
            upload.processing_error = None
            upload.processed_at = datetime.utcnow()
            upload.extracted_text_available = bool(cleaned_text)
            upload.extraction_method = method
            upload.document_type = document_type

            db.session.commit()

            return extraction

        except Exception as exc:
            db.session.rollback()

            upload = db.session.get(Upload, upload.id)

            if upload is not None:
                upload.processing_status = "failed"
                upload.processing_error = str(exc)[:5000]

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            raise RuntimeError(
                f"Document processing failed: {exc}"
            ) from exc

    @classmethod
    def reprocess_upload(cls, upload):
        """
        Safely reprocess an existing Upload using the current extraction
        and financial entity extraction pipeline.

        Reprocessing removes the previous untrusted extraction result and
        its candidates before creating a fresh extraction.

        Approved candidates are protected. If an existing extraction has
        already produced a trusted Transaction record, reprocessing is
        refused so that historical financial data cannot be silently
        changed.

        Returns:
            DocumentExtraction: The newly created extraction record.

        Raises:
            ValueError: If the upload is invalid, deleted, unsupported,
                or contains already-approved extraction candidates.
            RuntimeError: If the file is missing or processing fails.
        """
        if not isinstance(upload, Upload):
            raise ValueError("A valid Upload record is required.")

        if upload.is_deleted:
            raise ValueError("Deleted uploads cannot be reprocessed.")

        if upload.organization_id is None:
            raise ValueError(
                "The upload must belong to an organization before it "
                "can be reprocessed."
            )

        file_path = Path(upload.file_path)

        if not file_path.exists() or not file_path.is_file():
            error_message = "The uploaded file could not be found."

            upload.processing_status = "failed"
            upload.processing_error = error_message

            db.session.commit()

            raise RuntimeError(error_message)

        extension = file_path.suffix.lower()

        if extension not in cls.SUPPORTED_DOCUMENT_EXTENSIONS:
            error_message = (
                f"Unsupported document type: {extension or 'unknown'}"
            )

            upload.processing_status = "failed"
            upload.processing_error = error_message

            db.session.commit()

            raise ValueError(error_message)

        existing_extractions = (
            DocumentExtraction.query
            .filter_by(upload_id=upload.id)
            .order_by(DocumentExtraction.id.asc())
            .all()
        )

        extraction_ids = [
            extraction.id
            for extraction in existing_extractions
            if extraction.id is not None
        ]

        if extraction_ids:
            approved_count = (
                ExtractionCandidate.query
                .filter(
                    ExtractionCandidate.extraction_id.in_(extraction_ids),
                    ExtractionCandidate.review_status == "approved",
                )
                .count()
            )

            if approved_count > 0:
                raise ValueError(
                    "This upload cannot be reprocessed because one or "
                    "more extracted candidates have already been "
                    "approved as trusted transactions."
                )

        try:
            upload.processing_status = "processing"
            upload.processing_error = None
            upload.processed_at = None
            upload.extracted_text_available = False
            upload.extraction_method = None
            upload.document_type = None

            db.session.flush()

            for extraction in existing_extractions:
                db.session.delete(extraction)

            db.session.flush()

            text, method, document_type = cls._extract_document(
                file_path
            )

            cleaned_text = clean_text(text or "")

            candidates = extract_candidates(cleaned_text)

            extraction_confidence = cls._calculate_extraction_confidence(
                candidates
            )

            extraction = DocumentExtraction(
                upload_id=upload.id,
                organization_id=upload.organization_id,
                extracted_text=cleaned_text or None,
                document_type=document_type,
                extraction_method=method,
                processing_status="completed",
                confidence_score=extraction_confidence,
                processed_at=datetime.utcnow(),
            )

            db.session.add(extraction)
            db.session.flush()

            for candidate_data in candidates:
                candidate = cls._build_candidate(
                    extraction=extraction,
                    organization_id=upload.organization_id,
                    candidate_data=candidate_data,
                )

                db.session.add(candidate)

            upload.processing_status = "completed"
            upload.processing_error = None
            upload.processed_at = datetime.utcnow()
            upload.extracted_text_available = bool(cleaned_text)
            upload.extraction_method = method
            upload.document_type = document_type

            db.session.commit()

            return extraction

        except Exception as exc:
            db.session.rollback()

            upload = db.session.get(Upload, upload.id)

            if upload is not None:
                upload.processing_status = "failed"
                upload.processing_error = str(exc)[:5000]

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            raise RuntimeError(
                f"Document reprocessing failed: {exc}"
            ) from exc

    @classmethod
    def process(cls, path):
        """
        Backward-compatible processing method.

        This method extracts and cleans document content without creating
        database records. Database-backed processing should use
        process_upload().
        """
        file_path = Path(path)

        text, _, _ = cls._extract_document(file_path)

        cleaned_text = clean_text(text or "")

        return {
            "text": cleaned_text,
            "candidates": extract_candidates(cleaned_text),
        }

    @classmethod
    def _extract_document(cls, file_path):
        """
        Extract raw text from a supported document.

        Returns:
            tuple[str, str, str]:
                extracted text,
                extraction method,
                detected document type
        """
        extension = file_path.suffix.lower()

        if extension == ".pdf":
            text = extract_pdf_text(file_path)

            if text.strip():
                return text, "pymupdf", "pdf"

            text = cls._extract_scanned_pdf_text(file_path)

            if text.strip():
                return text, "tesseract_pdf_ocr", "pdf_scanned"

            return "", "pdf_ocr_no_text", "pdf_scanned"

        if extension in cls.SUPPORTED_TABULAR_EXTENSIONS:
            text = cls._extract_tabular_text(
                file_path,
                extension,
            )

            return (
                text,
                "pandas",
                "financial_table",
            )

        if extension in cls.SUPPORTED_IMAGE_EXTENSIONS:
            text = tesseract_extract(file_path)

            return (
                text,
                "tesseract",
                "image",
            )

        raise ValueError(
            f"Unsupported document extension: {extension}"
        )

    @staticmethod
    def _extract_scanned_pdf_text(file_path):
        """
        Render scanned PDF pages and extract text with Tesseract.

        PyMuPDF renders each PDF page into an image. The rendered image
        is then passed through the existing image preprocessing component
        before Tesseract OCR is performed.

        Temporary page images are deleted immediately after processing.
        """
        try:
            import fitz

            from ..ocr.image_preprocessor import preprocess_image

            page_text = []

            with fitz.open(str(file_path)) as document:
                for page_number, page in enumerate(
                    document,
                    start=1,
                ):
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False,
                    )

                    temporary_path = (
                        file_path.parent
                        / (
                            f".{file_path.stem}"
                            f"_page_{page_number}_ocr.png"
                        )
                    )

                    try:
                        pixmap.save(str(temporary_path))

                        processed_image = preprocess_image(
                            temporary_path
                        )

                        try:
                            import pytesseract

                            text = pytesseract.image_to_string(
                                processed_image
                            )
                        finally:
                            processed_image.close()

                        if text and text.strip():
                            page_text.append(
                                text.strip()
                            )

                    finally:
                        temporary_path.unlink(
                            missing_ok=True
                        )

            return "\n\n".join(page_text).strip()

        except Exception as exc:
            raise RuntimeError(
                f"Scanned PDF OCR failed: {exc}"
            ) from exc

    @staticmethod
    def _extract_tabular_text(file_path, extension):
        """
        Convert a CSV/XLS/XLSX document into normalized textual rows.

        The original uploaded file remains untouched.
        """
        if extension == ".csv":
            dataframe = pd.read_csv(
                file_path,
                dtype=str,
                keep_default_na=False,
            )
        else:
            dataframe = pd.read_excel(
                file_path,
                dtype=str,
            )

        if dataframe.empty:
            return ""

        dataframe = dataframe.fillna("")

        return dataframe.to_csv(
            index=False,
        )

    @classmethod
    def _build_candidate(
        cls,
        extraction,
        organization_id,
        candidate_data,
    ):
        """
        Convert an extractor result into a reviewable candidate.
        """
        amount = cls._safe_decimal(
            candidate_data.get("amount")
        )

        return ExtractionCandidate(
            extraction_id=extraction.id,
            organization_id=organization_id,
            transaction_date=cls._parse_date(
                candidate_data.get("date")
            ),
            description=(
                candidate_data.get("description")
                or candidate_data.get("raw_line")
                or None
            ),
            reference_number=(
                candidate_data.get("reference_number")
                or None
            ),
            amount=amount,
            debit_credit=(
                candidate_data.get("debit_credit")
                or None
            ),
            transaction_type=(
                candidate_data.get("transaction_type")
                or None
            ),
            category=(
                candidate_data.get("category")
                or None
            ),
            subcategory=(
                candidate_data.get("subcategory")
                or None
            ),
            confidence_score=cls._safe_decimal(
                candidate_data.get("confidence_score")
            ),
            raw_text=(
                candidate_data.get("raw_text")
                or candidate_data.get("raw_line")
                or None
            ),
            review_status="pending_review",
        )

    @staticmethod
    def _safe_decimal(value):
        """
        Convert a value to Decimal without allowing invalid numeric data
        to break the entire extraction process.
        """
        if value is None or value == "":
            return None

        try:
            decimal_value = Decimal(str(value))

            if not decimal_value.is_finite():
                return None

            return decimal_value

        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(value):
        """
        Parse common financial-document date representations.
        """
        if value is None or value == "":
            return None

        if isinstance(value, datetime):
            return value.date()

        if hasattr(value, "date") and not isinstance(value, str):
            try:
                return value.date()
            except (AttributeError, TypeError, ValueError):
                pass

        value = str(value).strip()

        formats = (
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%m/%d/%Y",
        )

        for date_format in formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                ).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _calculate_extraction_confidence(candidates):
        """
        Calculate a conservative aggregate extraction confidence.

        The current extractor does not provide confidence scores, so this
        method only returns a score when candidate confidence values exist.
        It does not invent a confidence value.
        """
        scores = []

        for candidate in candidates:
            value = candidate.get("confidence_score")

            if value is None:
                continue

            try:
                decimal_value = Decimal(str(value))

                if (
                    decimal_value.is_finite()
                    and Decimal("0") <= decimal_value <= Decimal("1")
                ):
                    scores.append(decimal_value)

            except (InvalidOperation, ValueError, TypeError):
                continue

        if not scores:
            return None

        return sum(scores) / Decimal(len(scores))