"""
Simple model tests for the Pearson Course Management System.
"""
import pytest
from datetime import datetime
from PythonProjects.pearson.models import Course, Lesson

def test_course_creation():
    """Test creating a Course instance."""
    course = Course(
        title="Python Programming",
        course_code="PY101",
        instructor="John Doe",
        level="Beginner"
    )

    assert str(course.title) == "Python Programming"
    assert str(course.course_code) == "PY101"
    assert str(course.instructor) == "John Doe"
    assert str(course.level) == "Beginner"
    assert course.created_date is None  # Not set until persisted
    
    # Test default values
    assert str(course.language) == "English"
    assert course.delivery_mode is None

def test_lesson_creation():
    """Test creating a Lesson instance."""
    lesson = Lesson(
        title="Introduction",
        content="Welcome to the course",
        duration=60,
        order=1,
        activity_type="Lecture"
    )
    
    assert str(lesson.title) == "Introduction"
    assert str(lesson.content) == "Welcome to the course"
    assert str(lesson.duration) == "60"
    assert str(lesson.order) == "1"
    assert str(lesson.activity_type) == "Lecture"
    assert lesson.created_date is None  # Not set until persisted

def test_course_string_representation():
    """Test Course __repr__ method."""
    course = Course(
        title="Test Course",
        course_code="TC101"
    )
    
    repr_str = repr(course)
    assert "Course" in repr_str
    assert "TC101" in repr_str
    assert "Test Course" in repr_str

def test_lesson_string_representation():
    """Test Lesson __repr__ method."""
    lesson = Lesson(
        title="Test Lesson",
        order=1
    )
    
    repr_str = repr(lesson)
    assert "Lesson" in repr_str
    assert "Test Lesson" in repr_str
    assert "1" in repr_str

@pytest.mark.integration
def test_course_persistence(db_session):
    """Test saving and retrieving a Course from database."""
    # Create and save a course
    course = Course(
        title="Database Test Course",
        course_code="DB101",
        instructor="Test Instructor"
    )
    
    db_session.add(course)
    db_session.commit()
    
    # Retrieve it
    retrieved = db_session.query(Course).filter_by(course_code="DB101").first()
    
    assert retrieved is not None
    assert retrieved.title == "Database Test Course"
    assert retrieved.instructor == "Test Instructor"
    assert isinstance(retrieved.created_date, datetime)

@pytest.mark.integration
def test_lesson_persistence(db_session):
    """Test saving and retrieving a Lesson from database."""
    # First create a course
    course = Course(title="Parent Course", course_code="PC101")
    db_session.add(course)
    db_session.commit()
    
    # Create a lesson for that course
    lesson = Lesson(
        title="Database Lesson",
        content="Test content",
        course_id=course.id
    )
    
    db_session.add(lesson)
    db_session.commit()
    
    # Retrieve it
    retrieved = db_session.query(Lesson).filter_by(title="Database Lesson").first()
    
    assert retrieved is not None
    assert retrieved.content == "Test content"
    assert retrieved.course_id == course.id
    assert isinstance(retrieved.created_date, datetime)