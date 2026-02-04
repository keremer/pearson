"""
Factories for creating test data using Factory Boy - Clean version.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.orm import Session
from typing import Optional

from PythonProjects.pearson.models import (
    Course, Lesson, LearningOutcome, 
    AssessmentFormat, Tool, LessonLearningOutcome
)

# Global session for factories (optional - simpler approach follows)
_DEFAULT_SESSION: Optional[Session] = None

def set_default_session(session: Session) -> None:
    """Set the default SQLAlchemy session for all factories."""
    global _DEFAULT_SESSION
    _DEFAULT_SESSION = session

# Simple base factory
class BaseFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore
        abstract = True
        sqlalchemy_session_persistence = 'commit'

# Course factory
class CourseFactory(BaseFactory):
    class Meta:  # type: ignore
        model = Course
    
    id = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f'Test Course {n}')
    course_code = factory.Sequence(lambda n: f'TC{n:03d}')
    instructor = factory.Faker('name')
    contact_email = factory.Faker('email')
    level = factory.Iterator(['Beginner', 'Intermediate', 'Advanced'])
    language = 'English'
    delivery_mode = factory.Iterator(['Online', 'In-person', 'Hybrid'])
    aim = factory.Faker('sentence')
    description = factory.Faker('paragraph')
    objectives = factory.Faker('paragraph')

# Lesson factory  
class LessonFactory(BaseFactory):
    class Meta:  # type: ignore
        model = Lesson
    
    id = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f'Test Lesson {n}')
    content = factory.Faker('paragraph')
    duration = factory.Iterator([30, 45, 60, 90])
    order = factory.Sequence(lambda n: n + 1)
    activity_type = factory.Iterator(['Lecture', 'Workshop', 'Lab', 'Discussion'])
    assignment_description = factory.Faker('sentence')
    materials_needed = factory.Faker('sentence')
    
    course = factory.SubFactory(CourseFactory)
    course_id = factory.SelfAttribute('course.id')

# LearningOutcome factory
class LearningOutcomeFactory(BaseFactory):
    class Meta:  # type: ignore
        model = LearningOutcome
    
    id = factory.Sequence(lambda n: n + 1)
    outcome_text = factory.Sequence(lambda n: f'Learning Outcome {n}: Master key concepts')
    course = factory.SubFactory(CourseFactory)

# AssessmentFormat factory
class AssessmentFormatFactory(BaseFactory):
    class Meta:  # type: ignore
        model = AssessmentFormat
    
    id = factory.Sequence(lambda n: n + 1)
    format_type = factory.Iterator(['Exam', 'Quiz', 'Project', 'Presentation', 'Homework'])
    percentage = factory.Iterator([20.0, 30.0, 25.0, 15.0, 10.0])
    description = factory.Faker('sentence')
    course = factory.SubFactory(CourseFactory)

# Tool factory
class ToolFactory(BaseFactory):
    class Meta:  # type: ignore
        model = Tool
    
    id = factory.Sequence(lambda n: n + 1)
    tool_name = factory.Sequence(lambda n: f'Tool {n}')
    purpose = factory.Faker('sentence')
    license_info = factory.Iterator(['MIT', 'Apache 2.0', 'GPLv3', 'BSD', 'Proprietary'])
    course = factory.SubFactory(CourseFactory)

# LessonLearningOutcome association factory (optional)
class LessonLearningOutcomeFactory(BaseFactory):
    class Meta:  # type: ignore
        model = LessonLearningOutcome
    
    id = factory.Sequence(lambda n: n + 1)
    strength = factory.Iterator(['Primary', 'Secondary', 'Tertiary'])
    lesson = factory.SubFactory(LessonFactory)
    learning_outcome = factory.SubFactory(LearningOutcomeFactory)

# Correct exports
__all__ = [
    'set_default_session',
    'BaseFactory',
    'CourseFactory', 
    'LessonFactory',
    'LearningOutcomeFactory',
    'AssessmentFormatFactory',
    'ToolFactory',
    'LessonLearningOutcomeFactory',  # Optional
]