"""
Google Docs Configuration with user-specific tokens and 2026 Digital Compliance Scopes.
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
    
    # 👤 Identity & Auth
    user_id: str = "default"
    
    # 🔑 2026 Scopes: Unified for Documents, Drive, and Identity
    # 📂 Paths: Initial defaults (resolved in __post_init__)
    client_secrets_path: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRETS",""))
    token_path: str = "tokens/google_token.json"
    
    scopes: List[str] = field(default_factory=lambda: [
        'openid',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.file'
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
        # 🏗️ Define Project Root (C:\inGitHub\pythonapps\crminaec)
        # We go up 4 levels from crminaec/interop/google_docs/config.py
        root = Path(__file__).parent.parent.parent.parent
        
        # 1. Resolve Client Secrets (Outside Project Folder)
        # If the path in .env starts with 'C:', we use it as is.
        # Otherwise, we assume it's relative to root.
        if not os.path.isabs(self.client_secrets_path):
            self.client_secrets_path = str(root / self.client_secrets_path)
        
        # 2. Setup Tokens Directory (Local to Project Root)
        # Path: C:\inGitHub\pythonapps\crminaec\tokens\
        token_dir = root / "tokens"
        token_dir.mkdir(parents=True, exist_ok=True) 
        
        # 3. Force User-Specific Token Filename
        # Result: C:\inGitHub\pythonapps\crminaec\tokens\token_default.json
        self.token_path = str(token_dir / f"token_{self.user_id}.json")
        
        # 4. Sync Folder ID Attributes
        if self.target_folder_id and not self.default_folder_id:
            self.default_folder_id = self.target_folder_id
        elif self.default_folder_id and not self.target_folder_id:
            self.target_folder_id = self.default_folder_id
        
        # 5. Final Validation Check
        secrets_file = Path(self.client_secrets_path)
        if not secrets_file.exists():
            print(f"❌ CRITICAL: Client secrets NOT FOUND at: {self.client_secrets_path}")
            print(f"💡 Check your .env: GOOGLE_CLIENT_SECRETS should be the full C:\\ path.")
        else:
            print(f"✅ Google Client Secrets located at: {self.client_secrets_path}")

    @property
    def folder_id(self) -> Optional[str]:
        return self.default_folder_id or self.target_folder_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in self.__dict__.items()}