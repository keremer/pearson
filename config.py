"""
Setup configuration for Pearson Course Management System.
"""
from setuptools import setup, find_packages

"""
Configuration management for Pearson.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# project_setup.py - Place this in pearson/ (project root)
"""
Project setup module - Import this FIRST in any file to ensure proper imports.
"""

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent

def setup_project_paths():
    """
    Setup Python path for the entire project.
    Call this function at the beginning of any module.
    """
    # Add project root to sys.path if not already there
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    
    return PROJECT_ROOT

def get_absolute_path(relative_path: str) -> Path:
    """
    Convert a relative path to absolute path from project root.
    """
    return PROJECT_ROOT / relative_path

# Run setup automatically when imported
setup_project_paths()

print(f"✅ Project paths configured")
print(f"   Project root: {PROJECT_ROOT}")
print(f"   Python path includes project root")

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    WTF_CSRF_ENABLED = True
    
    # Database
    @property
    def DATABASE_URL(self):
        """Get database URL with data folder."""
        from pearson import get_database_url
        return get_database_url()
    
    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    UPLOAD_FOLDER = Path(__file__).parent / 'web' / 'static' / 'uploads'
    ALLOWED_EXTENSIONS = {'md'}

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    @property
    def DATABASE_URL(self):
        return 'sqlite:///:memory:'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    @property
    def DATABASE_URL(self):
        return os.environ.get('DATABASE_URL', 'sqlite:///data/courses.db')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="pearson-course-manager",
    version="1.0.0",
    author="Pearson Team",
    author_email="",
    description="Course Management System with Learning Outcome Tracking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/keremer/pearson",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Flask",
        "Topic :: Education",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "pearson=pearson.__main__:main",
        ],
    },
    include_package_data=True,
    package_data={
        "pearson.web": ["templates/*", "static/**/*"],
    },
)