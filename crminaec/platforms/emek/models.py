from __future__ import annotations

import enum
import os
import re
import unicodedata
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import (Mapped, MappedAsDataclass, mapped_column,
                            relationship)

from crminaec.core.models import db  # Import your existing SQLAlchemy instance


# ==============================================================================
# 0. ENUMS
# ==============================================================================
class PriceSource(enum.Enum):
    MANUAL = "Manual Entry"         # 100% Reliable
    PROSAP_SYNC = "ProSAP Direct"   # 95% Reliable
    INFERRED = "System Inferred"    # 50-80% Reliable
    LEGACY = "MS Access Import"     # 20% Reliable

class NodeType(enum.Enum):
    CATEGORY = "Category"
    PRODUCT = "Product"
    ACTIVITY = "Activity" # Uniclass Ac, WBS Tasks
    SPACE = "Space"       # COBie Zones/Rooms

class StandardType(enum.Enum):
    UNICLASS_2015 = "Uniclass 2015"
    MASTERFORMAT_2020 = "MasterFormat 2020"
    TR_DIGITAL_REG = "TR Digital Regulation"
    COBIE_V3 = "COBie v3"


# ==============================================================================
# 1. ITEM CROSS REFERENCE (The Semantic Layer)
# ==============================================================================
class ItemCrossReference(db.Model, MappedAsDataclass):
    __tablename__ = 'emek_item_cross_references'
    
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    
    # 🚨 FIXED: Now correctly points to emek_items.item_id
    item_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete='CASCADE'), index=True, init=False)
    
    standard_type: Mapped[StandardType] = mapped_column(Enum(StandardType), nullable=False)
    standard_code: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., "Pr_25_71_63"
    standard_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None) # e.g., "Kitchen units"
    
    # Links back to the universal node
    item: Mapped["Item"] = relationship("Item", back_populates="cross_references", init=False)


