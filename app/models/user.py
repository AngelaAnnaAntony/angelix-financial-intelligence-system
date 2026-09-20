from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(50), nullable=False, default="user")

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = db.relationship(
        "Organization",
        foreign_keys=[organization_id],
        back_populates="users",
    )

    uploads = db.relationship(
        "Upload",
        foreign_keys="Upload.uploaded_by",
        back_populates="uploader",
        lazy=True,
    )

    reviewed_extraction_candidates = db.relationship(
        "ExtractionCandidate",
        foreign_keys="ExtractionCandidate.reviewed_by",
        back_populates="reviewer",
        lazy=True,
    )

    def set_password(self, password):
        """Hash and store a user's password using Werkzeug."""
        if not password:
            raise ValueError("Password cannot be empty.")

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a plain-text password against the stored password hash."""
        if not password or not self.password_hash:
            return False

        return check_password_hash(
            self.password_hash,
            password,
        )

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f"<User {self.email}>"