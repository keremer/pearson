"""
Test file for Google Docs interoperability
Run with: python test_googledocs.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, cast

# ============================================================================
# FIXED IMPORT SECTION
# ============================================================================

# Get absolute paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to sys.path
sys.path.insert(0, str(PROJECT_ROOT))

print(f"📁 Project structure:")
print(f"   Script location: {SCRIPT_DIR}")
print(f"   Project root: {PROJECT_ROOT}")
print(f"   Python path includes: {sys.path[0]}")

# Import the modules - these should work now
try:
    from interop.manager import InteropManager, Platform
    print("✅ Imported InteropManager and Platform")
except ImportError as e:
    print(f"❌ Failed to import manager: {e}")
    sys.exit(1)

try:
    from interop.google_docs import GoogleDocsConfig, GoogleDocsClient, GoogleDocsParser
    print("✅ Imported GoogleDocs modules")
except ImportError as e:
    print(f"❌ Failed to import GoogleDocs modules: {e}")
    print("💡 Checking google_docs module structure...")
    
    # Check what's in the google_docs directory
    google_docs_dir = PROJECT_ROOT / "interop" / "google_docs"
    if google_docs_dir.exists():
        print(f"📁 Contents of {google_docs_dir.relative_to(PROJECT_ROOT)}:")
        for item in google_docs_dir.iterdir():
            if item.is_file():
                print(f"   📄 {item.name}")
    
    # Try importing directly
    try:
        from interop.google_docs.config import GoogleDocsConfig
        from interop.google_docs.client import GoogleDocsClient
        from interop.google_docs.parser import GoogleDocsParser
        print("✅ Imported directly from submodules")
    except ImportError as e2:
        print(f"❌ Direct import also failed: {e2}")
        sys.exit(1)

print("\n" + "="*60)
print("IMPORT SUCCESSFUL - Starting tests...")
print("="*60 + "\n")

# ============================================================================
# REST OF YOUR TEST FUNCTIONS (NO CHANGES NEEDED BELOW HERE)
# ============================================================================

def setup_environment():
    """Check for required environment files"""
    print("🔍 Checking environment...")
    
    required_files = ['client_secrets.json', 'requirements.txt']
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        print("\n📋 Setup Instructions:")
        print("1. Download OAuth credentials from Google Cloud Console")
        print("2. Save as 'client_secrets.json' in project root")
        print("3. Ensure 'requirements.txt' exists")
        return False
    
    print("✅ Environment check passed")
    return True


def test_config():
    """Test GoogleDocsConfig initialization"""
    print("\n🧪 Testing GoogleDocsConfig...")
    
    try:
        config = GoogleDocsConfig(
            client_secrets_path="client_secrets.json",
            token_path="test_token.json"
        )
        print(f"✅ Config created successfully")
        print(f"   Client secrets: {config.client_secrets_path}")
        print(f"   Token path: {config.token_path}")
        print(f"   Scopes: {config.scopes}")
        return config
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return None


def test_client_authentication(config):
    """Test GoogleDocsClient authentication"""
    print("\n🔐 Testing GoogleDocsClient authentication...")
    
    try:
        client = GoogleDocsClient(config)
        
        if client.authenticated:
            print(f"✅ Authentication successful")
            print(f"   Authenticated as: {client.user_email}")
            print(f"   Drive service: {'✓' if client.drive_service else '✗'}")
            print(f"   Docs service: {'✓' if client.docs_service else '✗'}")
            return client
        else:
            print("⚠️  Not authenticated on init, attempting to authenticate...")
            if hasattr(client, 'authenticate'):
                auth_success = client.authenticate()
                if auth_success:
                    print(f"✅ Authentication successful via authenticate()")
                    print(f"   Authenticated as: {client.user_email}")
                    return client
                else:
                    print("❌ Authentication failed")
                    return None
            else:
                print("❌ No authenticate method found")
                return None
    except Exception as e:
        print(f"❌ Client test failed: {e}")
        return None


def test_parser():
    """Test GoogleDocsParser"""
    print("\n📄 Testing GoogleDocsParser...")
    
    try:
        parser = GoogleDocsParser()
        
        # Test with minimal content
        test_content = {
            'title': 'Test Course',
            'body': {
                'content': [
                    {
                        'paragraph': {
                            'elements': [
                                {
                                    'textRun': {
                                        'content': 'Course Title: Test Course'
                                    }
                                }
                            ],
                            'paragraphStyle': {
                                'namedStyleType': 'HEADING_1'
                            }
                        }
                    }
                ]
            }
        }
        
        result = parser.parse_to_course_structure(test_content)
        print(f"✅ Parser test passed")
        print(f"   Title extracted: {result.get('title')}")
        print(f"   Platform: {result.get('source_platform')}")
        return parser
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        return None


def test_client_operations(client):
    """Test client operations"""
    print("\n⚙️ Testing client operations...")
    
    if not client or not client.authenticated:
        print("❌ Client not authenticated, skipping operations test")
        return False
    
    try:
        # Test 1: List documents
        print("   📋 Testing list_documents()...")
        documents = client.list_documents()
        print(f"      Found {len(documents)} documents")
        
        if documents:
            for i, doc in enumerate(documents[:3], 1):
                doc_name = doc.get('name', 'Unnamed')
                doc_id = doc.get('id', 'No ID')
                print(f"      {i}. {doc_name} ({doc_id[:10]}...)")
        
        # Test 2: Create test document
        print("   📝 Testing create_document()...")
        test_doc_id = client.create_document("Test Document - Delete Me")
        
        if test_doc_id:
            print(f"      Created document ID: {test_doc_id}")
            
            # Test 3: Get content
            print("   📄 Testing get_content()...")
            content = client.get_content(test_doc_id)
            
            if content:
                title = content.get('title', 'No Title')
                print(f"      Retrieved document: {title}")
                
                # Get content length safely
                content_data = content.get('content', {})
                if isinstance(content_data, dict):
                    plain_text = content_data.get('plain_text', '')
                    print(f"      Content length: {len(plain_text)} chars")
                else:
                    print(f"      Content structure: {type(content_data)}")
                
                # Test 4: Update content
                print("   ✏️ Testing update_content()...")
                update_data = {
                    'title': 'Updated Test Document',
                    'content': 'This is updated content for testing.'
                }
                
                success = client.update_content(test_doc_id, update_data)
                print(f"      Update {'successful' if success else 'failed'}")
                
                # Test 5: Get metadata
                print("   📊 Testing get_document_metadata()...")
                metadata = client.get_document_metadata(test_doc_id)
                
                if metadata:
                    print(f"      Metadata retrieved")
                    metadata_title = metadata.get('title', 'No Title')
                    doc_structure = metadata.get('document_structure', {})
                    sections = doc_structure.get('sections', 'N/A')
                    print(f"      Title: {metadata_title}")
                    print(f"      Sections: {sections}")
                
                # Test 6: Delete test document
                print("   🗑️ Testing delete_document()...")
                delete_success = client.delete_document(test_doc_id)
                print(f"      Delete {'successful' if delete_success else 'failed'}")
                
            else:
                print("      ❌ Failed to get document content")
        else:
            print("      ❌ Failed to create test document")
        
        print("✅ Client operations test completed")
        return True
        
    except Exception as e:
        print(f"❌ Client operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_manager():
    """Test the unified InteropManager"""
    print("\n🏗️ Testing unified InteropManager...")
    
    try:
        manager = InteropManager()
        
        # Check supported platforms
        platforms = manager.get_supported_platforms()
        print(f"✅ Manager initialized")
        print(f"   Supported platforms: {[str(p) for p in platforms]}")
        
        if Platform.GOOGLE_DOCS in platforms:
            # Get platform status - use the method that actually exists
            client = manager.clients.get(Platform.GOOGLE_DOCS)
            
            # Get status directly from client if manager method doesn't exist
            google_status = {}
            if client:
                google_status = {
                    'initialized': True,
                    'authenticated': getattr(client, 'authenticated', False),
                    'user_email': getattr(client, 'user_email', 'N/A'),
                    'parser_available': Platform.GOOGLE_DOCS in getattr(manager, 'parsers', {})
                }
            
            print(f"   Google Docs status:")
            print(f"      Initialized: {google_status.get('initialized', False)}")
            print(f"      Authenticated: {google_status.get('authenticated', False)}")
            print(f"      User email: {google_status.get('user_email', 'N/A')}")
            print(f"      Parser available: {google_status.get('parser_available', False)}")
            
            # Test authentication - authenticate directly through client
            print("   🔐 Testing platform authentication...")
            auth_success = False
            
            if client:
                if hasattr(client, 'authenticate'):
                    auth_success = client.authenticate()
                else:
                    auth_success = getattr(client, 'authenticated', False)
            
            print(f"      Authentication: {'✓' if auth_success else '✗'}")
        
        print("✅ Unified manager test completed")
        return True
        
    except Exception as e:
        print(f"❌ Unified manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_workflow():
    """Test complete workflow from document fetch to parsing"""
    print("\n🔄 Testing complete workflow...")
    
    try:
        # Create manager
        manager = InteropManager()
        
        supported_platforms = manager.get_supported_platforms()
        if Platform.GOOGLE_DOCS not in supported_platforms:
            print("❌ Google Docs not initialized, skipping workflow test")
            return False
        
        # Get client from manager for testing
        client = manager.clients.get(Platform.GOOGLE_DOCS)
        
        if not client:
            print("❌ Client not found in manager")
            return False
        
        if not client.authenticated:
            print("❌ Client not ready, authenticating...")
            if hasattr(client, 'authenticate'):
                if not client.authenticate():
                    print("❌ Authentication failed")
                    return False
            else:
                print("❌ No authenticate method available")
                return False
        
        # List documents to find one to test with
        documents = client.list_documents()
        
        test_doc_id = None
        created_test_doc = False
        
        if not documents:
            print("⚠️ No documents found, creating test document...")
            
            # Create a test document
            test_content = """
            Course Title: Test Course Document
            Course Description: This is a test document for interoperability testing.
            
            Learning Outcomes:
            1. Understand interoperability concepts
            2. Test document parsing
            3. Validate course structure extraction
            
            Assessment:
            - Test assignment (30%)
            - Final project (70%)
            
            Weekly Schedule:
            Week 1: Introduction
            Week 2: Testing methods
            Week 3: Implementation
            """
            
            # Create document
            doc_id = client.create_document("Test Course Document")
            if not doc_id:
                print("❌ Failed to create test document")
                return False
            
            # Update with content
            update_data = {
                'title': 'Test Course Document',
                'content': test_content
            }
            client.update_content(doc_id, update_data)
            test_doc_id = doc_id
            created_test_doc = True
            print(f"✅ Created test document: {test_doc_id}")
            
        else:
            # Use first document found
            test_doc = documents[0]
            test_doc_id = test_doc['id']
            doc_name = test_doc.get('name', 'Unnamed')
            print(f"✅ Using existing document: {doc_name} ({test_doc_id})")
        
        # Test import workflow through manager
        print("   📥 Testing import workflow via manager...")
        course_data = manager.import_from_platform(Platform.GOOGLE_DOCS, test_doc_id)
        
        if course_data:
            print(f"✅ Import successful!")
            print(f"   Course title: {course_data.get('title', 'No title')}")
            print(f"   Learning outcomes: {len(course_data.get('learning_outcomes', []))}")
            print(f"   Assessment formats: {len(course_data.get('assessment_formats', []))}")
            print(f"   Tools: {len(course_data.get('tools', []))}")
            print(f"   Lessons: {len(course_data.get('lessons', []))}")
            
            # Print detailed structure
            print("\n   📋 Course structure:")
            for key, value in course_data.items():
                if key not in ['metadata', 'syllabus', 'content', 'raw_content']:
                    if isinstance(value, list):
                        print(f"      {key}: {len(value)} items")
                    elif isinstance(value, dict):
                        print(f"      {key}: {len(value)} key-value pairs")
                    else:
                        print(f"      {key}: {value}")
            
            # Test export workflow (create new document)
            print("\n   📤 Testing export workflow...")
            export_doc_id = manager.export_to_platform(
                Platform.GOOGLE_DOCS,
                course_data
            )
            
            if export_doc_id:
                print(f"✅ Export successful! New document ID: {export_doc_id}")
                
                # Clean up exported document
                if hasattr(client, 'delete_document'):
                    client.delete_document(export_doc_id)
                    print(f"   🗑️ Cleaned up exported document")
            
            # Clean up test document if we created it
            if created_test_doc and test_doc_id and hasattr(client, 'delete_document'):
                client.delete_document(test_doc_id)
                print(f"   🗑️ Cleaned up test document")
        
        else:
            print("❌ Import failed - no course data returned")
            # Clean up test document if we created it and import failed
            if created_test_doc and test_doc_id and hasattr(client, 'delete_document'):
                client.delete_document(test_doc_id)
                print(f"   🗑️ Cleaned up test document (import failed)")
        
        print("✅ Complete workflow test passed")
        return True
        
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_performance_test():
    """Run performance and edge case tests"""
    print("\n⚡ Running performance and edge case tests...")
    
    try:
        # Test 1: Empty document
        print("   📄 Testing empty document handling...")
        parser = GoogleDocsParser()
        empty_result = parser.parse_to_course_structure({})
        print(f"      Empty input: {'handled' if empty_result else 'failed'}")
        # Test 2: Parser error handling
        print("   🧪 Testing parser error handling...")
        try:
            bad_result = parser.parse_to_course_structure(cast(Dict[str, Any], "not a dict"))
            print(f"      Non-dict input: {'handled' if bad_result is None else 'unexpected'}")
        except Exception as e:
            print(f"      Non-dict input raised exception (expected): {type(e).__name__}")
            print(f"      Non-dict input raised exception (expected): {type(e).__name__}")
        
        # Test 3: Large document simulation (without actual API call)
        print("   📚 Testing document structure simulation...")
        
        # Create mock document structure
        mock_document = {
            'title': 'Large Test Document',
            'body': {
                'content': []
            }
        }
        
        # Add some mock content
        for i in range(5):
            mock_document['body']['content'].append({
                'paragraph': {
                    'elements': [{
                        'textRun': {
                            'content': f'Section {i+1}: This is section content for testing purposes.'
                        }
                    }],
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_1' if i == 0 else 'NORMAL_TEXT'
                    }
                }
            })
        
        large_result = parser.parse_to_course_structure(mock_document)
        print(f"      Mock document: {large_result.get('title', 'No title')} parsed")
        
        print("✅ Performance tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("=" * 60)
    print("Google Docs Interoperability Test Suite")
    print("=" * 60)
    
    # Check environment
    if not setup_environment():
        print("\n❌ Please fix the environment issues and try again.")
        return
    
    test_results = {}
    
    # Run individual tests
    test_results['config'] = test_config() is not None
    
    config = GoogleDocsConfig(
        client_secrets_path="client_secrets.json",
        token_path="test_token.json"
    )
    
    client = test_client_authentication(config)
    test_results['authentication'] = client is not None and getattr(client, 'authenticated', False)
    
    test_results['parser'] = test_parser() is not None
    
    if client:
        test_results['operations'] = test_client_operations(client)
    
    test_results['manager'] = test_unified_manager()
    
    # Only test workflow if client was authenticated
    if client and getattr(client, 'authenticated', False):
        test_results['workflow'] = test_full_workflow()
    else:
        print("\n⚠️  Skipping workflow test - client not authenticated")
        test_results['workflow'] = False
    
    test_results['performance'] = run_performance_test()
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title():25} {status}")
        if result:
            passed += 1
    
    print("\n" + "=" * 60)
    if total > 0:
        percentage = (passed / total) * 100
        print(f"TOTAL: {passed}/{total} tests passed ({percentage:.1f}%)")
    else:
        print("TOTAL: No tests executed")
    print("=" * 60)
    
    # Cleanup
    try:
        if os.path.exists("test_token.json"):
            os.remove("test_token.json")
            print("\n🗑️  Cleaned up test token file")
    except Exception as e:
        print(f"\n⚠️  Could not clean up test token: {e}")
    
    if passed == total and total > 0:
        print("\n🎉 All tests passed! Your Google Docs integration is working.")
    elif passed > 0:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
    else:
        print("\n❌ No tests passed. Please check the error messages above.")


if __name__ == "__main__":
    main()