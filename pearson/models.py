"""
Database models for Course Management System using SQLAlchemy ORM.
Enhanced with comprehensive relationships and validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, 
    DateTime, Float, Table, UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship, declarative_base, validates
from sqlalchemy.sql import func

Base = declarative_base()

# Association table for many-to-many between Lesson and LearningOutcome
lesson_learning_outcome = Table(
    'lesson_learning_outcome_assoc',
    Base.metadata,
    Column('lesson_id', Integer, ForeignKey('lessons.id', ondelete="CASCADE"), primary_key=True),
    Column('learning_outcome_id', Integer, ForeignKey('learning_outcomes.id', ondelete="CASCADE"), primary_key=True),
    Column('strength', String(20)),  # Primary, Secondary
    Column('created_date', DateTime, default=func.now()),
    UniqueConstraint('lesson_id', 'learning_outcome_id', name='uq_lesson_lo')
)


class Course(Base):
    """
    Course model representing a complete course.
    """
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    course_code = Column(String(50), nullable=False, unique=True, index=True)
    instructor = Column(String(100))
    contact_email = Column(String(100))
    level = Column(String(50))
    language = Column(String(50), default='English')
    delivery_mode = Column(String(50))
    aim = Column(Text)
    description = Column(Text)
    objectives = Column(Text)
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    lessons = relationship(
        "Lesson", 
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.order",
        lazy="dynamic"
    )
    
    learning_outcomes = relationship(
        "LearningOutcome",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="LearningOutcome.id"
    )
    
    assessment_formats = relationship(
        "AssessmentFormat",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="AssessmentFormat.id"
    )
    
    tools = relationship(
        "Tool",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Tool.id"
    )
    
    def __repr__(self) -> str:
        return f"<Course(id={self.id}, code='{self.course_code}', title='{self.title}')>"
    
    @validates('contact_email')
    def validate_email(self, key: str, email: Optional[str]) -> Optional[str]:
        """Simple email validation."""
        if email and '@' not in email:
            raise ValueError("Invalid email format")
        return email
    
    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """Convert course to dictionary representation."""
        result: Dict[str, Any] = {
            'id': self.id,
            'title': self.title,
            'course_code': self.course_code,
            'instructor': self.instructor,
            'contact_email': self.contact_email,
            'level': self.level,
            'language': self.language,
            'delivery_mode': self.delivery_mode,
            'aim': self.aim,
            'description': self.description,
            'objectives': self.objectives,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None,
            'updated_date': self.updated_date.isoformat() if self.updated_date is not None else None,
        }
        
        # Safely get lesson count
        try:
            if hasattr(self.lessons, 'count'):
                result['lesson_count'] = self.lessons.count()
            else:
                result['lesson_count'] = len(list(self.lessons))
        except:
            result['lesson_count'] = 0
        
        if include_relationships:
            result['lessons'] = [lesson.to_dict() for lesson in self.lessons]
            result['learning_outcomes'] = [lo.to_dict() for lo in self.learning_outcomes]
            result['assessment_formats'] = [af.to_dict() for af in self.assessment_formats]
            result['tools'] = [tool.to_dict() for tool in self.tools]
        
        return result


class Lesson(Base):
    """
    Lesson model representing individual lessons within a course.
    """
    __tablename__ = 'lessons'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    duration = Column(Integer, default=60)  # Duration in minutes
    order = Column(Integer, default=1)
    activity_type = Column(String(100))
    assignment_description = Column(Text)
    materials_needed = Column(Text)
    created_date = Column(DateTime, default=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="lessons")
    
    # Many-to-many relationship with LearningOutcome through association table
    learning_outcomes = relationship(
        "LearningOutcome",
        secondary=lesson_learning_outcome,
        back_populates="lessons",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, course_id={self.course_id}, title='{self.title}', order={self.order})>"
    
    @validates('duration')
    def validate_duration(self, key: str, duration: Optional[int]) -> Optional[int]:
        """Ensure duration is positive."""
        if duration is not None and duration <= 0:
            raise ValueError("Duration must be positive")
        return duration
    
    @validates('order')
    def validate_order(self, key: str, order: Optional[int]) -> Optional[int]:
        """Ensure order is positive."""
        if order is not None and order <= 0:
            raise ValueError("Order must be positive")
        return order
    
    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """Convert lesson to dictionary representation."""
        result: Dict[str, Any] = {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'content': self.content,
            'duration': self.duration,
            'order': self.order,
            'activity_type': self.activity_type,
            'assignment_description': self.assignment_description,
            'materials_needed': self.materials_needed,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None
        }
        
        if include_relationships:
            result['learning_outcomes'] = [
                {
                    'id': lo.id,
                    'outcome_text': lo.outcome_text,
                }
                for lo in self.learning_outcomes
            ]
        
        return result


class LearningOutcome(Base):
    """
    Learning outcomes for courses.
    """
    __tablename__ = 'learning_outcomes'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete="CASCADE"), nullable=False, index=True)
    outcome_text = Column(Text, nullable=False)
    created_date = Column(DateTime, default=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="learning_outcomes")
    
    # Many-to-many relationship with Lesson through association table
    lessons = relationship(
        "Lesson",
        secondary=lesson_learning_outcome,
        back_populates="learning_outcomes",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        outcome_val = self.outcome_text if isinstance(self.outcome_text, str) else ""
        short_text = outcome_val[:50] + "..." if len(outcome_val) > 50 else outcome_val
        return f"<LearningOutcome(id={self.id}, course_id={self.course_id}, text='{short_text}')>"
    
    def to_dict(self, include_coverage: bool = False) -> Dict[str, Any]:
        """Convert learning outcome to dictionary representation."""
        result: Dict[str, Any] = {
            'id': self.id,
            'course_id': self.course_id,
            'outcome_text': self.outcome_text,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None
        }
        
        return result


class AssessmentFormat(Base):
    """
    Assessment formats for courses.
    """
    __tablename__ = 'assessment_formats'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete="CASCADE"), nullable=False, index=True)
    format_type = Column(String(100), nullable=False)
    percentage = Column(Float)  # Percentage of total grade
    description = Column(Text)
    created_date = Column(DateTime, default=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="assessment_formats")
    
    def __repr__(self) -> str:
        return f"<AssessmentFormat(id={self.id}, course_id={self.course_id}, format='{self.format_type}', percentage={self.percentage})>"
    
    @validates('percentage')
    def validate_percentage(self, key: str, percentage: Optional[float]) -> Optional[float]:
        """Ensure percentage is between 0 and 100."""
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return percentage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert assessment format to dictionary representation."""
        return {
            'id': self.id,
            'course_id': self.course_id,
            'format_type': self.format_type,
            'percentage': self.percentage,
            'description': self.description,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None
        }


class Tool(Base):
    """
    Tools/software used in courses.
    """
    __tablename__ = 'tools'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    purpose = Column(Text)
    license_info = Column(String(100))
    created_date = Column(DateTime, default=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="tools")
    
    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, course_id={self.course_id}, name='{self.tool_name}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary representation."""
        return {
            'id': self.id,
            'course_id': self.course_id,
            'tool_name': self.tool_name,
            'purpose': self.purpose,
            'license_info': self.license_info,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None
        }


# Composite indexes for better query performance
Index('ix_course_instructor', Course.instructor)
Index('ix_course_level_language', Course.level, Course.language)
Index('ix_lesson_course_order', Lesson.course_id, Lesson.order)