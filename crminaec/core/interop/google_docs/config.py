import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GoogleDocFormat(str, Enum):
    """Supported Google Doc formats."""
    PLAIN_TEXT = "text/plain"
    HTML = "text/html"
    MARKDOWN = "text/markdown"
    RICH_TEXT = "application/rtf"

@dataclass
class GoogleDocsConfig:
    """Configuration for Google Docs integration with user-specific tokens."""
    
    # 👤 Identity & Auth
    user_id: str = "default"
    
    # 🔑 Paths (Must be injected by the application manager)
    client_secrets_path: str = ""
    token_path: str = ""
    
    scopes: List[str] = field(default_factory=lambda: [
        'openid',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive'
    ])

    # 🏗️ AEC Project Settings (Folder IDs)
    default_folder_id: Optional[str] = None
    target_folder_id: Optional[str] = None 
    
    # ⚙️ Behavior & Format
    default_format: GoogleDocFormat = GoogleDocFormat.HTML
    auto_create_folders: bool = True
    sync_interval_minutes: int = 30
    preserve_formatting: bool = True
    include_metadata: bool = True
    
    # 📉 Export & Size
    export_images: bool = True
    export_tables: bool = True
    max_file_size_mb: int = 10

    def __post_init__(self):
        """Validate configuration and set user-specific token path."""
        # 1. Sync Folder ID Attributes
        if self.target_folder_id and not self.default_folder_id:
            self.default_folder_id = self.target_folder_id
        elif self.default_folder_id and not self.target_folder_id:
            self.target_folder_id = self.default_folder_id
            
        # 2. Validate Client Secrets Path
        if not self.client_secrets_path:
            logger.error("❌ CRITICAL: client_secrets_path was not provided to GoogleDocsConfig!")
            return
            
        secrets_file = Path(self.client_secrets_path)
        if not secrets_file.is_absolute():
            # If a relative path is passed, resolve it against the current working directory safely
            self.client_secrets_path = str(Path.cwd() / self.client_secrets_path)
            secrets_file = Path(self.client_secrets_path)

        if not secrets_file.exists():
            logger.error(f"❌ CRITICAL: Client secrets NOT FOUND at: {self.client_secrets_path}")
        else:
            logger.info(f"✅ Google Client Secrets located at: {self.client_secrets_path}")

        # 3. Setup Tokens Directory Safely
        # We place it in the current working directory (project root) by default
        token_dir = Path.cwd() / "tokens"
        token_dir.mkdir(parents=True, exist_ok=True) 
        
        # 4. Force User-Specific Token Filename
        self.token_path = str(token_dir / f"token_{self.user_id}.json")

    @property
    def folder_id(self) -> Optional[str]:
        return self.default_folder_id or self.target_folder_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in self.__dict__.items()}