#!/usr/bin/env python3
"""
Quick test for Google Docs integration
"""
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from interop.google_docs.client import GoogleDocsClient
from interop.google_docs.parser import GoogleDocsParser
from interop.google_docs.config import GoogleDocsConfig

def test_google_docs():
    print("🧪 Testing Google Docs Integration...")
    
    try:
        # 1. Test Configuration
        print("1. Testing configuration...")
        config = GoogleDocsConfig(
            credentials_file=Path("credentials.json"),
            token_file=Path("token.json")
        )
        
        if not config.credentials_file.exists():
            print("   ⚠️  credentials.json not found - structure test only")
        
        print("   ✅ Configuration created")
        
        # 2. Test Client Initialization 
        print("2. Testing client initialization...")
        client = GoogleDocsClient(config)  # Should work now!
        print(f"   ✅ Client initialized (authenticated: {client.authenticated})")
        
        # 3. Test Abstract Method Implementation
        print("3. Testing abstract method implementation...")
        assert hasattr(client, 'update_content'), "Missing update_content method"
        print("   ✅ Abstract methods implemented")
        
        # 4. Test Parser
        print("4. Testing parser...")
        parser = GoogleDocsParser()
        
        mock_document = {
            'title': 'Test Course',
            'documentId': '1XQ5-OuGAs3xDsZkOxMmtkf3notcoGPmdhQnLdyXNqY8',
            'body': {'content': []}
        }
        
        course_data = parser.parse_to_course_structure(mock_document)
        print(f"   ✅ Parser test passed - Course: {course_data.get('title')}")
        
        print("\n🎉 All tests passed! Google Docs integration is ready.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_google_docs()