import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import (DeclarativeBase, Mapped, MappedAsDataclass,
                            mapped_column, relationship, validates)
from werkzeug.security import check_password_hash, generate_password_hash


# --- THE SINGLE INITIALIZATION POINT ---
class Base(MappedAsDataclass, DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# ----------------------------------------

# ================================================================
# 👥 CORE & AEC PLATFORM (crminaec)
# ================================================================

class UserAccount(db.Model):
    """Strictly Portal Authentication & Security Data."""
    __tablename__ = 'user_accounts'
    
    # 🔴 REQUIRED FIELDS (Must be first)
    # init=False because the database generates this ID
    account_id: Mapped[int] = mapped_column(primary_key=True, init=False) 
    party_id: Mapped[int] = mapped_column(ForeignKey('parties.party_id'), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), init=False)
    
    # 🔗 RELATIONSHIP
    # default=None is required here so the dataclass doesn't ask for a Party object on creation
    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="account", default=None)
    
    # 🟢 OPTIONAL FIELDS (Must go last, and MUST have default=...)
    role: Mapped[str] = mapped_column(String(50), default='customer')
    is_confirmed: Mapped[bool] = mapped_column(default=False)
    kvkk_approved: Mapped[bool] = mapped_column(default=False)
    
    # THE FIX: Explicit default=None added to these columns!
    confirmed_on: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    kvkk_approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    kvkk_approval_ip: Mapped[Optional[str]] = mapped_column(String(45), default=None)

    # Note: The manual __init__ was DELETED. MappedAsDataclass handles it automatically!

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Party(db.Model, UserMixin):
    __tablename__ = "parties"
    
    def get_id(self):
        return str(self.party_id)

    # 🔴 REQUIRED FIELDS
    party_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # REMOVED: username (We only use email now)
    
    # 🟢 OPTIONAL / DEFAULT FIELDS
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # REMOVED: role (Role is now strictly managed in UserAccount)
    first_name: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    last_name: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    phone: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    regid: Mapped[Optional[str]] = mapped_column(String(11), default=None)
    address: Mapped[Optional[str]] = mapped_column(Text, default=None)
    city: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    district: Mapped[Optional[str]] = mapped_column(String(50), default=None)

    # 🔗 RELATIONS
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="party", default_factory=list)
    
    # ADDED: The missing 1-to-1 link back to UserAccount
    account: Mapped[Optional["UserAccount"]] = relationship(
        "UserAccount", 
        back_populates="party", 
        uselist=False, 
        cascade="all, delete-orphan", 
        default=None
    )

# ================================================================
# 💰 THE ERP PRICING ENGINE (New)
# ================================================================

class PriceRecord(db.Model, MappedAsDataclass):
    """
    Standalone Pricing Entity.
    Can be a simple Kelebek import or a highly surgical EMEK cost breakdown.
    """
    __tablename__ = 'price_records'

    price_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    
    # What is being priced? (Links conceptually to CatalogProduct or Kelebek item code)
    entity_code: Mapped[str] = mapped_column(String(100), index=True) # e.g., "POZ-101" or Kelebek "URK"
    
    # Context (Whose price is it?)
    supplier: Mapped[str] = mapped_column(String(100), default="Kelebek") # Supplier A, B, or 'Internal'
    price_type: Mapped[str] = mapped_column(String(50), default="cost") # 'cost', 'sell', 'procurement'
    
    # Temporal Validity (When is it valid?)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Scale (For what quantity?)
    min_quantity: Mapped[float] = mapped_column(Float, default=1.0)
    
    # --- SURGICAL COST BREAKDOWN ---
    base_material_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0) # Malzeme Tutarı
    base_labor_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0) # İşçilik Tutarı
    logistics_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    general_expenses_pct: Mapped[float] = mapped_column(Float, default=0.0) # 5.0 = 5%
    profit_margin_pct: Mapped[float] = mapped_column(Float, default=0.0)    # 15.0 = 15%
    tax_rate_pct: Mapped[float] = mapped_column(Float, default=20.0)        # 20.0 = 20%
    
    currency: Mapped[str] = mapped_column(String(10), default="TRY")

    # The Final Computed Number (Cached for fast quoting/reporting)
    final_unit_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)

    # RELATIONS: 1 PriceRecord -> Many OrderItems
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="price_record", init=False, default_factory=list)


# ================================================================
# 👥 ARKHON PLATFORM (Arkhon)
# ================================================================

class ProjectTypology(db.Model, MappedAsDataclass):
    """Handles B2B Multi-Unit Projects (e.g., T1 = 16 Units, T2 = 9 Units)"""
    __tablename__ = 'project_typologies'

    typology_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)
    
    name: Mapped[str] = mapped_column(String(50)) # e.g., "T1" or "Villa"
    description: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    # RELATIONS: 1 Typology -> Many OrderItems | Many Typologies -> 1 Order
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="typology", default_factory=list, cascade="all, delete-orphan")
    order: Mapped["Order"] = relationship("Order", back_populates="typologies", init=False)


