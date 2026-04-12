from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean
from sqlalchemy import Enum
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import (Mapped, MappedAsDataclass, mapped_column,
                            relationship)

from crminaec.core.models import db  # Import your existing SQLAlchemy instance


# 1. Define the trust levels
class PriceSource(enum.Enum):
    MANUAL = "Manual Entry"         # 100% Reliable
    PROSAP_SYNC = "ProSAP Direct"   # 95% Reliable
    INFERRED = "System Inferred"    # 50-80% Reliable
    LEGACY = "MS Access Import"     # 20% Reliable
# ==============================================================================
# 1. Define Item FIRST so Pylance knows exactly what it is.
# Note the addition of `MappedAsDataclass`
# ==============================================================================
class Item(db.Model, MappedAsDataclass):
    """The universal recursive object: Can be a raw screw, a cabinet, or a whole kitchen."""
    __tablename__ = 'emek_items'

    item_id: Mapped[int] = mapped_column(primary_key=True, init=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str] = mapped_column(String(100), default="Generic")
    # THE SWITCH: True = Just a classification folder. False = A real physical/priced item.
    is_category: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    
    # --- NEW: Categorization ---
    product_group: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None) # maps to 'ug'
    product_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)  # maps to 'utk'
    is_configurable: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # --- NEW: Physical Properties ---
    uom: Mapped[str] = mapped_column(String(20), default="adet") # Unit of Measure (brm)
    dim_x: Mapped[float] = mapped_column(Float, default=0.0) # Width
    dim_y: Mapped[float] = mapped_column(Float, default=0.0) # Height
    dim_z: Mapped[float] = mapped_column(Float, default=0.0) # Depth

    # 'raw_material', 'assembly', 'service', 'project'
    item_type: Mapped[str] = mapped_column(String(50), default="raw_material") 
    
    # If it's a raw material, this is the cost. If it's an assembly, this should be 0.
    base_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # --- PRESENTATION & HYBRID DATA (The "Franke" Strategy) ---
    image_path: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    manufacturer_url: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    
    # JSON field for unlimited flexible attributes (e.g., {"Power": "2000W", "Color": "Inox"})
    technical_specs: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)

    # --- RECURSIVE ARCHITECTURE ---
    # We use strings ("ItemComposition") here because it is defined further down
    children_links: Mapped[List["ItemComposition"]] = relationship(
        "ItemComposition", 
        foreign_keys="ItemComposition.parent_id",
        back_populates="parent_item",
        cascade="all, delete-orphan",
        default_factory=list
    )
    # The New Intelligence Columns
    price_source: Mapped[PriceSource] = mapped_column(SQLEnum(PriceSource), default=PriceSource.LEGACY)
    reliability_score: Mapped[int] = mapped_column(Integer, default=20)
    base_cost: Mapped[float] = mapped_column(Float, default=0.0)

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
        
        # NEW LOGIC: Check if this child is already linked!
        for link in self.children_links:
            if link.child_id == child_item.item_id:
                # Just add the quantities together and stop
                link.quantity += float(qty)
                return

        # If we got here, it's a brand new link
        # CHANGE 'parent' to 'parent_item' and 'child' to 'child_item'
        new_link = ItemComposition(
            parent_item=self, 
            child_item=child_item, 
            quantity=float(qty)
        )
        self.children_links.append(new_link)


# ==============================================================================
# 2. Define ItemComposition SECOND. 
# Because Item is already defined, Mapped[Item] works natively!
# ==============================================================================
class ItemComposition(db.Model, MappedAsDataclass):
    """The associative table linking a Parent Item to its Child Components with quantities."""
    __tablename__ = 'emek_item_compositions'

    parent_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete="CASCADE"), primary_key=True, init=False)
    child_id: Mapped[int] = mapped_column(ForeignKey('emek_items.item_id', ondelete="CASCADE"), primary_key=True, init=False)
    
    # NO QUOTES needed for Item anymore! Pylance sees it right above.
    parent_item: Mapped[Item] = relationship("Item", foreign_keys=[parent_id], back_populates="children_links")
    child_item: Mapped[Item] = relationship("Item", foreign_keys=[child_id])

    quantity: Mapped[float] = mapped_column(Float, default=1.0)
