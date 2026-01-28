"""
Interoperability Hub - Core types and interfaces
"""
from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
#from .google_docs.client import GoogleDocsClient

class Platform(Enum):
    GOOGLE_DOCS = "google_docs"
    #NOTION = "notion"
    #MICROSOFT = "microsoft"
    # Future: SLACK, GITHUB, etc.

class SyncDirection(Enum):
    IMPORT = "import"      # External → Our System
    EXPORT = "export"      # Our System → External
    SYNC = "sync" 
    BIDIRECTIONAL = "bidirectional"

class InteropConfig:
    """Base configuration for all interoperability platforms"""
    def __init__(self, platform: Platform):
        self.platform = platform
        self.enabled = True
        self.sync_direction = SyncDirection.IMPORT
        self.webhook_url = None

class BaseInteropClient(ABC):
    """Abstract base class for all interoperability clients"""
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the external platform"""
        pass
    
    @abstractmethod
    def get_content(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve content from external platform"""
        pass
    
    @abstractmethod
    def update_content(self, source_id: str, content: Dict[str, Any]) -> bool:
        """Update content on external platform"""
        pass

class BaseContentParser(ABC):
    """Abstract base class for content parsers"""
    
    @abstractmethod
    def parse_to_course_structure(self, external_content: Dict[str, Any]) -> Dict[str, Any]:
        """Parse external content to our course data structure"""
        pass

# Export for easy access
__all__ = [
    'Platform', 
    'SyncDirection', 
    'InteropConfig', 
    'BaseInteropClient', 
    'BaseContentParser'
]