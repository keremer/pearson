"""
Unified Interoperability Manager - Single interface for all platforms
"""
from typing import Dict, Any, List, Optional

# Import from your existing __init__.py
from pearson.interop import Platform, SyncDirection, BaseInteropClient, BaseContentParser

# Import platform-specific implementations
from pearson.interop.google_docs import GoogleDocsConfig, GoogleDocsClient, GoogleDocsParser


class InteropManager:
    def __init__(self, user_id: str = "default"):
        self.clients = {}
        self.parsers = {}
        self._initialize_platforms(user_id)
    
    def _initialize_platforms(self, user_id):
        """Initialize all enabled platform clients"""
        # Google Docs
        try:
            config = GoogleDocsConfig(
                user_id=user_id
                #client_secrets_path="client_secrets.json",
                #token_path="token.json"
            )
            
            # Your GoogleDocsClient should inherit from BaseInteropClient
            self.clients[Platform.GOOGLE_DOCS] = GoogleDocsClient(config)
            
            # Your GoogleDocsParser should inherit from BaseContentParser
            self.parsers[Platform.GOOGLE_DOCS] = GoogleDocsParser()
            
            print(f"✅ {Platform.GOOGLE_DOCS.value} client initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize {Platform.GOOGLE_DOCS.value}: {e}")
    
    def import_from_platform(self, platform: Platform, source_id: str) -> Optional[Dict[str, Any]]:
        """Import content from any supported platform"""
        if platform not in self.clients:
            raise ValueError(f"Platform {platform.value} not supported or not configured")
        
        client = self.clients[platform]
        parser = self.parsers.get(platform)
        
        # All clients should implement BaseInteropClient.get_content()
        try:
            external_content = client.get_content(source_id)
            if external_content and parser:
                # All parsers should implement BaseContentParser.parse_to_course_structure()
                return parser.parse_to_course_structure(external_content)
        except Exception as e:
            print(f"❌ Error importing from {platform.value}: {e}")
            return None
        
        return None
    
    def export_to_platform(self, platform: Platform, content: Dict[str, Any], 
                         target_id: Optional[str] = None) -> Optional[str]:
        """Export content to any supported platform"""
        if platform not in self.clients:
            raise ValueError(f"Platform {platform.value} not supported or not configured")
        
        client = self.clients[platform]
        
        try:
            if target_id:
                # Update existing document
                success = client.update_content(target_id, content)
                return target_id if success else None
            else:
                # Create new document
                # Note: You might need to adapt this based on your actual interface
                if hasattr(client, 'create_document'):
                    title = content.get('title', 'Untitled')
                    return client.create_document(title)
        except Exception as e:
            print(f"❌ Error exporting to {platform.value}: {e}")
            return None
        
        return None
    
    def get_supported_platforms(self) -> List[Platform]:
        """Get list of currently supported platforms"""
        return list(self.clients.keys())
    
    # ... rest of your manager methods ...