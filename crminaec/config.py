import os
from pathlib import Path
from typing import ClassVar, Optional

from dotenv import load_dotenv

from crminaec.__about__ import __author__, __email__, __version__

# Load environment variables from .env file
load_dotenv()

# Determine Base Directory (Goes up one level from crminaec folder to the project root)
BASE_DIR = Path(__file__).parent.parent.absolute()

class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    WTF_CSRF_ENABLED: bool = True

    # Database - will be set by create_app
    DATABASE_URL: Optional[str] = None
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Uploads
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB max upload
    UPLOAD_FOLDER: Path = Path(__file__).parent / 'web' / 'static' / 'uploads'
    ALLOWED_EXTENSIONS: set[str] = {'md'}

    # Application (Fixed: Added .parent so it points to the directory, not the file)
    PROJECT_ROOT: ClassVar[Path] = Path(__file__).parent.absolute()
    DATA_DIR: ClassVar[Path] = PROJECT_ROOT / 'data'
    CONFIG_DIR: ClassVar[Path] = PROJECT_ROOT / 'config'
    TESTS_DIR: ClassVar[Path] = PROJECT_ROOT / 'tests'
    
    # ==========================================
    # 🔑 SHARED OAUTH CREDENTIALS (PORTAL LOGIN)
    # ==========================================
    # These are shared across all environments and must be a "Web Application" credential
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

    @classmethod
    def init_app(cls, app):
        """Initialize application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration (Local Laptop)."""
    DEBUG: bool = True
    TESTING: bool = False

    # 1. Local Callback for Portal Login
    GOOGLE_CALLBACK_URL = os.environ.get('LOCAL_CALLBACK_URL','http://127.0.0.1:5000/login/google/callback')
    # 2. Local Desktop Credentials for Google Docs API
    GOOGLE_CLIENT_SECRETS = os.environ.get('LOCAL_CLIENT_SECRETS', str(BASE_DIR / 'desktop_credentials.json'))

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        print(f"🚧 Development mode enabled")


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG: bool = False
    TESTING: bool = True
    WTF_CSRF_ENABLED: bool = False

    GOOGLE_CALLBACK_URL = os.environ.get('LOCAL_CALLBACK_URL', 'http://127.0.0.1:5000/login/google/callback')
    GOOGLE_CLIENT_SECRETS = os.environ.get('LOCAL_CLIENT_SECRETS', 'dummy_credentials.json')
   
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        print(f"🧪 Testing mode enabled")


class ProductionConfig(Config):
    """Production configuration (IIS Server Tunnel)."""
    DEBUG: bool = False
    TESTING: bool = False

    SESSION_COOKIE_DOMAIN = ".crminaec.com"
    SESSION_COOKIE_SECURE = True 
    SESSION_COOKIE_SAMESITE = 'Lax'

    # 1. Production Callback for Portal Login
    GOOGLE_CALLBACK_URL = os.environ.get('GOOGLE_CALLBACK_URL', 'https://pearson.crminaec.com/login/google/callback')
    
    # 2. Production Desktop Credentials for Google Docs API (MUST be in server env variables)
    GOOGLE_CLIENT_SECRETS = os.environ.get('GOOGLE_CLIENT_SECRETS')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        print(f"🚀 Production mode enabled (IIS Tunnel)")
        cls.DATA_DIR.mkdir(exist_ok=True)


# Configuration dictionary
config: dict[str, type[Config]] = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> type[Config]:
    """Get configuration class by name."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    return config.get(config_name, config['default'])