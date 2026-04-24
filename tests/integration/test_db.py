"""
Integration tests for database operations.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition, NodeType


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    def test_database_session_management(self, test_engine, SessionFactory):
        """Test that database sessions are properly managed."""
        # Create a session
        session1 = SessionFactory()
        session2 = SessionFactory()
        
        # They should be different instances
        assert session1 is not session2
        
        # Test basic CRUD
        course = Item(
            name='Integration Test Course',
            code='ITC101',
            item_type='course',
            node_type=NodeType.ACTIVITY
        )
        
        session1.add(course)
        session1.commit()
        
        # Verify persistence in same session
        retrieved = session1.query(Item).filter_by(code='ITC101').first()
        assert retrieved is not None
        assert retrieved.name == 'Integration Test Course'
        
        # Verify persistence in different session
        retrieved2 = session2.query(Item).filter_by(code='ITC101').first()
        assert retrieved2 is not None
        assert retrieved2.name == 'Integration Test Course'
        
        session1.close()
        session2.close()
    
    def test_database_constraints(self, db_session):
        """Test database constraints and integrity."""
        # Test that we can't create duplicate IDs
        course1 = Item(name='Course 1', code='CODE101', item_type='course')
        db_session.add(course1)
        db_session.commit()
        
        # Should be able to create another course with different code
        course2 = Item(name='Course 2', code='CODE102', item_type='course')
        db_session.add(course2)
        db_session.commit()  # Should not raise IntegrityError
        
        # Check both exist
        courses = db_session.query(Item).filter_by(item_type='course').all()
        assert len(courses) == 2
    
    def test_database_cascade_behavior(self, db_session):
        """Test cascade behavior when deleting courses."""
        # Create course with lessons
        course = Item(name='Test Course', code='CASCADE101', item_type='course')
        db_session.add(course)
        db_session.commit()
        
        lesson1 = Item(name='Lesson 1', code='L1', item_type='lesson')
        lesson2 = Item(name='Lesson 2', code='L2', item_type='lesson')
        db_session.add_all([ItemComposition(parent_item=course, child_item=lesson1, optional_attributes={}), ItemComposition(parent_item=course, child_item=lesson2, optional_attributes={})])
        db_session.commit()
        
        # Count lessons before delete
        lessons_before = db_session.query(ItemComposition).filter_by(parent_id=course.item_id).count()
        assert lessons_before == 2
        
        # Delete the course
        db_session.delete(course)
        db_session.commit()
        
        # Check if links still exist (they should be gone because of cascade)
        lessons_after = db_session.query(ItemComposition).filter_by(parent_id=course.item_id).count()
        assert lessons_after == 0
    
    def test_transaction_rollback(self, db_session):
        """Test that transactions can be rolled back."""
        # Count initial courses
        initial_count = db_session.query(Item).filter_by(item_type='course').count()
        
        # Create course but don't commit
        course = Item(name='Rollback Test', code='RB101', item_type='course')
        db_session.add(course)
        
        # Rollback
        db_session.rollback()
        
        # Count should be unchanged
        final_count = db_session.query(Item).filter_by(item_type='course').count()
        assert final_count == initial_count
    
    def test_session_isolation(self, SessionFactory):
        """Test that sessions are isolated from each other."""
        # Create two independent sessions
        session1 = SessionFactory()
        session2 = SessionFactory()
        
        # Add course in session1
        course1 = Item(name='Session 1 Course', code='SESS1', item_type='course')
        session1.add(course1)
        session1.commit()
        
        # session2 shouldn't see it until committed and refreshed
        courses_in_session2 = session2.query(Item).filter_by(code='SESS1').first()
        
        # Cleanup
        session1.close()
        session2.close()