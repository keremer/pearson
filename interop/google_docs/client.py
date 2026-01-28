"""
Google Docs Client with OAuth 2.0 Authentication
Implements BaseInteropClient interface
Optimized for GoogleDocsParser compatibility
"""
from __future__ import annotations

import pearson  # This automatically sets up everything

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

from pearson.interop import BaseInteropClient  # Import from parent __init__.py
from pearson.interop.google_docs.config import GoogleDocsConfig

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
        return DocumentContentExtractor.extract_plain_text(document)  # Same for now


class GoogleDocsClient(BaseInteropClient):
    """Google Docs client using OAuth 2.0 authentication"""
    
    def __init__(self, config: GoogleDocsConfig):
        self.config = config
        self.credentials: Optional[GoogleAuthCredentials] = None
        self.docs_service = None
        self.drive_service = None
        self.authenticated = False
        self.user_email: Optional[str] = None
        self.extractor = DocumentContentExtractor()
        
        # Try to authenticate on initialization
        try:
            self.authenticate()
        except Exception as e:
            logger.warning(f"Initial authentication deferred: {e}")

    def authenticate(self) -> bool:
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
            # ... rest of your service initialization ...
            return True
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def _get_user_email(self, credentials: GoogleAuthCredentials) -> Optional[str]:
        """Get the email address of the authenticated user"""
        try:
            # Use the credentials directly without type casting issues
            user_info_service = build('oauth2', 'v2', credentials=credentials, cache_discovery=False)
            user_info = user_info_service.userinfo().get().execute()
            return user_info.get('email')
        except Exception as e:
            logger.warning(f"Could not retrieve user email: {e}")
            return None
    
    def _reset_auth_state(self):
        """Reset authentication state on failure"""
        self.authenticated = False
        self.credentials = None
        self.docs_service = None
        self.drive_service = None
        self.user_email = None
    
    def _test_connection(self):
        """Test API connection safely"""
        try:
            # FIX: Check if drive_service is available and log if not
            if not self.drive_service:
                logger.warning("⚠️ Drive service not initialized for connection test")
                return
            
            results = self.drive_service.files().list(
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            
            items = results.get('files', [])
            logger.info(f"✅ Connection test passed. Found {len(items)} file(s).")
        except Exception as e:
            logger.warning(f"⚠️ Connection test warning: {e}")
    
    def _ensure_authenticated(self):
        """Ensure client is authenticated before API calls"""
        if not self.authenticated:
            if not self.authenticate():
                raise RuntimeError("Authentication required but failed")
    
    def get_content(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve content from Google Docs - implements BaseInteropClient
        
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
            self._ensure_authenticated()
            
            logger.info(f"📄 Fetching Google Doc: {source_id}")
            
            # FIX: Check if docs_service is None before using it
            if not self.docs_service:
                logger.error("❌ Google Docs service not initialized")
                return None
            
            # Get raw document from Google Docs API
            document = self.docs_service.documents().get(
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
                    'structured_text': plain_text  # Same as plain_text for now
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
            logger.debug(f"Document structure keys: {list(document.keys())}")
            
            return response
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.error(f"❌ Document not found: {source_id}")
            elif error.resp.status == 403:
                logger.error(f"❌ Permission denied: {source_id}")
                logger.info(f"💡 Tip: Make sure the document is shared with {self.user_email}")
            else:
                logger.error(f"❌ HTTP Error ({error.resp.status}): {error}")
            return None
        except Exception as e:
            logger.error(f"❌ Error retrieving document {source_id}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _get_drive_metadata(self, document_id: str) -> Dict[str, Any]:
        """Get additional metadata from Drive API"""
        try:
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.warning("Drive service not available")
                return {}
            
            file_metadata = self.drive_service.files().get(
                fileId=document_id,
                fields='id,name,createdTime,modifiedTime,owners,webViewLink,size,permissions'
            ).execute()
            
            return file_metadata
        except Exception as e:
            logger.warning(f"Could not get Drive metadata: {e}")
            return {}
    
    def update_content(self, source_id: str, content: Dict[str, Any]) -> bool:
        """
        Update content on Google Docs - implements BaseInteropClient
        
        Args:
            source_id: Google Docs document ID
            content: Dictionary containing content to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if docs_service is None before using it
            if not self.docs_service:
                logger.error("❌ Google Docs service not initialized")
                return False
            
            logger.info(f"📝 Updating Google Doc: {source_id}")
            
            # Get current document to determine length
            document = self.docs_service.documents().get(
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
                self.docs_service.documents().batchUpdate(
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
        """Get the end index of document content"""
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
        """Prepare content for insertion into Google Docs"""
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
        Create a new Google Document with optional folder placement
        
        Args:
            title: Document title
            folder_id: Optional Google Drive folder ID
            
        Returns:
            Document ID if successful, None otherwise
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return None
            
            logger.info(f"📄 Creating Google Doc: '{title}'")
            
            # Prepare file metadata
            file_metadata: Dict[str, Any] = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.document'
            }
            
            # Add parent folder if specified
            if folder_id:
                file_metadata['parents'] = [folder_id]
            elif self.config.target_folder_id:
                file_metadata['parents'] = [self.config.target_folder_id]
            
            # Create the document
            result = self.drive_service.files().create(
                body=file_metadata,
                fields='id,name,webViewLink,createdTime'
            ).execute()
            
            document_id = result.get('id')
            
            logger.info(f"✅ Created Google Doc: '{title}' (ID: {document_id})")
            logger.info(f"   🔗 View at: {result.get('webViewLink')}")
            logger.info(f"   🕒 Created: {result.get('createdTime')}")
            
            return document_id
            
        except Exception as e:
            logger.error(f"❌ Error creating document '{title}': {e}")
            return None
    
    def list_documents(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List Google Docs documents
        
        Args:
            query: Optional search query
            
        Returns:
            List of document metadata dictionaries
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return []
            
            # Build search query
            file_query = "mimeType='application/vnd.google-apps.document' and trashed=false"
            
            # Add folder filter if configured
            if self.config.target_folder_id:
                file_query += f" and '{self.config.target_folder_id}' in parents"
            
            if query:
                file_query += f" and (name contains '{query}' or fullText contains '{query}')"
            
            logger.info(f"🔍 Listing documents with query: {file_query}")
            
            # Execute query
            results = self.drive_service.files().list(
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
    
    def search_documents(self, query: str) -> List[Dict[str, Any]]:
        """
        Search documents by full text content
        
        Args:
            query: Search text
            
        Returns:
            List of matching document metadata dictionaries
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return []
            
            search_query = (
                f"mimeType='application/vnd.google-apps.document' "
                f"and trashed=false "
                f"and fullText contains '{query}'"
            )
            
            logger.info(f"🔍 Searching documents for: '{query}'")
            
            results = self.drive_service.files().list(
                q=search_query,
                pageSize=50,
                fields="files(id, name, createdTime, modifiedTime, webViewLink)"
            ).execute()
            
            documents = results.get('files', [])
            
            logger.info(f"✅ Found {len(documents)} documents matching search")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error searching documents: {e}")
            return []
    
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed document metadata
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            Dictionary with document metadata
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if docs_service is None before using it
            if not self.docs_service:
                logger.error("❌ Google Docs service not initialized")
                return None
            
            # Get Docs metadata
            docs_metadata = self.docs_service.documents().get(
                documentId=document_id
            ).execute()
            
            # Get Drive metadata
            drive_metadata = self._get_drive_metadata(document_id)
            
            # Count sections safely (handle missing/invalid body/content)
            sections = 0
            # Ensure docs_metadata is a dict and body is a dict (not None)
            body = docs_metadata.get('body') if isinstance(docs_metadata, dict) else {}
            if not isinstance(body, dict):
                body = {}
            # Safely extract content list
            content = body.get('content')
            content_list = content if isinstance(content, list) else []
            sections = sum(1 for c in content_list if isinstance(c, dict) and 'paragraph' in c)
            
            metadata = {
                'document_id': document_id,
                'title': docs_metadata.get('title', ''),
                'drive_metadata': drive_metadata,
                'document_structure': {
                    'sections': sections,
                    'last_modified': drive_metadata.get('modifiedTime'),
                    'total_elements': len(docs_metadata.get('body', {}).get('content', []))
                },
                'retrieved_at': datetime.utcnow().isoformat(),
                'authenticated_user': self.user_email
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error getting document metadata: {e}")
            return None
    
    def share_document(self, document_id: str, user_email: str, 
                      role: str = 'writer') -> bool:
        """
        Share a document with a user
        
        Args:
            document_id: Google Docs document ID
            user_email: Email address to share with
            role: Permission role (reader, writer, commenter)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return False
            
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': user_email
            }
            
            self.drive_service.permissions().create(
                fileId=document_id,
                body=permission,
                sendNotificationEmail=False
            ).execute()
            
            logger.info(f"✅ Shared document {document_id} with {user_email} as {role}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sharing document {document_id}: {e}")
            return False
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a Google Document
        
        Args:
            document_id: Google Docs document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return False
            
            self.drive_service.files().delete(fileId=document_id).execute()
            
            logger.info(f"✅ Deleted Google Doc: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting document {document_id}: {e}")
            return False
    
    def watch_document(self, document_id: str, webhook_url: str) -> Optional[Dict[str, Any]]:
        """
        Set up a webhook/watch for document changes
        
        Args:
            document_id: Google Docs document ID
            webhook_url: Webhook URL to notify on changes
            
        Returns:
            Watch configuration if successful, None otherwise
        """
        try:
            self._ensure_authenticated()
            
            # FIX: Check if drive_service is None before using it
            if not self.drive_service:
                logger.error("❌ Drive service not initialized")
                return None
            
            watch_request = {
                'id': f"watch-{document_id}-{datetime.utcnow().timestamp()}",
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True,
                'expiration': (datetime.utcnow().timestamp() + 86400 * 7) * 1000  # 7 days
            }
            
            result = self.drive_service.files().watch(
                fileId=document_id,
                body=watch_request
            ).execute()
            
            logger.info(f"✅ Set up watch for document: {document_id}")
            logger.info(f"   Webhook URL: {webhook_url}")
            logger.info(f"   Resource ID: {result.get('resourceId')}")
            logger.info(f"   Expires: {result.get('expiration')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error setting up watch for document {document_id}: {e}")
            return None
    
    def logout(self) -> bool:
        """
        Log out and delete token file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            token_path = self.config.token_path
            if token_path and os.path.exists(token_path):
                os.remove(token_path)
                logger.info(f"🗑️  Removed token file: {token_path}")
            
            self._reset_auth_state()
            logger.info("👋 Logged out successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during logout: {e}")
            return False
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated user
        
        Returns:
            User information dictionary
        """
        try:
            self._ensure_authenticated()
            
            if not self.credentials:
                return None
            
            # Cast to GoogleAuthCredentials for type safety
            auth_creds = cast(GoogleAuthCredentials, self.credentials)
            
            user_info_service = build('oauth2', 'v2', credentials=auth_creds, cache_discovery=False)
            user_info = user_info_service.userinfo().get().execute()
            
            return {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'picture': user_info.get('picture'),
                'locale': user_info.get('locale'),
                'authenticated': True
            }
        except Exception as e:
            logger.error(f"❌ Error getting user info: {e}")
            return None