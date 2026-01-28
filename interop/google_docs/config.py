"""
Google Docs Configuration
"""
import pearson  # This automatically sets up everything
import json
import os
from pathlib import Path
from typing import List, Optional

class GoogleDocsConfig:
    """Configuration for Google Docs OAuth 2.0"""
    
    def __init__(self, 
                 client_secrets_path: str = "client_secrets.json",
                 user_id: str = "default",  # New: differentiate users
                 target_folder_id: Optional[str] = None,
                 scopes: Optional[List[str]] = None):
        
        self.client_secrets_path = client_secrets_path
        # Store tokens in a dedicated directory to avoid clutter
        self.token_path = f"tokens/token_{user_id}.json" 
        self.target_folder_id = target_folder_id
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
        self._validate_paths()
    
    def _validate_paths(self) -> None:
        """Validate configuration paths"""
        if not os.path.exists(self.client_secrets_path):
            raise FileNotFoundError(
                f"Client secrets file not found: {self.client_secrets_path}\n"
                f"Please download OAuth credentials from Google Cloud Console"
            )