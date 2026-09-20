import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from the project root .env file.
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + str(BASE_DIR / "angelix_dev.db"),
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = (
        int(os.getenv("MAX_CONTENT_LENGTH_MB", "25")) * 1024 * 1024
    )

    UPLOAD_FOLDER = str(
        BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")
    )

    GENERATED_REPORT_FOLDER = str(
        BASE_DIR / os.getenv(
            "GENERATED_REPORT_FOLDER",
            "generated_reports",
        )
    )

    LOG_FOLDER = str(
        BASE_DIR / os.getenv("LOG_FOLDER", "logs")
    )

    ALLOWED_UPLOAD_EXTENSIONS = {
        "pdf",
        "csv",
        "xlsx",
        "xls",
        "png",
        "jpg",
        "jpeg",
    }

    OPENROUTER_API_KEY = os.getenv(
        "OPENROUTER_API_KEY",
        "",
    )

    OPENROUTER_MODEL = os.getenv(
        "OPENROUTER_MODEL",
        "",
    )

    OPENROUTER_BASE_URL = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )

    OPENROUTER_TIMEOUT_SECONDS = int(
        os.getenv(
            "OPENROUTER_TIMEOUT_SECONDS",
            "60",
        )
    )

    DEFAULT_CURRENCY = os.getenv(
        "DEFAULT_CURRENCY",
        "INR",
    )

    FLASK_HOST = os.getenv(
        "FLASK_HOST",
        "127.0.0.1",
    )

    FLASK_PORT = int(
        os.getenv(
            "FLASK_PORT",
            "5000",
        )
    )

    MAIL_SERVER = os.getenv(
        "MAIL_SERVER",
        "",
    )

    MAIL_PORT = int(
        os.getenv(
            "MAIL_PORT",
            "587",
        )
    )

    MAIL_USERNAME = os.getenv(
        "MAIL_USERNAME",
        "",
    )

    MAIL_PASSWORD = os.getenv(
        "MAIL_PASSWORD",
        "",
    )

    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        "",
    )

    MAIL_USE_TLS = (
        os.getenv(
            "MAIL_USE_TLS",
            "true",
        ).lower()
        == "true"
    )

    MAIL_USE_SSL = (
        os.getenv(
            "MAIL_USE_SSL",
            "false",
        ).lower()
        == "true"
    )