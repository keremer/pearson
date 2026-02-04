# pearson/interop/google_docs/config.py (updated with both attributes)
"""
Google Docs Configuration with user-specific tokens.
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class GoogleDocFormat(str, Enum):
    """Supported Google Doc formats."""
    PLAIN_TEXT = "text/plain"
    HTML = "text/html"
    MARKDOWN = "text/markdown"
    RICH_TEXT = "application/rtf"


@dataclass
class GoogleDocsConfig:
    """Configuration for Google Docs integration with user-specific tokens."""
    
    # Authentication
    user_id: str = "default"
    client_secrets_path: str = "client_secrets.json"
    token_path: str = "tokens/google_token.json"
    scopes: List[str] = field(default_factory=lambda: [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email'
    ])
    
    # Document settings - support both old and new attribute names
    default_folder_id: Optional[str] = None
    target_folder_id: Optional[str] = None  # Alias for default_folder_id for compatibility
    
    # Additional settings from enhanced version
    default_format: GoogleDocFormat = GoogleDocFormat.HTML
    auto_create_folders: bool = True
    
    # Sync settings
    sync_interval_minutes: int = 30
    preserve_formatting: bool = True
    include_metadata: bool = True
    
    # Export settings
    export_images: bool = True
    export_tables: bool = True
    max_file_size_mb: int = 10
    
    def __post_init__(self):
        """Validate configuration and set user-specific token path."""
        # Set user-specific token path
        if not self.token_path or "google_token.json" in self.token_path:
            self.token_path = f"tokens/token_{self.user_id}.json"
        
        # Ensure token directory exists
        token_dir = Path(self.token_path).parent
        token_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure at least one folder ID is set
        if self.target_folder_id and not self.default_folder_id:
            self.default_folder_id = self.target_folder_id
        elif self.default_folder_id and not self.target_folder_id:
            self.target_folder_id = self.default_folder_id
        
        # Check for client secrets
        if not Path(self.client_secrets_path).exists():
            print(f"⚠️  Warning: Client secrets file not found at {self.client_secrets_path}")
            print("   Please download from: https://console.cloud.google.com/apis/credentials")
    
    @property
    def folder_id(self) -> Optional[str]:
        """Get the folder ID, preferring default_folder_id."""
        return self.default_folder_id or self.target_folder_id
    
    def validate_paths(self) -> None:
        """Validate configuration paths."""
        if not os.path.exists(self.client_secrets_path):
            raise FileNotFoundError(
                f"Client secrets file not found: {self.client_secrets_path}\n"
                f"Please download OAuth credentials from Google Cloud Console"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'user_id': self.user_id,
            'client_secrets_path': self.client_secrets_path,
            'token_path': self.token_path,
            'scopes': self.scopes,
            'default_folder_id': self.default_folder_id,
            'target_folder_id': self.target_folder_id,
            'default_format': self.default_format.value,
            'auto_create_folders': self.auto_create_folders,
            'sync_interval_minutes': self.sync_interval_minutes,
            'preserve_formatting': self.preserve_formatting,
            'include_metadata': self.include_metadata,
            'export_images': self.export_images,
            'export_tables': self.export_tables,
            'max_file_size_mb': self.max_file_size_mb
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GoogleDocsConfig':
        """Create config from dictionary."""
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                if key == 'default_format' and isinstance(value, str):
                    value = GoogleDocFormat(value)
                setattr(config, key, value)
        return config