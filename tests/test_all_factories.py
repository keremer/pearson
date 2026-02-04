# tests/test_all_factories.py
import pytest
import sqlalchemy.orm

def test_all_factories(db_session):
    """Test that all factory classes work correctly."""
    # Set session on BaseFactory
    from tests.factories import BaseFactory
    BaseFactory._meta.sqlalchemy_session = db_session
    
    # Import all factories
    from tests.factories import (
        CourseFactory, LessonFactory, LearningOutcomeFactory,
        AssessmentFormatFactory, ToolFactory
    )
    
    # Test each factory
    print("Testing CourseFactory...")
    course = CourseFactory()
    assert course.id is not None
    print(f"  Created: {course.title}")
    
    print("Testing LessonFactory...")
    lesson = LessonFactory(course=course)
    assert lesson.course_id == course.id
    print(f"  Created: {lesson.title}")
    
    print("Testing LearningOutcomeFactory...")
    outcome = LearningOutcomeFactory(course=course)
    assert outcome.course_id == course.id
    print(f"  Created: {outcome.outcome_text[:50]}...")
    
    print("Testing AssessmentFormatFactory...")
    assessment = AssessmentFormatFactory(course=course)
    assert assessment.course_id == course.id
    print(f"  Created: {assessment.format_type}")
    
    print("Testing ToolFactory...")
    tool = ToolFactory(course=course)
    assert tool.course_id == course.id
    print(f"  Created: {tool.tool_name}")
    
    print("\n✅ All factories work correctly!")
    return True

if __name__ == "__main__":
    # Quick test without pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from PythonProjects.pearson.models import Base
    
    engine = create_engine('sqlite:///:memory:')
    Session = sessionmaker(bind=engine)
    session = Session()
    Base.metadata.create_all(engine)
    
    success = test_all_factories(session)
    exit(0 if success else 1)