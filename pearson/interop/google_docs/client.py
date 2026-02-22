# pearson/interop/google_docs/client.py (fixed)
"""
Google Docs Client with OAuth 2.0 Authentication
Implements BaseInteropClient interface
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast
from pathlib import Path

from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.external_account_authorized_user import Credentials as ExternalAccountCredentials
from google.auth.credentials import Credentials as GoogleAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .. import BaseInteropClient
from .config import GoogleDocsConfig

logger = logging.getLogger(__name__)


class DocumentContentExtractor:
    """Embedded content extractor for Google Docs"""
    
    @staticmethod
    def extract_plain_text(document: Dict[str, Any]) -> str:
        """Extract plain text from document structure - for metadata only"""
        text_parts = []
        
        if 'body' in document and 'content' in document['body']:
            for element in document['body']['content']:
                if 'paragraph' in element:
                    paragraph_text = []
                    for elem in element['paragraph']['elements']:
                        if 'textRun' in elem:
                            paragraph_text.append(elem['textRun']['content'])
                    
                    if paragraph_text:
                        text_parts.append(''.join(paragraph_text).strip())
        
        return '\n'.join(text_parts)
    
    @staticmethod
    def extract_structured_text(document: Dict[str, Any]) -> str:
        """Extract structured text with paragraph markers"""
        return DocumentContentExtractor.extract_plain_text(document)


class GoogleDocsClient(BaseInteropClient):
    """Google Docs client using OAuth 2.0 authentication"""
    
    def __init__(self, config: GoogleDocsConfig):
        self.config = config
        self.credentials: Optional[GoogleAuthCredentials] = None
        self.docs_service: Optional[Any] = None
        self.drive_service: Optional[Any] = None
        self.authenticated = False
        self.user_email: Optional[str] = None
        self.extractor = DocumentContentExtractor()
        
        # Try to authenticate on initialization
        try:
            self.authenticate()
        except Exception as e:
            logger.warning(f"Initial authentication deferred: {e}")

    def authenticate(self) -> bool:
        """Authenticate with Google API using OAuth 2.0."""
        try:
            creds = None
            # Ensure the tokens directory exists
            os.makedirs(os.path.dirname(self.config.token_path), exist_ok=True)
            if os.path.exists(self.config.token_path):
                creds = OAuthCredentials.from_authorized_user_file(
                    self.config.token_path, self.config.scopes
                )

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.config.client_secrets_path, self.config.scopes
                    )
                    # CRITICAL: prompt='select_account' forces the UI to let you pick the right email
                    creds = flow.run_local_server(port=0, prompt='select_account')

                with open(self.config.token_path, 'w') as token:
                    token.write(creds.to_json())

            self.credentials = creds
            self.authenticated = True
            
            # Build services
            self.docs_service = build('docs', 'v1', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            # Get user email
            self.user_email = self._get_user_email(creds)
            
            logger.info(f"✅ Authenticated as: {self.user_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            self._reset_auth_state()
            return False
    
    def _get_user_email(self, credentials: GoogleAuthCredentials) -> Optional[str]:
        """Get the email address of the authenticated user."""
        try:
            user_info_service = build('oauth2', 'v2', credentials=credentials, cache_discovery=False)
            user_info = user_info_service.userinfo().get().execute()
            return user_info.get('email')
        except Exception as e:
            logger.warning(f"Could not retrieve user email: {e}")
            return None
    
    def _reset_auth_state(self) -> None:
        """Reset authentication state on failure."""
        self.authenticated = False
        self.credentials = None
        self.docs_service = None
        self.drive_service = None
        self.user_email = None
    
    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated before API calls."""
        if not self.authenticated:
            if not self.authenticate():
                raise RuntimeError("Authentication required but failed")
    
    def _ensure_docs_service(self) -> None:
        """Ensure docs service is available."""
        self._ensure_authenticated()
        if self.docs_service is None:
            raise RuntimeError("Google Docs service not initialized")
    
    def _ensure_drive_service(self) -> None:
        """Ensure drive service is available."""
        self._ensure_authenticated()
        if self.drive_service is None:
            raise RuntimeError("Google Drive service not initialized")
    
    def get_content(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve content from Google Docs.
        
        Returns format optimized for GoogleDocsParser:
        - Raw Google Docs API response
        - Enhanced with metadata
        - Compatible with parser's _extract_content_and_metadata method
        
        Args:
            source_id: Google Docs document ID
            
        Returns:
            Dictionary containing raw document and metadata
        """
        try:
            self._ensure_docs_service()
            
            logger.info(f"📄 Fetching Google Doc: {source_id}")
            
            # Get raw document from Google Docs API
            document = self.docs_service.documents().get(  # type: ignore
                documentId=source_id
            ).execute()
            
            # Get additional metadata from Drive API
            drive_metadata = self._get_drive_metadata(source_id)
            
            # Extract plain text for convenience and metadata
            plain_text = self.extractor.extract_plain_text(document)
            
            # Get title from document
            title = document.get('title', 'Untitled Document')
            
            # Create the response in parser-optimized format
            # This matches what GoogleDocsParser._extract_content_and_metadata expects
            response = {
                # Format 1: Parser expects 'content' with 'raw' key
                'content': {
                    'raw': document,  # Raw Google Docs API response
                    'plain_text': plain_text,
                    'structured_text': plain_text
                },
                
                # Format 2: Direct access fields for parser
                'id': source_id,
                'title': title,
                
                # Enhanced metadata
                'metadata': {
                    'platform': 'google_docs',
                    'document_id': source_id,
                    'title': title,
                    'created_time': drive_metadata.get('createdTime'),
                    'modified_time': drive_metadata.get('modifiedTime'),
                    'web_view_link': drive_metadata.get('webViewLink'),
                    'retrieved_at': datetime.utcnow().isoformat(),
                    'authenticated_user': self.user_email,
                    'file_size': drive_metadata.get('size'),
                    'owners': drive_metadata.get('owners', [])
                },
                
                # Format 3: Also include raw document at root for backward compatibility
                'body': document.get('body', {}),
                'documentId': source_id,
                'modifiedTime': drive_metadata.get('modifiedTime'),
                
                # Format 4: Raw document accessible directly
                '_raw_document': document
            }
            
            # Add raw document fields for direct parser access
            for key in ['title', 'documentId', 'body']:
                if key in document and key not in response:
                    response[key] = document[key]
            
            logger.info(f"✅ Retrieved: '{title}' ({len(plain_text)} characters)")
            
            return response
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.error(f"❌ Document not found: {source_id}")
            elif error.resp.status == 403:
                logger.error(f"❌ Permission denied: {source_id}")
                if self.user_email:
                    logger.info(f"💡 Tip: Make sure the document is shared with {self.user_email}")
            else:
                logger.error(f"❌ HTTP Error ({error.resp.status}): {error}")
            return None
        except Exception as e:
            logger.error(f"❌ Error retrieving document {source_id}: {e}")
            return None
    
    def _get_drive_metadata(self, document_id: str) -> Dict[str, Any]:
        """Get additional metadata from Drive API."""
        try:
            self._ensure_drive_service()
            
            file_metadata = self.drive_service.files().get(  # type: ignore
                fileId=document_id,
                fields='id,name,createdTime,modifiedTime,owners,webViewLink,size,permissions'
            ).execute()
            
            return file_metadata
        except Exception as e:
            logger.warning(f"Could not get Drive metadata: {e}")
            return {}
    
    def update_content(self, source_id: str, content: Dict[str, Any]) -> bool:
        """
        Update content on Google Docs.
        
        Args:
            source_id: Google Docs document ID
            content: Dictionary containing content to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._ensure_docs_service()
            
            logger.info(f"📝 Updating Google Doc: {source_id}")
            
            # Get current document to determine length
            document = self.docs_service.documents().get(  # type: ignore
                documentId=source_id
            ).execute()
            
            # Prepare update requests
            requests = []
            
            # Clear existing content
            end_index = self._get_document_end_index(document)
            if end_index > 2:  # Document has content beyond initial newline
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': end_index - 1
                        }
                    }
                })
            
            # Add new content
            text_to_insert = self._prepare_content_for_update(content)
            if text_to_insert:
                requests.append({
                    'insertText': {
                        'location': {'index': 1},
                        'text': text_to_insert
                    }
                })
            
            # Execute batch update
            if requests:
                self.docs_service.documents().batchUpdate(  # type: ignore
                    documentId=source_id,
                    body={'requests': requests}
                ).execute()
            
            logger.info(f"✅ Updated Google Doc: {source_id}")
            return True
            
        except HttpError as error:
            logger.error(f"❌ HTTP Error updating document: {error}")
            return False
        except Exception as e:
            logger.error(f"❌ Error updating document {source_id}: {e}")
            return False
    
    def _get_document_end_index(self, document: Dict[str, Any]) -> int:
        """Get the end index of document content."""
        try:
            end_index = 1
            if 'body' in document and 'content' in document['body']:
                for element in document['body']['content']:
                    if 'endIndex' in element:
                        end_index = max(end_index, element['endIndex'])
            return end_index
        except Exception:
            return 1
    
    def _prepare_content_for_update(self, content: Dict[str, Any]) -> str:
        """Prepare content for insertion into Google Docs."""
        text_parts = []
        
        # Add title if present
        if 'title' in content:
            text_parts.append(f"# {content['title']}\n\n")
        
        # Add content based on structure
        if 'content' in content:
            if isinstance(content['content'], str):
                text_parts.append(content['content'])
            elif isinstance(content['content'], dict):
                # Try to get text from structured content
                text = content['content'].get('plain_text') or content['content'].get('text')
                if text:
                    text_parts.append(text)
            else:
                text_parts.append(str(content['content']))
        
        # Add structured sections if present
        if 'sections' in content and isinstance(content['sections'], dict):
            for section_name, section_content in content['sections'].items():
                text_parts.append(f"\n## {section_name}\n")
                if isinstance(section_content, list):
                    for item in section_content:
                        text_parts.append(f"- {item}\n")
                else:
                    text_parts.append(f"{section_content}\n")
        
        return '\n'.join(text_parts)
    
    def create_document(self, title: str, folder_id: Optional[str] = None) -> Optional[str]:
        """
        Create a new Google Document with optional folder placement.
        
        Args:
            title: Document title
            folder_id: Optional Google Drive folder ID
            
        Returns:
            Document ID if successful, None otherwise
        """
        try:
            self._ensure_drive_service()
            
            logger.info(f"📄 Creating Google Doc: '{title}'")
            
            # Prepare file metadata
            file_metadata: Dict[str, Any] = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.document'
            }
            
            # Add parent folder if specified
            if folder_id:
                file_metadata['parents'] = [folder_id]
            elif hasattr(self.config, 'default_folder_id') and self.config.default_folder_id:
                file_metadata['parents'] = [self.config.default_folder_id]
            elif hasattr(self.config, 'target_folder_id') and self.config.target_folder_id:
                file_metadata['parents'] = [self.config.target_folder_id]
            
            # Create the document
            result = self.drive_service.files().create(  # type: ignore
                body=file_metadata,
                fields='id,name,webViewLink,createdTime'
            ).execute()
            
            document_id = result.get('id')
            
            logger.info(f"✅ Created Google Doc: '{title}' (ID: {document_id})")
            return document_id
            
        except Exception as e:
            logger.error(f"❌ Error creating document '{title}': {e}")
            return None
    
    def list_documents(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List Google Docs documents.
        
        Args:
            query: Optional search query
            
        Returns:
            List of document metadata dictionaries
        """
        try:
            self._ensure_drive_service()
            
            # Build search query
            file_query = "mimeType='application/vnd.google-apps.document' and trashed=false"
            
            # Add folder filter if configured
            default_folder_id = None
            if hasattr(self.config, 'default_folder_id'):
                default_folder_id = self.config.default_folder_id
            elif hasattr(self.config, 'target_folder_id'):
                default_folder_id = self.config.target_folder_id
            
            if default_folder_id:
                file_query += f" and '{default_folder_id}' in parents"
            
            if query:
                file_query += f" and (name contains '{query}' or fullText contains '{query}')"
            
            logger.info(f"🔍 Listing documents with query: {file_query}")
            
            # Execute query
            results = self.drive_service.files().list(  # type: ignore
                q=file_query,
                pageSize=100,
                fields="files(id, name, createdTime, modifiedTime, webViewLink, size, owners, parents)",
                orderBy="modifiedTime desc"
            ).execute()
            
            documents = results.get('files', [])
            
            logger.info(f"✅ Found {len(documents)} Google Docs")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error listing documents: {e}")
            return []