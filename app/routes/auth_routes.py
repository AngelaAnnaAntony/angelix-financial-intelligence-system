from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_user,
    logout_user,
)

from ..utils.email_service import send_password_reset_email
from ..extensions import db
from ..models.password_reset_token import PasswordResetToken
from ..models.user import User
from ..utils.security import validate_password


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
)


# =========================================================
# HELPERS
# =========================================================

PASSWORD_RESET_EXPIRY_MINUTES = 30


def _hash_reset_token(token):
    """
    Hash a password-reset token before storing it.

    The raw token is only included in the reset URL.
    PostgreSQL stores the SHA-256 hash rather than the
    usable token itself.
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def _generate_reset_token():
    """
    Generate a cryptographically secure reset token.
    """
    return secrets.token_urlsafe(48)


# =========================================================
# REGISTER
# =========================================================

@auth_bp.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.home")
        )

    if request.method == "POST":

        first_name = request.form.get(
            "first_name",
            "",
        ).strip()

        last_name = request.form.get(
            "last_name",
            "",
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        password = request.form.get(
            "password",
            "",
        )


        # -------------------------------------------------
        # Basic validation
        # -------------------------------------------------

        if not first_name:

            flash(
                "First name is required.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        if not last_name:

            flash(
                "Last name is required.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        if not email:

            flash(
                "Email address is required.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        if not password:

            flash(
                "Password is required.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        # -------------------------------------------------
        # Password validation
        # -------------------------------------------------

        try:

            validate_password(password)

        except ValueError as exc:

            flash(
                str(exc),
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        # -------------------------------------------------
        # Existing email
        # -------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()


        if existing_user:

            flash(
                "Email already registered.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        # -------------------------------------------------
        # Create user
        # -------------------------------------------------

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        user.set_password(password)

        db.session.add(user)

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to create your account. "
                "Please try again.",
                "error",
            )

            return render_template(
                "auth/register.html"
            )


        login_user(user)

        return redirect(
            url_for("dashboard.home")
        )


    return render_template(
        "auth/register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.home")
        )


    if request.method == "POST":

        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        password = request.form.get(
            "password",
            "",
        )


        user = User.query.filter_by(
            email=email
        ).first()


        if (
            user
            and user.check_password(password)
            and user.is_active
        ):

            login_user(user)

            user.last_login_at = datetime.now(
                timezone.utc
            )

            db.session.commit()

            return redirect(
                url_for("dashboard.home")
            )


        flash(
            "Invalid credentials.",
            "error",
        )


    return render_template(
        "auth/login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@auth_bp.post("/logout")
def logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"],
)
def forgot_password():

    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.home")
        )

    # -----------------------------------------------------
    # Always use the same response message.
    #
    # This prevents attackers from discovering whether
    # an email address has an Angelix account.
    # -----------------------------------------------------

    generic_message = (
        "If an account exists for that email, "
        "a password reset link has been generated."
    )

    if request.method == "POST":

        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        user = User.query.filter_by(
            email=email
        ).first()

        # -------------------------------------------------
        # Only generate a reset token for an existing,
        # active account.
        # -------------------------------------------------

        if user and user.is_active:

            # ---------------------------------------------
            # Invalidate previous unused tokens
            # ---------------------------------------------

            existing_tokens = (
                PasswordResetToken.query
                .filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .all()
            )

            for old_token in existing_tokens:
                old_token.used_at = datetime.now(
                    timezone.utc
                )

            # ---------------------------------------------
            # Generate secure token
            # ---------------------------------------------

            raw_token = _generate_reset_token()

            token_hash = _hash_reset_token(
                raw_token
            )

            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    minutes=PASSWORD_RESET_EXPIRY_MINUTES
                )
            )

            reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )

            db.session.add(reset_token)

            try:
                db.session.commit()

            except Exception:
                db.session.rollback()

                flash(
                    generic_message,
                    "success",
                )

                return render_template(
                    "auth/forgot_password.html"
                )

            # ---------------------------------------------
            # Generate password reset URL
            # ---------------------------------------------

            reset_url = url_for(
                "auth.reset_password",
                token=raw_token,
                _external=True,
            )

            # ---------------------------------------------
            # Send password reset email
            # ---------------------------------------------

            email_sent = send_password_reset_email(
                recipient=user.email,
                reset_url=reset_url,
                expiry_minutes=PASSWORD_RESET_EXPIRY_MINUTES,
            )

            current_app.logger.info(
                "Password reset email attempted for user_id=%s, "
                "delivery_success=%s",
                user.id,
                email_sent,
            )
            # ---------------------------------------------
            # Always show the generic response
            # ---------------------------------------------

            flash(
                generic_message,
                "success",
            )

            # ---------------------------------------------
            # Development fallback
            #
            # If SMTP is not configured or email delivery
            # fails during local development, expose the
            # reset URL so the workflow can still be tested.
            # ---------------------------------------------

            if (
                not email_sent
                and current_app.debug
            ):
                return render_template(
                    "auth/forgot_password.html",
                    development_reset_url=reset_url,
                )

        # -------------------------------------------------
        # IMPORTANT:
        # Whether the account exists or not, return the
        # same page with the same generic message.
        # -------------------------------------------------

        return render_template(
            "auth/forgot_password.html"
        )

    # -----------------------------------------------------
    # GET request
    # -----------------------------------------------------

    return render_template(
        "auth/forgot_password.html"
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
)
def reset_password(token):

    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.home")
        )


    if not token:

        flash(
            "Invalid password reset link.",
            "error",
        )

        return redirect(
            url_for("auth.forgot_password")
        )


    token_hash = _hash_reset_token(
        token
    )


    reset_token = (
        PasswordResetToken.query
        .filter_by(
            token_hash=token_hash
        )
        .first()
    )


    # -----------------------------------------------------
    # Validate token
    # -----------------------------------------------------

    if not reset_token:

        flash(
            "This password reset link is invalid.",
            "error",
        )

        return redirect(
            url_for("auth.forgot_password")
        )


    now = datetime.now(timezone.utc)


    if reset_token.used_at is not None:

        flash(
            "This password reset link has already been used.",
            "error",
        )

        return redirect(
            url_for("auth.forgot_password")
        )


    if reset_token.expires_at <= now:

        flash(
            "This password reset link has expired.",
            "error",
        )

        return redirect(
            url_for("auth.forgot_password")
        )


    user = User.query.get(
        reset_token.user_id
    )


    if not user or not user.is_active:

        flash(
            "This password reset link is invalid.",
            "error",
        )

        return redirect(
            url_for("auth.forgot_password")
        )


    # -----------------------------------------------------
    # Submit new password
    # -----------------------------------------------------

    if request.method == "POST":

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error",
            )

            return render_template(
                "auth/reset_password.html"
            )


        try:

            validate_password(password)

        except ValueError as exc:

            flash(
                str(exc),
                "error",
            )

            return render_template(
                "auth/reset_password.html"
            )


        # -------------------------------------------------
        # Update password
        # -------------------------------------------------

        user.set_password(password)

        reset_token.used_at = now

        db.session.commit()


        flash(
            "Your password has been reset successfully. "
            "You can now sign in.",
            "success",
        )


        return redirect(
            url_for("auth.login")
        )


    return render_template(
        "auth/reset_password.html"
    )