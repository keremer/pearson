# pearson/interop/google_docs/config.py
"""
Google Docs Configuration with user-specific tokens.
"""
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class GoogleDocFormat(str, Enum):
    """Supported Google Doc formats."""
    PLAIN_TEXT = "text/plain"
    HTML = "text/html"
    MARKDOWN = "text/markdown"
    RICH_TEXT = "application/rtf"

@dataclass
class GoogleDocsConfig:
    """Configuration for Google Docs integration with user-specific tokens."""
    
    # Base path resolution (assuming this file is in pearson/interop/google_docs/)
    # Resolves to the root directory where .env and client_secrets.json usually live
    user_id: str = "default"
    # Centralized path logic
    client_secrets_path: str = field(default_factory=lambda: os.getenv(
        "GOOGLE_CLIENT_SECRETS","")) 

    token_path: str = "tokens/google_token.json"
    
    scopes: List[str] = field(default_factory=lambda: [

        'openid',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email'
    ])
    
    # Document settings
    default_folder_id: Optional[str] = None
    target_folder_id: Optional[str] = None 
    
    # Default behavior
    default_format: GoogleDocFormat = GoogleDocFormat.HTML
    auto_create_folders: bool = True
    sync_interval_minutes: int = 30
    preserve_formatting: bool = True
    include_metadata: bool = True
    
    # Export settings
    export_images: bool = True
    export_tables: bool = True
    max_file_size_mb: int = 10
    
    def __post_init__(self):
        """Validate configuration and set user-specific token path."""
        root = Path(__file__).parent.parent.parent.parent
        if not os.path.isabs(self.client_secrets_path):
            self.client_secrets_path = str(root / self.client_secrets_path)

        # Force tokens to a local subdirectory that isn't the root
        token_dir = root / "tokens"
        token_dir.mkdir(parents=True, exist_ok=True) 
        
        # Ensure the filename is specific
        self.token_path = str(token_dir / f"token_{self.user_id}.json")
            
        # Set user-specific token filename
        token_path_obj = Path(self.token_path)
        if "google_token.json" in token_path_obj.name:
            self.token_path = str(token_path_obj.with_name(f"token_{self.user_id}.json"))
        
        # Ensure token directory exists
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Sync folder ID attributes
        if self.target_folder_id and not self.default_folder_id:
            self.default_folder_id = self.target_folder_id
        elif self.default_folder_id and not self.target_folder_id:
            self.target_folder_id = self.default_folder_id
        
        # Validation Check
        if not Path(self.client_secrets_path).exists():
            print(f"⚠️  Warning: Client secrets file not found at {self.client_secrets_path}")
            print("❌ Error: GOOGLE_CLIENT_SECRETS not found in .env file.")
            print("   Please check the path in your .env file.")
            print("   Please download from: https://console.cloud.google.com/apis/credentials")

    @property
    def folder_id(self) -> Optional[str]:
        return self.default_folder_id or self.target_folder_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in self.__dict__.items() if k != 'project_root'}