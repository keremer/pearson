"""
Configuration management for Pearson.
"""
import os
from pathlib import Path
from typing import Optional, ClassVar

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    WTF_CSRF_ENABLED: bool = True

    # Database - will be set by create_app
    DATABASE_URL: Optional[str] = None

    # Uploads
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB max upload
    UPLOAD_FOLDER: Path = Path(__file__).parent / 'web' / 'static' / 'uploads'
    ALLOWED_EXTENSIONS: set[str] = {'md'}

    # Application
    PROJECT_ROOT: ClassVar[Path] = Path(__file__).parent.absolute()
    DATA_DIR: ClassVar[Path] = PROJECT_ROOT / 'data'
    CONFIG_DIR: ClassVar[Path] = PROJECT_ROOT / 'config'
    TESTS_DIR: ClassVar[Path] = PROJECT_ROOT / 'tests'

    @classmethod
    def init_app(cls, app):
        """Initialize application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG: bool = True
    TESTING: bool = False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # Development-specific initialization
        print(f"🚧 Development mode enabled")


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG: bool = False
    TESTING: bool = True
    WTF_CSRF_ENABLED: bool = False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # Testing-specific initialization
        print(f"🧪 Testing mode enabled")


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG: bool = False
    TESTING: bool = False

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # Production-specific initialization
        print(f"🚀 Production mode enabled")

        # Ensure data directory exists
        cls.DATA_DIR.mkdir(exist_ok=True)


# Configuration dictionary
config: dict[str, type[Config]] = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> type[Config]:
    """
    Get configuration class by name.

    Args:
        config_name (str): Configuration name ('development', 'testing', 'production')

    Returns:
        Config: Configuration class
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    return config.get(config_name, config['default'])