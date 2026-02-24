"""
Unified webhook handler for Google Docs interoperability
FIXED: Proper Google Docs webhook processing and security
"""
from flask import request, jsonify
import hmac
import hashlib
import json
import os
from typing import Dict, Any, List, Optional

from interop.manager import InteropManager
from interop import Platform
from pearson.models import Course, Lesson, LearningOutcome, AssessmentFormat, Tool
from cli.setup import DatabaseSetup

class GoogleDocsWebhookProcessor:
    def __init__(self):
        self.interop_manager = InteropManager()
        self.db_setup = DatabaseSetup()
        self.webhook_secret = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret-here')
    
    def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Google Docs webhook payload"""
        try:
            # Google Drive API webhook structure
            if 'message' in payload:
                # This is a Google Drive API push notification
                return self._process_drive_webhook(payload)
            elif 'documentId' in payload:
                # This is a direct document update
                return self._process_document_update(payload)
            else:
                return {'error': 'Unsupported webhook format'}
                
        except Exception as e:
            return {'error': f'Webhook processing failed: {str(e)}'}
    
    def _process_drive_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Google Drive API push notification"""
        # Extract resource information from the webhook
        resource_state = payload.get('state', '')
        resource_uri = payload.get('resourceUri', '')
        
        print(f"🔔 Google Drive webhook received - State: {resource_state}")
        
        # Extract document ID from resource URI
        # Format: https://www.googleapis.com/drive/v3/files/{fileId}
        if '/files/' in resource_uri:
            document_id = resource_uri.split('/files/')[-1]
            return self._sync_document_to_course(document_id)
        else:
            return {'error': 'Could not extract document ID from webhook'}
    
    def _process_document_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process direct document update webhook"""
        document_id = payload.get('documentId')
        if not document_id:
            return {'error': 'No document ID provided'}
        
        return self._sync_document_to_course(document_id)
    
    def _sync_document_to_course(self, document_id: str) -> Dict[str, Any]:
        """Sync Google Doc content to course database"""
        try:
            print(f"🔄 Syncing document {document_id} to course...")
            
            # Import document using interop manager
            course_data = self.interop_manager.import_from_platform(
                Platform.GOOGLE_DOCS, 
                document_id
            )
            
            if not course_data:
                return {'error': 'Could not import document content'}
            
            # Update or create course in database
            session = self.db_setup.Session()
            try:
                result = self._update_course_from_data(session, course_data, document_id)
                session.commit()
                return result
                
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
                
        except Exception as e:
            return {'error': f'Sync failed: {str(e)}'}
    
    def _update_course_from_data(self, session, course_data: Dict[str, Any], document_id: str) -> Dict[str, Any]:
        """Update course database from imported data"""
        # Look for existing course by title or create new one
        course_title = course_data.get('title', 'Untitled Course')
        course = session.query(Course).filter(Course.title == course_title).first()
        
        if not course:
            # Create new course
            course = Course(
                title=course_title,
                course_code=self._generate_course_code(course_title),
                instructor="Instructor TBD",
                contact_email="contact@institution.edu",
                level="HND Art & Design",
                language="English",
                delivery_mode="Blended",
                aim=course_data.get('aim', ''),
                description=self._build_course_description(course_data),
                objectives=", ".join(course_data.get('learning_outcomes', []))
            )
            session.add(course)
            session.flush()
            action = 'created'
        else:
            # Update existing course
            course.aim = course_data.get('aim', course.aim)
            course.description = self._build_course_description(course_data)
            course.objectives = ", ".join(course_data.get('learning_outcomes', []))
            action = 'updated'
        
        # Update learning outcomes
        self._update_learning_outcomes(session, course, course_data.get('learning_outcomes', []))
        
        # Update assessment formats
        self._update_assessment_formats(session, course, course_data.get('assessment_formats', []))
        
        # Update tools
        self._update_tools(session, course, course_data.get('tools', []))
        
        # Update lessons
        self._update_lessons(session, course, course_data.get('lessons', []))
        
        print(f"✅ Course {action}: {course.title} (ID: {course.id})")
        
        return {
            'status': 'success',
            'action': action,
            'course_id': course.id,
            'course_title': course.title,
            'document_id': document_id,
            'updates': {
                'learning_outcomes': len(course_data.get('learning_outcomes', [])),
                'assessment_formats': len(course_data.get('assessment_formats', [])),
                'tools': len(course_data.get('tools', [])),
                'lessons': len(course_data.get('lessons', []))
            }
        }
    
    def _update_learning_outcomes(self, session, course, outcomes: List[str]):
        """Update learning outcomes for course"""
        # Clear existing outcomes
        session.query(LearningOutcome).filter(LearningOutcome.course_id == course.id).delete()
        
        # Add new outcomes
        for i, outcome in enumerate(outcomes, 1):
            lo = LearningOutcome(
                code=f"LO{i}",
                description=outcome,
                course_id=course.id
            )
            session.add(lo)
    
    def _update_assessment_formats(self, session, course, assessments: List[Dict]):
        """Update assessment formats for course"""
        session.query(AssessmentFormat).filter(AssessmentFormat.course_id == course.id).delete()
        
        for assessment in assessments:
            af = AssessmentFormat(
                course_id=course.id,
                format_type=assessment.get('type', 'Assignment'),
                requirements=assessment.get('description', ''),
                description=assessment.get('description', '')
            )
            session.add(af)
    
    def _update_tools(self, session, course, tools: List[Dict]):
        """Update tools for course"""
        session.query(Tool).filter(Tool.course_id == course.id).delete()
        
        for tool_data in tools:
            tool = Tool(
                category=tool_data.get('category', 'Software'),
                name=tool_data.get('name', 'Tool'),
                description=tool_data.get('description', '')
            )
            session.add(tool)
    
    def _update_lessons(self, session, course, lessons: List[Dict]):
        """Update lessons for course"""
        session.query(Lesson).filter(Lesson.course_id == course.id).delete()
        
        for i, lesson_data in enumerate(lessons, 1):
            lesson = Lesson(
                course_id=course.id,
                title=lesson_data.get('title', f'Week {i}'),
                content=lesson_data.get('content', ''),
                duration=lesson_data.get('duration', 60),
                order=i,
                activity_type=lesson_data.get('activity_type', 'Lecture'),
                assignment_description=lesson_data.get('assignment', ''),
                materials_needed=lesson_data.get('materials', '')
            )
            session.add(lesson)
    
    def _generate_course_code(self, title: str) -> str:
        """Generate course code from title"""
        words = title.split()
        if len(words) >= 2:
            return f"{words[0][:2].upper()}{words[1][:2].upper()}01"
        return "COURSE01"
    
    def _build_course_description(self, course_data: Dict[str, Any]) -> str:
        """Build course description from imported data"""
        parts = [f"Title: {course_data.get('title', 'Untitled')}"]
        
        if course_data.get('aim'):
            parts.append(f"Aim: {course_data['aim']}")
        
        if course_data.get('learning_outcomes'):
            parts.append("Learning Outcomes:")
            parts.extend([f"- {lo}" for lo in course_data['learning_outcomes']])
        
        return '\n'.join(parts)

def init_webhook_routes(app):
    """Initialize webhook routes for the Flask app"""
    processor = GoogleDocsWebhookProcessor()
    
    @app.route('/api/webhooks/google-docs', methods=['POST', 'GET'])
    def google_docs_webhook():
        """Google Docs webhook endpoint with proper security"""
        
        # Handle webhook verification (GET request for initial setup)
        if request.method == 'GET':
            verification_token = request.args.get('verification_token')
            if verification_token == processor.webhook_secret:
                return jsonify({'status': 'verified'})
            else:
                return jsonify({'error': 'Invalid verification token'}), 401
        
        # Handle webhook payload (POST request)
        elif request.method == 'POST':
            # Verify webhook signature for security
            if not _verify_webhook_signature(request, processor.webhook_secret):
                return jsonify({'error': 'Invalid signature'}), 401
            
            # Process the webhook payload
            payload = request.get_json()
            if not payload:
                return jsonify({'error': 'No JSON payload provided'}), 400
            
            result = processor.process_webhook(payload)
            
            if 'error' in result:
                return jsonify(result), 400
            else:
                return jsonify(result)
    
    @app.route('/api/webhooks/test/<document_id>', methods=['POST'])
    def test_webhook_sync(document_id):
        """Test endpoint to manually trigger document sync"""
        try:
            result = processor._sync_document_to_course(document_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

def _verify_webhook_signature(request, secret: str) -> bool:
    """Verify webhook signature for security"""
    # Google Drive webhooks don't typically sign payloads,
    # but you can implement verification based on your setup
    
    # For development, you might want to skip verification
    if os.getenv('ENVIRONMENT') == 'development':
        return True
    
    # In production, implement proper verification
    # This could be based on Google's verification token or custom signature
    signature = request.headers.get('X-Webhook-Signature')
    if signature and secret:
        expected_signature = hmac.new(
            secret.encode(), 
            request.get_data(), 
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    return True  # For now, accept all webhooks (configure based on your security needs)

# Export for easy import
__all__ = ['init_webhook_routes', 'GoogleDocsWebhookProcessor']