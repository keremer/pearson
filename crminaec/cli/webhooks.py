"""
Unified webhook handler for Google Docs interoperability
Aligned with Data-First Flask-SQLAlchemy Architecture
"""
import hashlib
import hmac
import os
from typing import Any, Dict, List

from flask import jsonify, request

from crminaec.core.interop import Platform
from crminaec.core.interop.manager import InteropManager
# Import the unified database and models
from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition, NodeType


class GoogleDocsWebhookProcessor:
    def __init__(self):
        self.interop_manager = InteropManager()
        self.webhook_secret = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret-here')
    
    def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Google Docs webhook payload"""
        try:
            if 'message' in payload:
                return self._process_drive_webhook(payload)
            elif 'documentId' in payload:
                return self._process_document_update(payload)
            else:
                return {'error': 'Unsupported webhook format'}
                
        except Exception as e:
            return {'error': f'Webhook processing failed: {str(e)}'}
    
    def _process_drive_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Google Drive API push notification"""
        resource_state = payload.get('state', '')
        resource_uri = payload.get('resourceUri', '')
        
        print(f"🔔 Google Drive webhook received - State: {resource_state}")
        
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
            
            course_data = self.interop_manager.import_from_platform(
                Platform.GOOGLE_DOCS, 
                document_id
            )
            
            if not course_data:
                return {'error': 'Could not import document content'}
            
            # Use the global db.session provided by Flask-SQLAlchemy
            try:
                result = self._update_course_from_data(course_data, document_id)
                db.session.commit()
                return result
                
            except Exception as e:
                db.session.rollback()
                raise e
                
        except Exception as e:
            return {'error': f'Sync failed: {str(e)}'}
    
    def _update_course_from_data(self, course_data: Dict[str, Any], document_id: str) -> Dict[str, Any]:
        """Update course database from imported data"""
        course_title = course_data.get('title', 'Untitled Course')
        
        # Check for existing course
        course = db.session.query(Item).filter_by(name=course_title, item_type='course').first()
        
        tech_specs = {
            'instructor': "Instructor TBD",
            'contact_email': "contact@institution.edu",
            'level': "HND Art & Design",
            'language': "English",
            'delivery_mode': "Blended",
            'aim': course_data.get('aim', ''),
            'description': self._build_course_description(course_data),
            'objectives': ", ".join(course_data.get('learning_outcomes', [])),
            'learning_outcomes': course_data.get('learning_outcomes', []),
            'assessment_formats': course_data.get('assessment_formats', []),
            'tools': course_data.get('tools', [])
        }
        
        if not course:
            course = Item(
                name=course_title,
                code=self._generate_course_code(course_title),
                item_type='course',
                node_type=NodeType.ACTIVITY,
                technical_specs=tech_specs
            )
            db.session.add(course)
            db.session.flush()
            action = 'created'
        else:
            if not course.technical_specs:
                course.technical_specs = {}
            course.technical_specs.update(tech_specs)
            # Clear old lessons to replace them cleanly
            db.session.query(ItemComposition).filter_by(parent_id=course.item_id).delete()
            action = 'updated'
        
        # Add new lessons
        lessons_data = course_data.get('lessons', [])
        for i, lesson_data in enumerate(lessons_data, 1):
            lesson_tech_specs = {
                'duration': lesson_data.get('duration', 60),
                'activity_type': lesson_data.get('activity_type', 'Lecture'),
                'assignment_description': lesson_data.get('assignment', ''),
                'materials_needed': lesson_data.get('materials', ''),
                'content': lesson_data.get('content', '')
            }
            lesson = Item(
                name=lesson_data.get('title', f'Week {i}'),
                code=f"{course.code}-W{i}",
                item_type='lesson',
                node_type=NodeType.ACTIVITY,
                technical_specs=lesson_tech_specs
            )
            db.session.add(lesson)
            db.session.flush()
            
            comp = ItemComposition(parent_item=course, child_item=lesson, sort_order=i, optional_attributes={})
            db.session.add(comp)
        
        print(f"✅ Course {action}: {course.name} (ID: {course.item_id})")
        
        return {
            'status': 'success',
            'action': action,
            'course_id': course.item_id,
            'course_title': course.name,
            'document_id': document_id,
            'updates': {
                'lessons': len(lessons_data)
            }
        }
    
    def _generate_course_code(self, title: str) -> str:
        words = title.split()
        if len(words) >= 2:
            return f"{words[0][:2].upper()}{words[1][:2].upper()}01"
        return "COURSE01"
    
    def _build_course_description(self, course_data: Dict[str, Any]) -> str:
        parts = [f"Title: {course_data.get('title', 'Untitled')}"]
        if course_data.get('aim'):
            parts.append(f"Aim: {course_data['aim']}")
        if course_data.get('learning_outcomes'):
            parts.append("Learning Outcomes:")
            parts.extend([f"- {lo}" for lo in course_data['learning_outcomes']])
        return '\n'.join(parts)


def init_webhook_routes(app):
    processor = GoogleDocsWebhookProcessor()
    
    @app.route('/api/webhooks/google-docs', methods=['POST', 'GET'])
    def google_docs_webhook():
        if request.method == 'GET':
            verification_token = request.args.get('verification_token')
            if verification_token == processor.webhook_secret:
                return jsonify({'status': 'verified'})
            return jsonify({'error': 'Invalid verification token'}), 401
        
        elif request.method == 'POST':
            if not _verify_webhook_signature(request, processor.webhook_secret):
                return jsonify({'error': 'Invalid signature'}), 401
            
            payload = request.get_json()
            if not payload:
                return jsonify({'error': 'No JSON payload provided'}), 400
            
            result = processor.process_webhook(payload)
            return jsonify(result), 400 if 'error' in result else 200
    
    @app.route('/api/webhooks/test/<document_id>', methods=['POST'])
    def test_webhook_sync(document_id):
        try:
            result = processor._sync_document_to_course(document_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

def _verify_webhook_signature(request, secret: str) -> bool:
    if os.getenv('ENVIRONMENT') == 'development':
        return True
    
    signature = request.headers.get('X-Webhook-Signature')
    if signature and secret:
        expected_signature = hmac.new(
            secret.encode(), 
            request.get_data(), 
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    return True

__all__ = ['init_webhook_routes', 'GoogleDocsWebhookProcessor']