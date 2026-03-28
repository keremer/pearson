"""
Unified Interoperability Manager - Single interface for all platforms.
"""
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

# Import only base classes and enums at the top level
from . import BaseContentParser, BaseInteropClient, Platform

# Type-only imports (erased at runtime)
if TYPE_CHECKING:
    from crminaec.core.interop.google_docs.client import GoogleDocsClient
    from crminaec.core.interop.google_docs.config import GoogleDocsConfig
    from crminaec.core.interop.google_docs.parser import GoogleDocsParser

logger = logging.getLogger(__name__)

class InteropManager:
    """Universal manager for interoperability across multiple platforms."""
    
    def __init__(self):
        self.clients: Dict[Platform, BaseInteropClient] = {}
        self.parsers: Dict[Platform, BaseContentParser] = {}
        self._initialize_platforms()
    
    def _initialize_platforms(self):
        """Initialize all enabled platform clients and parsers."""
        try:
            # RUNTIME IMPORTS: This breaks the circular dependency chain
            from .google_docs.client import GoogleDocsClient
            from .google_docs.config import GoogleDocsConfig
            from .google_docs.parser import GoogleDocsParser
            
            config = GoogleDocsConfig()
            self.clients[Platform.GOOGLE_DOCS] = GoogleDocsClient(config)
            self.parsers[Platform.GOOGLE_DOCS] = GoogleDocsParser()
            
            print(f"✅ {Platform.GOOGLE_DOCS.value} client initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize {Platform.GOOGLE_DOCS.value}: {e}")

    def import_from_platform(self, platform: Platform, source_id: str) -> Optional[Dict[str, Any]]:
        """Import content from a supported platform and parse it."""
        client = self.clients.get(platform)
        parser = self.parsers.get(platform)
        
        if not client:
            return None
        
        try:
            external_content = client.get_content(source_id)
            if not external_content:
                return None
            
            if parser:
                course_data = parser.parse_to_course_structure(external_content)
                if course_data:
                    course_data.setdefault('metadata', {})['imported_from'] = platform.value
                    course_data['metadata']['imported_at'] = datetime.utcnow().isoformat()
                return course_data
            
            return external_content
        except Exception as e:
            logger.error(f"❌ Error importing from {platform.value}: {e}")
            return None

    def export_to_platform(self, platform: Platform, content: Dict[str, Any], 
                           target_id: Optional[str] = None) -> Optional[str]:
        """Export content: Update if target_id exists, else Create."""
        client = self.clients.get(platform)
        if not client:
            return None
        
        try:
            if target_id:
                success = client.update_content(target_id, content)
                return target_id if success else None
            
            # Use hasattr/getattr safely for platform-specific methods
            if hasattr(client, 'create_document'):
                title = content.get('title', 'Untitled Document')
                return client.create_document(title) # type: ignore
            
            return None
        except Exception as e:
            logger.error(f"❌ Error exporting: {e}")
            return None

    def get_platform_status(self) -> Dict[Platform, Dict[str, Any]]:
        """Return status for initialized platforms."""
        status = {}
        for platform, client in self.clients.items():
            status[platform] = {
                'initialized': True,
                'authenticated': getattr(client, 'authenticated', False),
                'parser_available': platform in self.parsers,
            }
        return status

def create_interop_manager() -> InteropManager:
    """Factory function for initialization."""
    return InteropManager()