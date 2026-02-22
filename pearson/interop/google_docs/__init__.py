"""
Google Docs Platform Module
"""
from .config import GoogleDocsConfig
from .client import GoogleDocsClient
from .parser import GoogleDocsParser

__all__ = ['GoogleDocsConfig', 'GoogleDocsClient', 'GoogleDocsParser']