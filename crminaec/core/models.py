import uuid
from datetime import datetime, timezone
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
class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
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
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

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
    
    # Soft Delete & Archiving
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

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

class PriceRecord(db.Model):
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
    valid_from: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(timezone.utc))
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

class ProjectTypology(db.Model):
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


class CatalogProduct(db.Model):
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


class Order(db.Model):
    __tablename__ = 'orders'

    order_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    
    party_id: Mapped[Optional[int]] = mapped_column(ForeignKey('parties.party_id'), default=None)
    offer_number: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), default=None)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_plan: Mapped[Optional[str]] = mapped_column(Text, default=None)
    date: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(timezone.utc))
    
    # Lead / Pre-Sales Fields
    project_type: Mapped[str] = mapped_column(String(50), default='Kitchen') # Kitchen, Home Solutions, Architectural
    measurement_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    info_docs_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    info_docs_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    
    # Installation & After-Sales Milestones
    factory_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None) # Expected arrival from Kelebek
    installation_appointment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    kitchen_installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    countertop_installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    appliance_installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    handover_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    # RELATIONS: Core Order Hub
    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="orders", default=None)
    typologies: Mapped[List["ProjectTypology"]] = relationship("ProjectTypology", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    quotes: Mapped[List["Quote"]] = relationship("Quote", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    preferences: Mapped[Optional["ProjectPreference"]] = relationship("ProjectPreference", back_populates="order", default=None, init=False, cascade="all, delete-orphan")
    attachments: Mapped[List["OrderAttachment"]] = relationship("OrderAttachment", back_populates="order", default_factory=list, cascade="all, delete-orphan")
    issues: Mapped[List["CustomerIssue"]] = relationship("CustomerIssue", back_populates="order", default_factory=list, cascade="all, delete-orphan")


class CustomerIssue(db.Model):
    """Müşteri Şikayetleri ve Satış Sonrası Destek (After-Sales Support)."""
    __tablename__ = 'customer_issues'

    issue_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default='Açık') # Açık, İncelemede, Çözüldü
    priority: Mapped[str] = mapped_column(String(20), default='Normal') # Düşük, Normal, Acil (Low, Normal, Urgent)
    
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    
    reported_date: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(timezone.utc))
    investigation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    solution_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="issues", init=False)

class OrderAttachment(db.Model):
    """Stores files like measurements, signed contracts with semantic renaming."""
    __tablename__ = 'order_attachments'

    attachment_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)

    original_filename: Mapped[str] = mapped_column(String(255))
    semantic_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50)) # image or document
    context: Mapped[str] = mapped_column(String(50), default='Measurement')
    upload_date: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(timezone.utc))

    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="attachments", init=False)

class OrderItem(db.Model):
    """
    Arkhon Order Item Model (Kelebek Furniture Spec & EMEK Construction Items)
    """
    __tablename__ = 'order_items'

    item_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)
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


class Quote(db.Model):
    """Tracks Quote versions, ProSAP pricing, and legally binding customer approvals."""
    __tablename__ = 'quotes'

    quote_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)
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


class ProjectPreference(db.Model):
    """Müşteri ve Sipariş Takip Formu (Preferences Chart)."""
    __tablename__ = 'project_preferences'

    pref_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete="CASCADE"), init=False)

    model_name: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    front_color: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    body_color: Mapped[Optional[str]] = mapped_column(String(100), default=None) 
    handle_code: Mapped[Optional[str]] = mapped_column(String(50), default=None) 
    cabinet_grouping_notes: Mapped[Optional[str]] = mapped_column(Text, default=None) 

    # Baza (Plinth) Specifics
    plinth_height: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    plinth_material: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    plinth_color: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # Glazed Doors Specifics
    glazed_door_model: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    glazed_door_frame_color: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    glazing_type: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # Lighting & Sensors
    light_cab_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    light_cab_led: Mapped[Optional[str]] = mapped_column(String(50), default=None) # Yok, Tek Yan, Çift Yan
    light_counter_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    light_counter_led: Mapped[bool] = mapped_column(Boolean, default=False)
    light_bt_led: Mapped[bool] = mapped_column(Boolean, default=False)
    sensor_dimmer: Mapped[bool] = mapped_column(Boolean, default=False)
    sensor_door: Mapped[bool] = mapped_column(Boolean, default=False)
    light_control_wall: Mapped[bool] = mapped_column(Boolean, default=False)
    light_control_switch: Mapped[bool] = mapped_column(Boolean, default=False)

    # Accessories
    cutlery_tray: Mapped[Optional[str]] = mapped_column(String(255), default=None) 
    trash_bin: Mapped[Optional[str]] = mapped_column(String(255), default=None) 
    mechanisms: Mapped[Optional[str]] = mapped_column(Text, default=None) 
    
    # Designer Checklist (Appliances)
    appliance_refrigerator: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    appliance_dishwasher: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    appliance_washing_machine: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    appliance_oven_mw: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # RELATIONS:
    order: Mapped["Order"] = relationship("Order", back_populates="preferences", init=False)


class PaymentInstallment(db.Model):
    """Ödeme Planı (Payment Schedule for Contracts)."""
    __tablename__ = 'payment_installments'

    installment_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    quote_id: Mapped[int] = mapped_column(ForeignKey('quotes.quote_id', ondelete="CASCADE"), init=False)

    date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    method: Mapped[str] = mapped_column(String(50), default=None) 
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    status: Mapped[str] = mapped_column(String(20), default='Bekliyor') 
    
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(100), default=None) # Receipt or Wire Transfer ID

    # RELATIONS:
    quote: Mapped["Quote"] = relationship("Quote", back_populates="installments", init=False)