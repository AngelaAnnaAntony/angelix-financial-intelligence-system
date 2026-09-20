from .development import DevelopmentConfig
from .production import ProductionConfig


def load_config():
    return DevelopmentConfig