"""
Google Docs Platform Module
"""

# Use relative imports to keep the package self-contained
from .client import GoogleDocsClient
from .config import GoogleDocsConfig
from .parser import GoogleDocsParser

__all__ = ['GoogleDocsConfig', 'GoogleDocsClient', 'GoogleDocsParser']
