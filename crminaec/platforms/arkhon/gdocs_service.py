import logging
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.json'

# THE FIX: Pull the credentials path directly from your .env file
CREDS_FILE = os.environ.get('GOOGLE_CLIENT_SECRETS', 'credentials.json') # Falls back to 'credentials.json' if env is missing

def get_google_services():
    """Authenticates using OAuth 2.0, auto-refreshes tokens, and forces re-auth if expired."""
    creds = None
    
    # 1. Load the token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    # 2. If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                # Try to silently refresh the token
                creds.refresh(Request())
            except RefreshError:
                # If the refresh token is dead, delete the file and force a new login
                print("Token expired completely. Deleting token.json and requesting new authorization...")
                os.remove(TOKEN_FILE)
                creds = None 
                
        if not creds:
            # Trigger the OAuth Consent Screen popup using the CREDS_FILE
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    # 3. Build and return the services
    drive_service = build('drive', 'v3', credentials=creds)
    docs_service = build('docs', 'v1', credentials=creds)
    
    return drive_service, docs_service

def format_table_as_string(table_data):
    """Converts the JSON array into a clean, tabbed string for Google Docs."""
    if not table_data:
        return ""
    
    # Create a formatted text block that mimics a table
    text_block = ""
    for row in table_data:
        # e.g., "T1 (Büyük Tip Lüks Villa)      145.500,00 ₺      2.328.000,00 ₺"
        mutfak = row.get("MUTFAK TİPİ", "").ljust(40) # Pads the string to align columns
        fiyat = row.get("ADET FİYATI", "").rjust(15)
        toplam = row.get("TOPLAM FİYAT", "").rjust(15)
        text_block += f"{mutfak}\t{fiyat}\t{toplam}\n"
    
    return text_block

def format_itemized_pages(typology_pages):
    """Converts the nested item arrays into a clean, readable list."""
    if not typology_pages:
        return ""
    
    text_block = ""
    for page in typology_pages:
        text_block += f"\n--- {page['typology_name']} MUTFAK ÜNİTELERİ ---\n"
        for item in page['items']:
            text_block += f"• [{item['code']}] {item['name']} - {item['qty']} {item['unit']}\n"
    
    return text_block

def generate_quote_doc(payload, template_id, target_folder_id):
    """
    Copies the master template, replaces the tags with the payload,
    and returns the URL of the generated document.
    """
    try:
        drive_service, docs_service = get_google_services()
        
        # 1. Copy the Master Template
        new_doc_title = f"Teklif_{payload['quote_number']}_{payload['customer_name']}"
        body = {
            'name': new_doc_title,
            'parents': [target_folder_id]
        }
        copied_file = drive_service.files().copy(
            fileId=template_id, body=body).execute()
        new_doc_id = copied_file.get('id')
        
        # 2. Pre-process the arrays into strings
        summary_text = format_table_as_string(payload['project_summary_table'])
        itemized_text = format_itemized_pages(payload['typology_itemized_pages'])
        
        # 3. Build the Search & Replace Requests
        requests = [
            {'replaceAllText': {'containsText': {'text': '{{quote_number}}', 'matchCase': True}, 'replaceText': payload['quote_number']}},
            {'replaceAllText': {'containsText': {'text': '{{date}}', 'matchCase': True}, 'replaceText': payload['date']}},
            {'replaceAllText': {'containsText': {'text': '{{customer_name}}', 'matchCase': True}, 'replaceText': payload['customer_name']}},
            {'replaceAllText': {'containsText': {'text': '{{project_name}}', 'matchCase': True}, 'replaceText': payload['project_name']}},
            {'replaceAllText': {'containsText': {'text': '{{total_kitchen_count}}', 'matchCase': True}, 'replaceText': str(payload['total_kitchen_count'])}},
            {'replaceAllText': {'containsText': {'text': '{{typology_list_bulleted}}', 'matchCase': True}, 'replaceText': payload['typology_list_bulleted']}},
            {'replaceAllText': {'containsText': {'text': '{{project_summary_table}}', 'matchCase': True}, 'replaceText': summary_text}},
            {'replaceAllText': {'containsText': {'text': '{{typology_itemized_pages}}', 'matchCase': True}, 'replaceText': itemized_text}},
            {'replaceAllText': {'containsText': {'text': '{{payment_terms}}', 'matchCase': True}, 'replaceText': payload['payment_terms']}},
            {'replaceAllText': {'containsText': {'text': '{{validity_date}}', 'matchCase': True}, 'replaceText': payload['validity_date']}},
        ]
        
        # 4. Execute the update against the new document
        docs_service.documents().batchUpdate(
            documentId=new_doc_id, body={'requests': requests}).execute()
        
        # 5. Return the clickable URL
        return f"https://docs.google.com/document/d/{new_doc_id}/edit"
        
    except Exception as e:
        logger.error(f"Failed to generate Google Doc: {e}")
        raise