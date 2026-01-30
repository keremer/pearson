"""
Unit tests for database models with relationships.
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from shared.models import Course, Lesson, LearningOutcome, AssessmentFormat, Tool

class TestCourseModelRelationships:
    """Tests for Course model relationships."""
    
    def test_course_lessons_relationship(self, db_session):
        """Test bidirectional relationship between Course and Lesson."""
        # Create a course
        course = Course(
            title='Python Programming',
            course_code='PY101',
            instructor='John Doe'
        )
        db_session.add(course)
        db_session.commit()
        
        # Create lessons using the relationship
        lesson1 = Lesson(
            title='Introduction',
            content='Python basics',
            order=1,
            course=course  # Use relationship, not course_id
        )
        
        lesson2 = Lesson(
            title='Advanced Topics',
            content='Advanced Python',
            order=2,
            course=course  # Use relationship
        )
        
        db_session.add_all([lesson1, lesson2])
        db_session.commit()
        
        # Refresh to load relationships
        db_session.refresh(course)
        
        # Test bidirectional access
        assert len(course.lessons.all()) == 2  # Using .all() because lazy="dynamic"
        assert str(course.lessons.first().title) == 'Introduction'
        assert str(lesson1.course.title) == 'Python Programming'
        assert str(lesson1.course_id) == str(course.id)
    
    def test_course_cascade_delete(self, db_session):
        """Test that deleting a course cascades to lessons."""
        # Create course with lessons
        course = Course(title='Test Course', course_code='CASCADE101')
        lesson1 = Lesson(title='Lesson 1', course=course)
        lesson2 = Lesson(title='Lesson 2', course=course)
        
        db_session.add(course)
        db_session.add_all([lesson1, lesson2])
        db_session.commit()
        
        # Verify lessons exist
        lesson_count = db_session.query(Lesson).filter_by(course_id=course.id).count()
        assert lesson_count == 2
        
        # Delete the course
        db_session.delete(course)
        db_session.commit()
        
        # Lessons should be automatically deleted due to cascade
        remaining_lessons = db_session.query(Lesson).filter_by(course_id=course.id).all()
        assert len(remaining_lessons) == 0
    
    def test_course_lesson_ordering(self, db_session):
        """Test that lessons are automatically ordered by 'order' field."""
        course = Course(title='Ordered Course', course_code='ORDER101')
        
        # Create lessons in reverse order
        lesson3 = Lesson(title='Lesson 3', order=3, course=course)
        lesson1 = Lesson(title='Lesson 1', order=1, course=course)
        lesson2 = Lesson(title='Lesson 2', order=2, course=course)
        
        db_session.add(course)
        db_session.commit()
        
        # Get lessons - should be ordered
        lessons = course.lessons.order_by(Lesson.order).all()
        assert len(lessons) == 3
        assert lessons[0].title == 'Lesson 1'
        assert lessons[1].title == 'Lesson 2'
        assert lessons[2].title == 'Lesson 3'
    
    def test_course_other_relationships(self, db_session):
        """Test relationships with other models."""
        course = Course(title='Comprehensive Course', course_code='COMP101')
        
        # Create related objects
        outcome = LearningOutcome(
            outcome_text='Learn Python programming',
            course=course
        )
        
        assessment = AssessmentFormat(
            format_type='Exam',
            percentage=50.0,
            description='Final exam',
            course=course
        )
        
        tool = Tool(
            tool_name='PyCharm',
            purpose='Python IDE',
            license_info='Commercial',
            course=course
        )
        
        db_session.add(course)
        db_session.commit()
        
        # Test relationships
        assert len(course.learning_outcomes) == 1
        assert course.learning_outcomes[0].outcome_text == 'Learn Python programming'
        
        assert len(course.assessment_formats) == 1
        assert course.assessment_formats[0].format_type == 'Exam'
        
        assert len(course.tools) == 1
        assert course.tools[0].tool_name == 'PyCharm'

class TestLessonModelRelationships:
    """Tests for Lesson model relationships."""
    
    def test_lesson_course_backref(self, db_session):
        """Test accessing course from lesson."""
        course = Course(title='Parent Course', course_code='PARENT101')
        lesson = Lesson(title='Child Lesson', course=course)
        
        db_session.add_all([course, lesson])
        db_session.commit()
        
        # Test backref
        assert lesson.course.title == 'Parent Course'
        assert lesson.course.course_code == 'PARENT101'
        
        # Test foreign key
        assert str(lesson.course_id) == str(course.id)
    
    def test_lesson_validation(self, db_session):
        """Test lesson field validations."""
        course = Course(title='Validation Course', course_code='VALID101')
        db_session.add(course)
        db_session.commit()
        
        # Test positive duration validation
        with pytest.raises(ValueError):
            lesson = Lesson(
                title='Invalid Duration',
                duration=-10,  # Negative duration
                course=course
            )
            db_session.add(lesson)
            db_session.commit()
        db_session.rollback()
        
        # Test positive order validation
        with pytest.raises(ValueError):
            lesson = Lesson(
                title='Invalid Order',
                order=0,  # Zero order
                course=course
            )
            db_session.add(lesson)
            db_session.commit()
        db_session.rollback()

class TestAssessmentFormatValidation:
    """Tests for AssessmentFormat validation."""
    
    def test_percentage_validation(self, db_session):
        """Test percentage validation."""
        course = Course(title='Assessment Course', course_code='ASSESS101')
        db_session.add(course)
        db_session.commit()
        
        # Test valid percentage
        assessment = AssessmentFormat(
            format_type='Valid',
            percentage=75.5,
            course=course
        )
        db_session.add(assessment)
        db_session.commit()
        assert str(assessment.percentage) == str(pytest.approx(75.5))
        
        # Test invalid percentage (negative)
        with pytest.raises(ValueError):
            assessment2 = AssessmentFormat(
                format_type='Invalid',
                percentage=-10.0,
                course=course
            )
            db_session.add(assessment2)
            db_session.commit()
        db_session.rollback()
        
        # Test invalid percentage (over 100)
        with pytest.raises(ValueError):
            assessment3 = AssessmentFormat(
                format_type='Invalid',
                percentage=150.0,
                course=course
            )
            db_session.add(assessment3)
            db_session.commit()
        db_session.rollback()

class TestEmailValidation:
    """Tests for email validation in Course model."""
    
    def test_email_validation(self, db_session):
        """Test email format validation."""
        # Test valid email
        course1 = Course(
            title='Valid Email Course',
            course_code='EMAIL1',
            contact_email='instructor@example.com'
        )
        db_session.add(course1)
        db_session.commit()
        assert str(course1.contact_email) == 'instructor@example.com'
        
        # Test invalid email
        with pytest.raises(ValueError):
            course2 = Course(
                title='Invalid Email Course',
                course_code='EMAIL2',
                contact_email='not-an-email'
            )
            db_session.add(course2)
            db_session.commit()
        db_session.rollback()
        
        # Test empty email (should be allowed)
        course3 = Course(
            title='No Email Course',
            course_code='EMAIL3',
            contact_email=''  # Empty string
        )
        db_session.add(course3)
        db_session.commit()
        assert str(course3.contact_email) == ''

def test_to_dict_methods(db_session):
    """Test serialization methods."""
    # Create course with lesson
    course = Course(
        title='Serialization Test',
        course_code='SERIAL101',
        instructor='Test Instructor',
        contact_email='test@example.com'
    )
    
    lesson = Lesson(
        title='Test Lesson',
        content='Lesson content',
        duration=45,
        order=1,
        course=course
    )
    
    db_session.add_all([course, lesson])
    db_session.commit()
    
    # Test course to_dict
    course_dict = course.to_dict()
    assert course_dict['title'] == 'Serialization Test'
    assert course_dict['course_code'] == 'SERIAL101'
    assert course_dict['lesson_count'] == 1
    assert 'created_date' in course_dict
    assert 'updated_date' in course_dict
    
    # Test lesson to_dict
    lesson_dict = lesson.to_dict()
    assert lesson_dict['title'] == 'Test Lesson'
    assert lesson_dict['duration'] == 45
    assert lesson_dict['order'] == 1
    assert 'created_date' in lesson_dict
    
    # Ensure dates are ISO format strings
    assert isinstance(course_dict['created_date'], str)
    assert 'T' in course_dict['created_date']  # ISO format has 'T' separator