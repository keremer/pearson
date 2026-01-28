"""
Database models for Course Management System using SQLAlchemy ORM.
Enhanced with comprehensive relationships and validation.
"""
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, ForeignKey, 
                       DateTime, Boolean, Float, Table, UniqueConstraint)
from sqlalchemy.orm import relationship, declarative_base, validates, backref
from sqlalchemy.sql import func
from sqlalchemy.schema import Index

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
    
    def __repr__(self):
        return f"<Course(id={self.id}, code='{self.course_code}', title='{self.title}')>"
    
    @validates('contact_email')
    def validate_email(self, key, email):
        """Simple email validation."""
        if email and '@' not in email:
            raise ValueError("Invalid email format")
        return email
    
    def get_learning_outcome_coverage(self):
        """Calculate how many lessons cover each learning outcome."""
        coverage = {}
        for lo in self.learning_outcomes:
            lesson_count = sum(1 for lesson in self.lessons if lo in lesson.learning_outcomes)
            coverage[lo.id] = {
                'outcome': lo.outcome_text,
                'total_lessons': self.lessons.count(),
                'covered_in_lessons': lesson_count,
                'coverage_percentage': (lesson_count / self.lessons.count() * 100) if self.lessons.count() > 0 else 0
            }
        return coverage
    
    def to_dict(self, include_relationships=False):
        """Convert course to dictionary representation."""
        result = {
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
            'lesson_count': self.lessons.count() if hasattr(self.lessons, 'count') else len(self.lessons)
        }
        
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
    
    # Direct access to association objects with strength
    learning_outcome_associations = relationship(
        "LessonLearningOutcome",
        back_populates="lesson",
        cascade="all, delete-orphan"
    )
    
    # Index for efficient ordering
    __table_args__ = (
        Index('ix_lesson_course_order', 'course_id', 'order'),
        Index('ix_lesson_activity', 'activity_type'),
    )
    
    def __repr__(self):
        return f"<Lesson(id={self.id}, course_id={self.course_id}, title='{self.title}', order={self.order})>"
    
    @validates('duration')
    def validate_duration(self, key, duration):
        """Ensure duration is positive."""
        if duration is not None and duration <= 0:
            raise ValueError("Duration must be positive")
        return duration
    
    @validates('order')
    def validate_order(self, key, order):
        """Ensure order is positive."""
        if order is not None and order <= 0:
            raise ValueError("Order must be positive")
        return order
    
    def add_learning_outcome(self, learning_outcome, strength="Primary"):
        """Helper method to add a learning outcome with strength."""
        from sqlalchemy.orm import Session
        session = Session.object_session(self)
        if session is None:
            raise RuntimeError("Lesson object is not attached to a session. Please add it to a session before calling this method.")
        
        # Check if association already exists
        existing = session.query(lesson_learning_outcome).filter_by(
            lesson_id=self.id,
            learning_outcome_id=learning_outcome.id
        ).first()
        
        if not existing:
            # Create new association
            stmt = lesson_learning_outcome.insert().values(
                lesson_id=self.id,
                learning_outcome_id=learning_outcome.id,
                strength=strength
            )
            session.execute(stmt)
            session.commit()
    
    def get_learning_outcomes_by_strength(self, strength=None):
        """Get learning outcomes filtered by strength."""
        query = self.learning_outcomes
        if strength:
            # This requires a join with the association table
            from sqlalchemy.orm import aliased
            from sqlalchemy import and_
            
            # We'll implement this in the actual query
            pass
        return query.all()
    
    def to_dict(self, include_relationships=False):
        """Convert lesson to dictionary representation."""
        result = {
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
                    'strength': self._get_lo_strength(lo.id)
                }
                for lo in self.learning_outcomes
            ]
        
        return result
    
    def _get_lo_strength(self, lo_id):
        """Get the strength of a specific learning outcome for this lesson."""
        from sqlalchemy.orm import Session
        session = Session.object_session(self)
        
        if session is None:
            return None

        result = session.execute(
            lesson_learning_outcome.select().where(
                lesson_learning_outcome.c.lesson_id == self.id,
                lesson_learning_outcome.c.learning_outcome_id == lo_id
            )
        ).first()
        
        return result.strength if result else None

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
    
    # Direct access to association objects
    lesson_associations = relationship(
        "LessonLearningOutcome",
        back_populates="learning_outcome",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        outcome_val = self.outcome_text if isinstance(self.outcome_text, str) else ""
        short_text = outcome_val[:50] + "..." if len(outcome_val) > 50 else outcome_val
        return f"<LearningOutcome(id={self.id}, course_id={self.course_id}, text='{short_text}')>"
    
    def get_coverage(self):
        """Calculate which lessons cover this learning outcome."""
        coverage = {
            'total_lessons': self.course.lessons.count() if self.course else 0,
            'covered_in': [],
            'primary_strength_count': 0,
            'secondary_strength_count': 0
        }
        
        for lesson in self.lessons:
            # Find the strength for this lesson
            for assoc in lesson.learning_outcome_associations:
                if assoc.learning_outcome_id == self.id:
                    coverage['covered_in'].append({
                        'lesson_id': lesson.id,
                        'lesson_title': lesson.title,
                        'strength': assoc.strength
                    })
                    if assoc.strength == 'Primary':
                        coverage['primary_strength_count'] += 1
                    elif assoc.strength == 'Secondary':
                        coverage['secondary_strength_count'] += 1
                    break
        
        coverage['total_covered'] = len(coverage['covered_in'])
        coverage['coverage_percentage'] = (
            coverage['total_covered'] / coverage['total_lessons'] * 100
            if coverage['total_lessons'] > 0 else 0
        )
        
        return coverage
    
    def to_dict(self, include_coverage=False):
        """Convert learning outcome to dictionary representation."""
        result = {
            'id': self.id,
            'course_id': self.course_id,
            'outcome_text': self.outcome_text,
            'created_date': self.created_date.isoformat() if self.created_date is not None else None
        }
        
        if include_coverage:
            result['coverage'] = self.get_coverage()
        
        return result

class LessonLearningOutcome(Base):
    """
    Association model for Lesson and LearningOutcome with additional attributes.
    Represents which learning outcomes are addressed in each lesson and with what strength.
    """
    __tablename__ = 'lesson_learning_outcomes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lesson_id = Column(Integer, ForeignKey('lessons.id', ondelete="CASCADE"), nullable=False)
    learning_outcome_id = Column(Integer, ForeignKey('learning_outcomes.id', ondelete="CASCADE"), nullable=False)
    strength = Column(String(20))  # Primary, Secondary, Tertiary
    
    # Relationships
    lesson = relationship("Lesson", back_populates="learning_outcome_associations")
    learning_outcome = relationship("LearningOutcome", back_populates="lesson_associations")
    
    # Unique constraint to prevent duplicate associations
    __table_args__ = (
        UniqueConstraint('lesson_id', 'learning_outcome_id', name='uq_lesson_lo_direct'),
    )
    
    def __repr__(self):
        return f"<LessonLO(id={self.id}, lesson={self.lesson_id}, LO={self.learning_outcome_id}, strength='{self.strength}')>"
    
    @validates('strength')
    def validate_strength(self, key, strength):
        """Validate strength value."""
        valid_strengths = ['Primary', 'Secondary', 'Tertiary']
        if strength not in valid_strengths:
            raise ValueError(f"Strength must be one of {valid_strengths}")
        return strength
    
    def to_dict(self):
        """Convert association to dictionary representation."""
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'learning_outcome_id': self.learning_outcome_id,
            'strength': self.strength,
            'lesson_title': self.lesson.title if self.lesson else None,
            'outcome_text': self.learning_outcome.outcome_text[:100] if self.learning_outcome else None
        }

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
    
    def __repr__(self):
        return f"<AssessmentFormat(id={self.id}, course_id={self.course_id}, format='{self.format_type}', percentage={self.percentage})>"
    
    @validates('percentage')
    def validate_percentage(self, key, percentage):
        """Ensure percentage is between 0 and 100."""
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return percentage
    
    def to_dict(self):
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
    
    def __repr__(self):
        return f"<Tool(id={self.id}, course_id={self.course_id}, name='{self.tool_name}')>"
    
    def to_dict(self):
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
Index('ix_lesson_learning_outcome', LessonLearningOutcome.lesson_id, LessonLearningOutcome.learning_outcome_id)
Index('ix_lo_strength', LessonLearningOutcome.strength)