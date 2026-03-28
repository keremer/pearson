from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, cast
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Numeric, Float, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, MappedAsDataclass, validates

# --- THE SINGLE INITIALIZATION POINT ---
class Base(MappedAsDataclass, DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# ----------------------------------------

# ================================================================
# 👥 CORE & AEC PLATFORM (Arkhon)
# ================================================================

class Party(db.Model, MappedAsDataclass):
    __tablename__ = "parties"

    party_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    
    role: Mapped[str] = mapped_column(String(20), default="guest")
    first_name: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    last_name: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    phone: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    regid: Mapped[Optional[str]] = mapped_column(String(11), default=None)
    address: Mapped[Optional[str]] = mapped_column(Text, default=None)
    city: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    district: Mapped[Optional[str]] = mapped_column(String(50), default=None)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="party", default_factory=list)

class Order(db.Model, MappedAsDataclass):
    __tablename__ = 'orders'

    order_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    
    party_id: Mapped[Optional[int]] = mapped_column(ForeignKey('parties.party_id'), default=None)
    offer_number: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), default=None)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    payment_plan: Mapped[Optional[str]] = mapped_column(Text, default=None)
    date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="orders", default=None)


# ================================================================
# 🎓 ACADEMIC PLATFORM (Pearson Automation)
# ================================================================

# Association table for many-to-many between Lesson and LearningOutcome
lesson_learning_outcome = db.Table(
    'lesson_learning_outcome_assoc',
    db.Model.metadata,
    db.Column('lesson_id', db.Integer, db.ForeignKey('lessons.lesson_id', ondelete="CASCADE"), primary_key=True),
    db.Column('learning_outcome_id', db.Integer, db.ForeignKey('learning_outcomes.id', ondelete="CASCADE"), primary_key=True),
    db.Column('strength', db.String(20)),  # Primary, Secondary
    db.Column('created_date', db.DateTime, default=datetime.utcnow),
    UniqueConstraint('lesson_id', 'learning_outcome_id', name='uq_lesson_lo')
)

class Course(db.Model, MappedAsDataclass):
    __tablename__ = 'courses'

    # Required
    course_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    course_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # Optional / Defaults
    instructor: Mapped[Optional[str]] = mapped_column(String(100), default=None, index=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    level: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    language: Mapped[Optional[str]] = mapped_column(String(50), default='English')
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    aim: Mapped[Optional[str]] = mapped_column(Text, default=None)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    objectives: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)
    updated_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lessons: Mapped[List["Lesson"]] = relationship('Lesson', back_populates='course', cascade='all, delete-orphan', order_by='Lesson.order', default_factory=list)
    learning_outcomes: Mapped[List["LearningOutcome"]] = relationship('LearningOutcome', back_populates='course', cascade='all, delete-orphan', order_by='LearningOutcome.id', default_factory=list)
    assessment_formats: Mapped[List["AssessmentFormat"]] = relationship('AssessmentFormat', back_populates='course', cascade='all, delete-orphan', order_by='AssessmentFormat.id', default_factory=list)
    tools: Mapped[List["Tool"]] = relationship('Tool', back_populates='course', cascade='all, delete-orphan', order_by='Tool.id', default_factory=list)

    # Composite Index mapping for SQLAlchemy 2.0
    __table_args__ = (
        Index('ix_course_level_language', 'level', 'language'),
    )

    def __repr__(self) -> str:
        return f"<Course(course_id={self.course_id}, code='{self.course_code}', title='{self.course_title}')>"

    @validates('contact_email')
    def validate_email(self, key: str, email: Optional[str]) -> Optional[str]:
        if email and '@' not in email:
            raise ValueError("Invalid email format")
        return email

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'course_id': self.course_id,
            'course_title': self.course_title,
            'course_code': self.course_code,
            'instructor': self.instructor,
            'contact_email': self.contact_email,
            'level': self.level,
            'language': self.language,
            'delivery_mode': self.delivery_mode,
            'aim': self.aim,
            'description': self.description,
            'objectives': self.objectives,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'updated_date': self.updated_date.isoformat() if self.updated_date else None,
            'lesson_count': len(self.lessons)
        }

        if include_relationships:
            result['lessons'] = [lesson.to_dict() for lesson in self.lessons]
            result['learning_outcomes'] = [lo.to_dict() for lo in self.learning_outcomes]
            result['assessment_formats'] = [af.to_dict() for af in self.assessment_formats]
            result['tools'] = [tool.to_dict() for tool in self.tools]

        return result


