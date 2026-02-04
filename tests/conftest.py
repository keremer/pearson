"""
Pytest configuration and fixtures for Pearson Course Management System.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import event

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from PythonProjects.pearson.models import Base, Course, Lesson, LearningOutcome, AssessmentFormat, Tool, LessonLearningOutcome
from pearson.cli.setup import DatabaseSetup
from pearson.web import web_bp  # Now this works!

# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope='session')
def test_database_url():
    """Get test database URL. Using in-memory SQLite for speed."""
    return 'sqlite:///:memory:'

@pytest.fixture(scope='session')
def test_engine(test_database_url):
    """Create test database engine."""
    engine = create_engine(test_database_url)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture(scope='session')
def SessionFactory(test_engine):
    """Create session factory for the entire test session."""
    return sessionmaker(bind=test_engine, expire_on_commit=False)

@pytest.fixture
def db_session(SessionFactory):
    """
    Provide a fresh database session for each test.
    Uses nested transactions for automatic rollback.
    """
    # Create a session
    session = SessionFactory()
    
    # Begin a transaction
    session.begin()
    
    # Begin a nested transaction (savepoint)
    session.begin_nested()
    
    # SQLAlchemy event for savepoint management
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        """
        Each time the nested transaction ends, reopen it.
        This allows rollback to work properly.
        """
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()
    
    yield session
    
    # Cleanup - rollback the transaction
    session.rollback()
    session.close()

# ============================================================================
# FLASK APPLICATION FIXTURES
# ============================================================================

@pytest.fixture
def app(test_database_url):
    """
    Create and configure a Flask app for testing.
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Test configuration
    app.config.update({
        'TESTING': True,
        'DATABASE_URL': test_database_url,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })
    
    # Register blueprint
    app.register_blueprint(web_bp, url_prefix='/')
    
    # Setup database (matching your routes' expectations)
    db_setup = DatabaseSetup(test_database_url)
    app.config['db_setup'] = db_setup
    
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_course_injector(mocker):
    """Mock the CourseInjector class."""
    return mocker.patch('cli.course_injector.CourseInjector')

@pytest.fixture
def mock_db_setup(mocker):
    """Mock the DatabaseSetup class."""
    return mocker.patch('cli.setup.DatabaseSetup')

# ============================================================================
# TEST DATA FACTORIES
# ============================================================================

@pytest.fixture
def sample_course_data():
    """Return sample course data for testing."""
    return {
        'title': 'Test Course',
        'course_code': 'TC101',
        'instructor': 'Test Instructor',
        'contact_email': 'instructor@test.edu',
        'level': 'Beginner',
        'language': 'English',
        'delivery_mode': 'Online',
        'aim': 'Test aim',
        'description': 'Test description',
        'objectives': 'Test objectives'
    }

@pytest.fixture
def sample_lesson_data():
    """Return sample lesson data for testing."""
    return {
        'title': 'Test Lesson',
        'content': 'Test content',
        'duration': 60,
        'order': 1,
        'activity_type': 'Lecture',
        'assignment_description': 'Test assignment',
        'materials_needed': 'Test materials'
    }

# ============================================================================
# HELPER FUNCTIONS (available as fixtures)
# ============================================================================

def create_test_course(session, **kwargs):
    """Helper to create a test course."""
    defaults = {
        'title': 'Test Course',
        'course_code': 'TC101',
        'instructor': 'Test Instructor',
        'contact_email': 'instructor@test.edu',
        'level': 'Beginner',
        'language': 'English',
        'delivery_mode': 'Online',
        'aim': 'Test aim',
        'description': 'Test description',
        'objectives': 'Test objectives'
    }
    defaults.update(kwargs)
    
    course = Course(**defaults)
    session.add(course)
    session.commit()
    session.refresh(course)  # Refresh to load relationships
    return course

def create_test_lesson(session, course=None, course_id=None, **kwargs):
    """Helper to create a test lesson."""
    if not course and not course_id:
        raise ValueError("Either course or course_id must be provided")
    
    defaults = {
        'title': 'Test Lesson',
        'content': 'Test content',
        'duration': 60,
        'order': 1,
        'activity_type': 'Lecture',
        'assignment_description': 'Test assignment',
        'materials_needed': 'Test materials'
    }
    defaults.update(kwargs)
    
    lesson = Lesson(**defaults)
    
    if course:
        lesson.course = course  # Use relationship
    elif course_id is not None:
        lesson.course_id = course_id  # Use foreign key
    
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson

def create_test_learning_outcome(session, course, outcome_text="Test outcome"):
    """Helper to create a test learning outcome."""
    outcome = LearningOutcome(
        outcome_text=outcome_text,
        course=course
    )
    session.add(outcome)
    session.commit()
    return outcome

def create_test_assessment_format(session, course, format_type="Exam", percentage=50.0):
    """Helper to create a test assessment format."""
    assessment = AssessmentFormat(
        format_type=format_type,
        percentage=percentage,
        description=f"Test {format_type}",
        course=course
    )
    session.add(assessment)
    session.commit()
    return assessment

