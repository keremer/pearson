"""
Optimized Test Suite for Google Docs Interoperability
Focus: Multi-account support and personal quota management
"""
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any

from pearson.interop.manager import InteropManager, Platform
from pearson.interop.google_docs import GoogleDocsConfig, GoogleDocsClient

def test_full_workflow(user_email: str):
    print(f"\n🚀 Starting Workflow Test for: {user_email}")
    print("=" * 60)

    # 1. Setup Config with specific user identity
    # Using a user-specific token prevents account collisions
    config = GoogleDocsConfig(
        client_secrets_path="client_secrets.json",
    )
    # store per-user token path on the config object (attribute set dynamically)
    config.token_path = f"tokens/token_{user_email.split('@')[0]}.json"

    # 2. Initialize Client
    client = GoogleDocsClient(config)
    
    # Force fresh authentication if not targeting the right account
    if client.authenticated and client.user_email != user_email:
        print(f"🔄 Switching accounts from {client.user_email} to {user_email}...")
        client.logout()
        client.authenticate()

    if not client.authenticated:
        print("❌ Authentication failed. Cannot proceed.")
        return

    try:
        # 3. Create Test Doc
        doc_name = f"Pearson Test - {int(time.time())}"
        print(f"📝 Creating: {doc_name}")
        doc_id = client.create_document(doc_name)
        
        # Personal Account Quota Tip: Wait for Drive indexing
        time.sleep(2) 

        # Validate doc_id to satisfy type checker (create_document may return Optional[str])
        if doc_id is None:
            print("❌ Failed to create document; received no doc_id. Aborting workflow.")
            return

        # 4. Update with Course Content
        course_payload = {
            "title": doc_name,
            "content": "Learning Outcomes:\n1. Master Python API\n2. Solve Quota Limits"
        }
        client.update_content(doc_id, course_payload)
        print(f"✅ Document {doc_id} created and updated.")

        # 5. Test Manager Import
        manager = InteropManager()
        # Overwrite manager's default client with our authenticated one
        manager.clients[Platform.GOOGLE_DOCS] = client 
        
        print("📥 Testing Manager Import...")
        parsed_data = manager.import_from_platform(Platform.GOOGLE_DOCS, doc_id)
        
        if parsed_data and parsed_data.get('title'):
            print(f"🎉 Success! Parsed Title: {parsed_data['title']}")
        else:
            print("⚠️ Parsed data was empty or invalid.")

        # 6. Cleanup
        print("🗑️ Deleting test document...")
        client.delete_document(doc_id)
        print("✅ Cleanup complete.")

    except Exception as e:
        print(f"❌ Workflow Error: {e}")

if __name__ == "__main__":
    target_account = "doarch@gmail.com"
        
    test_full_workflow(target_account)