# ==============================================================================
# 2. ITEM (The Universal Node)
# ==============================================================================
class Item(db.Model, MappedAsDataclass):
    """The universal recursive object: Can be a raw screw, a cabinet, or a whole kitchen."""
    __tablename__ = 'emek_items'

    item_id: Mapped[int] = mapped_column(primary_key=True, init=False)

    # 1. Identifiers & Naming
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    
    # 🚨 FIXED: Unified syntax for Enum
    node_type: Mapped[NodeType] = mapped_column(Enum(NodeType), default=NodeType.CATEGORY)

    # 2. Formal ERP Taxonomy
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Generic")
    product_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None) # maps to 'ug'    
    product_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)  # maps to 'utk'
    uom: Mapped[str] = mapped_column(String(20), default="adet") # Unit of measure (brm)

    # THE SWITCH: True = Just a classification folder. False = A real physical/priced item.
    # 🚨 FIXED: Removed the duplicate definition of is_category
    is_category: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_configurable: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 3. Physical Properties
    dim_x: Mapped[float] = mapped_column(Float, default=0.0) # Width
    dim_y: Mapped[float] = mapped_column(Float, default=0.0) # Height
    dim_z: Mapped[float] = mapped_column(Float, default=0.0) # Depth

    # 'raw_material', 'assembly', 'service', 'project'
    item_type: Mapped[str] = mapped_column(String(50), default="raw_material") 
    
    # 4. Costing & Specs (🚨 FIXED: Removed the duplicate definitions below)
    base_cost: Mapped[float] = mapped_column(Float, default=0.0)
    price_source: Mapped[PriceSource] = mapped_column(Enum(PriceSource), default=PriceSource.MANUAL)
    reliability_score: Mapped[int] = mapped_column(Integer, default=100)
    
    # JSON field for unlimited flexible attributes (e.g., {"Power": "2000W", "Color": "Inox"})
    technical_specs: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=dict) 

    # 5. PRESENTATION & HYBRID DATA (The "Franke" Strategy)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    manufacturer_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    # --- RELATIONSHIPS ---
    
    # 1. Semantic Standards Cross-References
    cross_references: Mapped[List["ItemCrossReference"]] = relationship(
        "ItemCrossReference",
        back_populates="item",
        cascade="all, delete-orphan",
        default_factory=list
    )

    # 2. Children links (Recursive Architecture)
    children_links: Mapped[List["ItemComposition"]] = relationship(
        "ItemComposition", 
        foreign_keys="ItemComposition.parent_id",
        back_populates="parent_item",
        cascade="all, delete-orphan",
        default_factory=list
    )
    
    # 3. PDM ATTACHMENTS
    attachments: Mapped[List["ItemAttachment"]] = relationship(
        "ItemAttachment",
        back_populates="item",
        cascade="all, delete-orphan",
        default_factory=list
    )

    @property
    def total_cost(self) -> float:
        """
        Recursively calculates the total cost. 
        If is_category is True, it acts as a Phantom Node and returns 0.0.
        """
        # --- THE CIRCUIT BREAKER ---
        if self.is_category:
            return 0.0 
        
        # Start with the baseline cost of the item itself (if any)
        cost = float(self.base_cost or 0.0)
        
        # Loop through all children, recursively getting their cost * quantity
        for link in self.children_links:
            if link.child_item:
                child_cost = float(link.child_item.total_cost or 0.0)
                cost += (child_cost * float(link.quantity or 1.0))
                
        return cost

    def can_add_child(self, proposed_child: "Item") -> bool:
        """Prevents infinite recursion (e.g., adding a Cabinet into itself)."""
        if self.item_id == proposed_child.item_id:
            return False

        def contains_target(node: "Item", target_id: int) -> bool:
            if node.item_id == target_id:
                return True
            for component in node.children_links:
                if contains_target(component.child_item, target_id):
                    return True
            return False

        if contains_target(proposed_child, self.item_id):
            return False
            
        return True

    def add_component(self, child_item, qty=1.0):
        """Adds a child component, gracefully adding to the quantity if it already exists."""
        if not self.can_add_child(child_item):
            raise ValueError(f"Döngü hatası: {self.name}, {child_item.name} öğesini içeremez.")
        
        # Check if this child is already linked!
        for link in self.children_links:
            if link.child_id == child_item.item_id:
                link.quantity += float(qty)
                return

        # If brand new link
        new_link = ItemComposition(
            parent_item=self, 
            child_item=child_item, 
            quantity=float(qty)
        )
        self.children_links.append(new_link)


# ==============================================================================
# 3. ITEM COMPOSITION (BOM Link) Model
# ==============================================================================
class ItemComposition(db.Model, MappedAsDataclass):
    """The Association Object for the Bill of Materials (BOM) hierarchy."""
    __tablename__ = 'emek_item_compositions'

    parent_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete="CASCADE"), primary_key=True, init=False)
    child_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete="CASCADE"), primary_key=True, init=False)
    
    parent_item: Mapped[Item] = relationship("Item", foreign_keys=[parent_id], back_populates="children_links")
    child_item: Mapped[Item] = relationship("Item", foreign_keys=[child_id])

    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0) 
    
    # Parametric Relationship Data (e.g. {"opt1": "L"})
    optional_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=dict)


# ==============================================================================
# 4. Define ItemAttachment (The PDM Vault)
# ==============================================================================
class ItemAttachment(db.Model, MappedAsDataclass):
    """Stores files/images linked to an Item with semantic renaming."""
    __tablename__ = 'emek_item_attachments'

    attachment_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    item_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete="CASCADE"), init=False)
    
    original_filename: Mapped[str] = mapped_column(String(255))
    semantic_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50), default="document") # 'image', 'pdf', 'cad', etc.

    # Relationship back to Item
    item: Mapped["Item"] = relationship("Item", back_populates="attachments", init=False)