def create_test_tool(session, course, tool_name="Test Tool"):
    """Helper to create a test tool."""
    tool = Tool(
        tool_name=tool_name,
        purpose="Testing purposes",
        license_info="MIT",
        course=course
    )
    session.add(tool)
    session.commit()
    return tool

# Make helper functions available as fixtures
@pytest.fixture
def course_factory():
    """Fixture that returns the create_test_course function."""
    return create_test_course

@pytest.fixture
def lesson_factory():
    """Fixture that returns the create_test_lesson function."""
    return create_test_lesson

@pytest.fixture
def learning_outcome_factory():
    """Fixture that returns the create_test_learning_outcome function."""
    return create_test_learning_outcome

@pytest.fixture
def assessment_format_factory():
    """Fixture that returns the create_test_assessment_format function."""
    return create_test_assessment_format

@pytest.fixture
def tool_factory():
    """Fixture that returns the create_test_tool function."""
    return create_test_tool

# ============================================================================
# COMMON TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def course_with_lessons(db_session, course_factory, lesson_factory):
    """Create a course with multiple lessons."""
    course = course_factory(
        db_session,
        title="Course with Lessons",
        course_code="CWL101"
    )
    
    # Add lessons
    lesson1 = lesson_factory(
        db_session,
        course=course,
        title="Lesson 1",
        order=1
    )
    
    lesson2 = lesson_factory(
        db_session,
        course=course,
        title="Lesson 2",
        order=2
    )
    
    return {
        'course': course,
        'lessons': [lesson1, lesson2]
    }

@pytest.fixture
def complete_course(db_session, course_factory, lesson_factory, 
                   learning_outcome_factory, assessment_format_factory, 
                   tool_factory):
    """Create a complete course with all related entities."""
    course = course_factory(
        db_session,
        title="Complete Course",
        course_code="COMP101"
    )
    
    # Add lessons
    lesson1 = lesson_factory(db_session, course=course, title="Intro", order=1)
    lesson2 = lesson_factory(db_session, course=course, title="Advanced", order=2)
    
    # Add learning outcomes
    outcome1 = learning_outcome_factory(db_session, course, "Learn Python")
    outcome2 = learning_outcome_factory(db_session, course, "Build projects")
    
    # Add assessment formats
    exam = assessment_format_factory(db_session, course, "Exam", 50.0)
    project = assessment_format_factory(db_session, course, "Project", 30.0)
    
    # Add tools
    tool1 = tool_factory(db_session, course, "Python")
    tool2 = tool_factory(db_session, course, "VS Code")
    
    return {
        'course': course,
        'lessons': [lesson1, lesson2],
        'outcomes': [outcome1, outcome2],
        'assessments': [exam, project],
        'tools': [tool1, tool2]
    
    }
def create_test_lesson_learning_outcome(session, lesson, learning_outcome, strength="Primary"):
    """Helper to create a LessonLearningOutcome association."""
    # Check if association already exists
    existing = session.query(LessonLearningOutcome).filter_by(
        lesson_id=lesson.id,
        learning_outcome_id=learning_outcome.id
    ).first()
    
    if existing:
        return existing
    
    # Create new association
    association = LessonLearningOutcome(
        lesson=lesson,
        learning_outcome=learning_outcome,
        strength=strength
    )
    session.add(association)
    session.commit()
    return association

def create_course_with_learning_outcomes(session, num_outcomes=3):
    """Create a course with learning outcomes."""
    course = create_test_course(session, title="Course with LOs", course_code="CLO101")
    
    learning_outcomes = []
    for i in range(num_outcomes):
        lo = create_test_learning_outcome(
            session,
            course,
            outcome_text=f"Learning Outcome {i+1}: Master concept {i+1}"
        )
        learning_outcomes.append(lo)
    
    return {
        'course': course,
        'learning_outcomes': learning_outcomes
    }

def create_lesson_with_learning_outcomes(session, course, num_outcomes=2):
    """Create a lesson with associated learning outcomes."""
    lesson = create_test_lesson(session, course=course, title="Comprehensive Lesson")
    
    # Create learning outcomes for the course
    outcomes = []
    for i in range(num_outcomes):
        lo = create_test_learning_outcome(
            session,
            course,
            outcome_text=f"LO for lesson: Outcome {i+1}"
        )
        outcomes.append(lo)
        
        # Associate with lesson
        strength = "Primary" if i == 0 else "Secondary"
        create_test_lesson_learning_outcome(session, lesson, lo, strength)
    
    return {
        'lesson': lesson,
        'learning_outcomes': outcomes
    }

# Add to pytest fixtures
@pytest.fixture
def lesson_learning_outcome_factory():
    """Fixture that returns the create_test_lesson_learning_outcome function."""
    return create_test_lesson_learning_outcome