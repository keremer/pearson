# test_factory_validation.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.factories import CourseFactory, LessonFactory, set_default_session

def test_current_factories():
    """Test if your current factory implementation works."""
    # Setup in-memory database
    engine = create_engine('sqlite:///:memory:')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create tables
    from PythonProjects.pearson.models import Base
    Base.metadata.create_all(engine)
    
    try:
        # Try to set session
        set_default_session(session)
        
        # Try to create objects
        print("Testing CourseFactory...")
        course = CourseFactory()
        print(f"  Created: {course.title}")
        
        print("Testing LessonFactory...")
        lesson = LessonFactory(course=course)
        print(f"  Created: {lesson.title} for course: {lesson.course.title}")
        
        print("\n✅ Factories work!")
        return True
    except Exception as e:
        print(f"\n❌ Factories failed: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    success = test_current_factories()
    exit(0 if success else 1)