class Lesson(db.Model, MappedAsDataclass):
    __tablename__ = 'lessons'

    # Required
    lesson_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.course_id', ondelete="CASCADE"), nullable=False, index=True)
    lesson_title: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Optional / Defaults
    content: Mapped[Optional[str]] = mapped_column(Text, default=None)
    duration: Mapped[int] = mapped_column(Integer, default=60)
    order: Mapped[int] = mapped_column(Integer, default=1)
    activity_type: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    assignment_description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    materials_needed: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    # Relationships
    course: Mapped[Optional["Course"]] = relationship('Course', back_populates='lessons', default=None)
    learning_outcomes: Mapped[List["LearningOutcome"]] = relationship('LearningOutcome', secondary=lesson_learning_outcome, back_populates='lessons', default_factory=list)

    __table_args__ = (
        Index('ix_lesson_course_order', 'course_id', 'order'),
    )

    def __repr__(self) -> str:
        return f"<Lesson(id={self.lesson_id}, course_id={self.course_id}, title='{self.lesson_title}', order={self.order})>"

    @validates('duration')
    def validate_duration(self, key: str, duration: int) -> int:
        if duration <= 0:
            raise ValueError("Duration must be positive")
        return duration

    @validates('order')
    def validate_order(self, key: str, order: int) -> int:
        if order <= 0:
            raise ValueError("Order must be positive")
        return order

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'lesson_id': self.lesson_id,
            'course_id': self.course_id,
            'lesson_title': self.lesson_title,
            'content': self.content,
            'duration': self.duration,
            'order': self.order,
            'activity_type': self.activity_type,
            'assignment_description': self.assignment_description,
            'materials_needed': self.materials_needed,
            'created_date': self.created_date.isoformat() if self.created_date else None
        }

        if include_relationships:
            result['learning_outcomes'] = [
                {'id': lo.id, 'outcome_text': lo.outcome_text} for lo in self.learning_outcomes
            ]

        return result


class LearningOutcome(db.Model, MappedAsDataclass):
    __tablename__ = 'learning_outcomes'

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.course_id', ondelete="CASCADE"), nullable=False, index=True)
    outcome_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    course: Mapped[Optional["Course"]] = relationship('Course', back_populates='learning_outcomes', default=None)
    lessons: Mapped[List["Lesson"]] = relationship('Lesson', secondary=lesson_learning_outcome, back_populates='learning_outcomes', default_factory=list)

    def __repr__(self) -> str:
        outcome_val = self.outcome_text if isinstance(self.outcome_text, str) else ""
        short_text = outcome_val[:50] + "..." if len(outcome_val) > 50 else outcome_val
        return f"<LearningOutcome(id={self.id}, course_id={self.course_id}, text='{short_text}')>"

    def to_dict(self, include_coverage: bool = False) -> Dict[str, Any]:
        return {
            'id': self.id,
            'course_id': self.course_id,
            'outcome_text': self.outcome_text,
            'created_date': self.created_date.isoformat() if self.created_date else None
        }


class AssessmentFormat(db.Model, MappedAsDataclass):
    __tablename__ = 'assessment_formats'

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.course_id', ondelete="CASCADE"), nullable=False, index=True)
    format_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    percentage: Mapped[Optional[float]] = mapped_column(Float, default=None)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    course: Mapped[Optional["Course"]] = relationship('Course', back_populates='assessment_formats', default=None)

    def __repr__(self) -> str:
        return f"<AssessmentFormat(id={self.id}, course_id={self.course_id}, format='{self.format_type}', percentage={self.percentage})>"

    @validates('percentage')
    def validate_percentage(self, key: str, percentage: Optional[float]) -> Optional[float]:
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return percentage

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'course_id': self.course_id,
            'format_type': self.format_type,
            'percentage': self.percentage,
            'description': self.description,
            'created_date': self.created_date.isoformat() if self.created_date else None
        }


class Tool(db.Model, MappedAsDataclass):
    __tablename__ = 'tools'

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.course_id', ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    purpose: Mapped[Optional[str]] = mapped_column(Text, default=None)
    license_info: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    course: Mapped[Optional["Course"]] = relationship('Course', back_populates='tools', default=None)

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, course_id={self.course_id}, name='{self.tool_name}')>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'course_id': self.course_id,
            'tool_name': self.tool_name,
            'purpose': self.purpose,
            'license_info': self.license_info,
            'created_date': self.created_date.isoformat() if self.created_date else None
        }