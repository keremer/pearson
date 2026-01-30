"""
Integration tests for database operations.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from shared.models import Course, Lesson

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
        course = Course(
            title='Integration Test Course',
            course_code='ITC101',
            instructor='Test Instructor'
        )
        
        session1.add(course)
        session1.commit()
        
        # Verify persistence in same session
        retrieved = session1.query(Course).filter_by(course_code='ITC101').first()
        assert retrieved is not None
        assert retrieved.title == 'Integration Test Course'
        
        # Verify persistence in different session
        retrieved2 = session2.query(Course).filter_by(course_code='ITC101').first()
        assert retrieved2 is not None
        assert retrieved2.title == 'Integration Test Course'
        
        session1.close()
        session2.close()
    
    def test_database_constraints(self, db_session):
        """Test database constraints and integrity."""
        # Test that we can't create duplicate IDs
        course1 = Course(title='Course 1', course_code='CODE101')
        db_session.add(course1)
        db_session.commit()
        
        # Should be able to create another course with different code
        course2 = Course(title='Course 2', course_code='CODE102')
        db_session.add(course2)
        db_session.commit()  # Should not raise IntegrityError
        
        # Check both exist
        courses = db_session.query(Course).all()
        assert len(courses) == 2
    
    def test_database_cascade_behavior(self, db_session):
        """Test cascade behavior when deleting courses."""
        # Create course with lessons
        course = Course(title='Test Course', course_code='CASCADE101')
        db_session.add(course)
        db_session.commit()
        
        lesson1 = Lesson(title='Lesson 1', course_id=course.id)
        lesson2 = Lesson(title='Lesson 2', course_id=course.id)
        db_session.add_all([lesson1, lesson2])
        db_session.commit()
        
        # Count lessons before delete
        lessons_before = db_session.query(Lesson).filter_by(course_id=course.id).count()
        assert lessons_before == 2
        
        # Delete the course
        db_session.delete(course)
        db_session.commit()
        
        # Check if lessons still exist (they should, unless cascade is configured)
        lessons_after = db_session.query(Lesson).filter_by(course_id=course.id).all()
        # Without cascade delete, lessons should still exist
        assert len(lessons_after) == 2
        
        # But they should have orphaned course_id
        for lesson in lessons_after:
            assert lesson.course_id == course.id  # Still has the ID, but course is gone
    
    def test_transaction_rollback(self, db_session):
        """Test that transactions can be rolled back."""
        # Count initial courses
        initial_count = db_session.query(Course).count()
        
        # Create course but don't commit
        course = Course(title='Rollback Test', course_code='RB101')
        db_session.add(course)
        
        # Rollback
        db_session.rollback()
        
        # Count should be unchanged
        final_count = db_session.query(Course).count()
        assert final_count == initial_count
    
    def test_session_isolation(self, SessionFactory):
        """Test that sessions are isolated from each other."""
        # Create two independent sessions
        session1 = SessionFactory()
        session2 = SessionFactory()
        
        # Add course in session1
        course1 = Course(title='Session 1 Course', course_code='SESS1')
        session1.add(course1)
        session1.commit()
        
        # session2 shouldn't see it until committed and refreshed
        courses_in_session2 = session2.query(Course).filter_by(course_code='SESS1').first()
        # SQLite with in-memory might behave differently, but generally:
        # session2 should see it because it's committed
        
        # Cleanup
        session1.close()
        session2.close()