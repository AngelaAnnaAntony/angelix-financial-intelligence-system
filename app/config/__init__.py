import os

from .development import DevelopmentConfig
from .production import ProductionConfig
from .testing import TestingConfig


_CONFIG_MAP = {
    "app.config.development.DevelopmentConfig": DevelopmentConfig,
    "app.config.production.ProductionConfig": ProductionConfig,
    "app.config.testing.TestingConfig": TestingConfig,
}


def load_config():
    config_path = os.getenv(
        "FLASK_CONFIG",
        "app.config.development.DevelopmentConfig",
    )

    return _CONFIG_MAP.get(
        config_path,
        DevelopmentConfig,
    )