class CatalogProduct(db.Model, MappedAsDataclass):
    """
    Standard products database (Appliances, Countertops, Sinks).
    """
    __tablename__ = 'catalog_products'

    product_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False) 
    brand: Mapped[str] = mapped_column(String(100), nullable=False) 
    product_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    default_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), default=None)  


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

    # RELATIONS: Core Order Hub
    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="orders", default=None)
    typologies: Mapped[List["ProjectTypology"]] = relationship("ProjectTypology", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    quotes: Mapped[List["Quote"]] = relationship("Quote", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    preferences: Mapped[Optional["ProjectPreference"]] = relationship("ProjectPreference", back_populates="order", default=None, init=False, cascade="all, delete-orphan")


class OrderItem(db.Model, MappedAsDataclass):
    """
    Arkhon Order Item Model (Kelebek Furniture Spec & EMEK Construction Items)
    """
    __tablename__ = 'order_items'

    item_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id'), init=False)
    typology_id: Mapped[Optional[int]] = mapped_column(ForeignKey('project_typologies.typology_id', ondelete="SET NULL"), default=None)
    
    # THE ERP PRICING LINK (Replaces raw 'fiyat')
    price_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey('price_records.price_id', ondelete="SET NULL"), default=None)

    # Base Identification
    pozno: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    urk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None) 
    ura: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None) 
    
    # Quantities & Units
    adet: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    brm: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)

    # Dimensions
    byt_x: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    byt_y: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    byt_z: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    
    is_visible_on_quote: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(50), default='Furniture') 
    accessory_image_path: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    # Specifics & Colors
    ozk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)
    oza: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    rnk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)
    rna: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    govdernk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)
    govderna: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    konfigurasyon: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    konfigurasyonXML: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    nitelikdetay: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="items", init=False)
    typology: Mapped[Optional["ProjectTypology"]] = relationship("ProjectTypology", back_populates="items", init=False, default=None)
    price_record: Mapped[Optional["PriceRecord"]] = relationship("PriceRecord", back_populates="order_items", init=False, default=None)


class Quote(db.Model, MappedAsDataclass):
    """Tracks Quote versions, ProSAP pricing, and legally binding customer approvals."""
    __tablename__ = 'quotes'

    quote_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id'), init=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    quote_category: Mapped[str] = mapped_column(String(50), default='Furniture')
    
    access_token: Mapped[str] = mapped_column(String(64), default_factory=lambda: uuid.uuid4().hex, unique=True)
    
    list_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    tax_rate: Mapped[float] = mapped_column(Float, default=20.0)
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    
    validity_days: Mapped[int] = mapped_column(Integer, default=15)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text, default=None)
    delivery_type: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    delivery_place: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    
    special_notes: Mapped[Optional[str]] = mapped_column(Text, default=None) 
    
    status: Mapped[str] = mapped_column(String(20), default='draft') # draft, sent, approved, rejected
    approval_text: Mapped[Optional[str]] = mapped_column(Text, default=None) 
    approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    approval_ip: Mapped[Optional[str]] = mapped_column(String(50), default=None) 
    
    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="quotes", init=False)
    installments: Mapped[List["PaymentInstallment"]] = relationship(
        "PaymentInstallment",
        back_populates="quote", 
        default_factory=list, 
        init=False, 
        cascade="all, delete-orphan"
    )


class ProjectPreference(db.Model, MappedAsDataclass):
    """Müşteri ve Sipariş Takip Formu (Preferences Chart)."""
    __tablename__ = 'project_preferences'

    pref_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)

    model_name: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    front_color: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    body_color: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    plinth_detail: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    handle_code: Mapped[Optional[str]] = mapped_column(String(50), default=None) 
    glass_color: Mapped[Optional[str]] = mapped_column(String(50), default=None) 

    led_strip: Mapped[bool] = mapped_column(Boolean, default=False)
    spotlight: Mapped[bool] = mapped_column(Boolean, default=False)

    cutlery_tray: Mapped[Optional[str]] = mapped_column(String(255), default=None) 
    trash_bin: Mapped[Optional[str]] = mapped_column(String(255), default=None) 
    mechanisms: Mapped[Optional[str]] = mapped_column(Text, default=None) 
    
    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="preferences", init=False)


class PaymentInstallment(db.Model, MappedAsDataclass):
    """Ödeme Planı (Payment Schedule for Contracts)."""
    __tablename__ = 'payment_installments'

    installment_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    quote_id: Mapped[int] = mapped_column(ForeignKey('quotes.quote_id', ondelete="CASCADE"), init=False)

    date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    method: Mapped[str] = mapped_column(String(50), default=None) 
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    status: Mapped[str] = mapped_column(String(20), default='Bekliyor') 

    # RELATIONS:
    quote: Mapped["Quote"] = relationship("Quote", back_populates="installments", init=False)


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

    course_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    course_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
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

    # RELATIONS: Core Course Hub
    lessons: Mapped[List["Lesson"]] = relationship('Lesson', back_populates='course', cascade='all, delete-orphan', order_by='Lesson.order', default_factory=list)
    learning_outcomes: Mapped[List["LearningOutcome"]] = relationship('LearningOutcome', back_populates='course', cascade='all, delete-orphan', order_by='LearningOutcome.id', default_factory=list)
    assessment_formats: Mapped[List["AssessmentFormat"]] = relationship('AssessmentFormat', back_populates='course', cascade='all, delete-orphan', order_by='AssessmentFormat.id', default_factory=list)
    tools: Mapped[List["Tool"]] = relationship('Tool', back_populates='course', cascade='all, delete-orphan', order_by='Tool.id', default_factory=list)

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

    lesson_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.course_id', ondelete="CASCADE"), nullable=False, index=True)
    lesson_title: Mapped[str] = mapped_column(String(200), nullable=False)
    
    content: Mapped[Optional[str]] = mapped_column(Text, default=None)
    duration: Mapped[int] = mapped_column(Integer, default=60)
    order: Mapped[int] = mapped_column(Integer, default=1)
    activity_type: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    assignment_description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    materials_needed: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_date: Mapped[datetime] = mapped_column(DateTime, default_factory=datetime.utcnow)

    # RELATIONS: Many Lessons -> 1 Course | Many Lessons <-> Many Learning Outcomes
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

    # RELATIONS: Many Learning Outcomes -> 1 Course | Many Outcomes <-> Many Lessons
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

    # RELATIONS: Many AssessmentFormats -> 1 Course
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

    # RELATIONS: Many Tools -> 1 Course
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