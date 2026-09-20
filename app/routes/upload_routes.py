from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models.upload import Upload
from ..services.access_service import require_member
from ..services.document_processing_service import (
    DocumentProcessingService,
)
from ..utils.file_utils import (
    detect_mime,
    private_filename,
    safe_org_path,
    sha256_file,
    validate_upload,
)


upload_bp = Blueprint(
    "uploads",
    __name__,
    url_prefix="/organizations",
)


# ============================================================================
# UPLOAD / UPLOAD HISTORY
# ============================================================================


@upload_bp.route(
    "/<organization_id>/uploads",
    methods=["GET", "POST"],
)
@login_required
def uploads(organization_id):
    """
    Display organization uploads and process newly uploaded documents.
    """

    try:
        require_member(organization_id)
    except PermissionError:
        return ("Forbidden", 403)

    if request.method == "POST":
        uploaded_file = request.files.get("file")

        if not uploaded_file or not uploaded_file.filename:
            flash("Choose a file.", "error")
            return redirect(request.url)

        try:
            extension = validate_upload(
                uploaded_file.filename,
                current_app.config[
                    "ALLOWED_UPLOAD_EXTENSIONS"
                ],
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(request.url)

        file_path = None
        upload = None

        try:
            organization_folder = safe_org_path(
                current_app.config["UPLOAD_FOLDER"],
                organization_id,
            )

            stored_filename = private_filename(
                extension
            )

            file_path = (
                organization_folder
                / stored_filename
            )

            uploaded_file.save(file_path)

            upload = Upload(
                organization_id=int(organization_id),
                uploaded_by=current_user.id,
                original_filename=Path(
                    uploaded_file.filename
                ).name,
                stored_filename=stored_filename,
                file_path=str(file_path),
                file_extension=extension,
                mime_type=detect_mime(file_path),
                file_size=file_path.stat().st_size,
                file_hash=sha256_file(file_path),
                processing_status="pending",
                extracted_text_available=False,
                is_encrypted=False,
                is_deleted=False,
            )

            db.session.add(upload)
            db.session.commit()

        except Exception:
            db.session.rollback()

            if file_path is not None:
                try:
                    file_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    current_app.logger.exception(
                        "Failed to remove incomplete upload file."
                    )

            current_app.logger.exception(
                "Failed to store uploaded file."
            )

            flash(
                "The file could not be stored. Please try again.",
                "error",
            )

            return redirect(request.url)

        # ------------------------------------------------------------------
        # Process the uploaded document after the Upload record has been
        # committed successfully.
        # ------------------------------------------------------------------

        try:
            extraction = (
                DocumentProcessingService.process_upload(
                    upload
                )
            )

            candidate_count = len(
                extraction.candidates
            )

            if candidate_count:
                flash(
                    (
                        "Document processed successfully. "
                        f"{candidate_count} transaction candidate(s) "
                        "are waiting for review."
                    ),
                    "success",
                )
            else:
                flash(
                    (
                        "Document processed, but no transaction "
                        "candidates were detected."
                    ),
                    "warning",
                )

        except Exception:
            current_app.logger.exception(
                "Document processing failed for upload %s.",
                upload.id,
            )

            flash(
                (
                    "The file was uploaded, but document processing "
                    "failed. Check the processing status for details."
                ),
                "error",
            )

        return redirect(
            url_for(
                "uploads.uploads",
                organization_id=organization_id,
            )
        )

    rows = (
        Upload.query
        .filter_by(
            organization_id=int(organization_id),
            is_deleted=False,
        )
        .order_by(
            Upload.created_at.desc()
        )
        .all()
    )

    return render_template(
        "uploads/list.html",
        uploads=rows,
        organization_id=organization_id,
    )


# ============================================================================
# DELETE UPLOAD
# ============================================================================


@upload_bp.post(
    "/<organization_id>/uploads/<int:upload_id>/delete"
)
@login_required
def delete_upload(organization_id, upload_id):
    """
    Delete an uploaded document from the organization's upload history.

    The database record is retained as a soft-deleted record for audit
    purposes while the physical uploaded file is removed from storage.

    Trusted financial transactions that may already have been approved
    from the document are not deleted.
    """

    try:
        require_member(organization_id)
    except PermissionError:
        return ("Forbidden", 403)

    upload = (
        Upload.query
        .filter_by(
            id=int(upload_id),
            organization_id=int(organization_id),
            is_deleted=False,
        )
        .first()
    )

    if upload is None:
        flash(
            "The requested upload was not found.",
            "error",
        )

        return redirect(
            url_for(
                "uploads.uploads",
                organization_id=organization_id,
            )
        )

    # ------------------------------------------------------------------
    # Preserve the physical path before marking the record deleted.
    # ------------------------------------------------------------------

    file_path = None

    if upload.file_path:
        file_path = Path(upload.file_path)

    try:
        # --------------------------------------------------------------
        # Soft-delete the database record.
        # --------------------------------------------------------------

        upload.is_deleted = True

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete upload record %s.",
            upload_id,
        )

        flash(
            "The document could not be deleted. Please try again.",
            "error",
        )

        return redirect(
            url_for(
                "uploads.uploads",
                organization_id=organization_id,
            )
        )

    # ------------------------------------------------------------------
    # Remove the physical file after the database transaction succeeds.
    # ------------------------------------------------------------------

    if file_path is not None:
        try:
            file_path.unlink(
                missing_ok=True
            )

        except OSError:
            current_app.logger.exception(
                "Upload %s was marked deleted, but its physical "
                "file could not be removed: %s",
                upload_id,
                file_path,
            )

            flash(
                (
                    "The document was removed from Upload History, "
                    "but its stored file could not be removed. "
                    "Please contact an administrator."
                ),
                "warning",
            )

            return redirect(
                url_for(
                    "uploads.uploads",
                    organization_id=organization_id,
                )
            )

    flash(
        "Document deleted successfully.",
        "success",
    )

    return redirect(
        url_for(
            "uploads.uploads",
            organization_id=organization_id,
        )
    )