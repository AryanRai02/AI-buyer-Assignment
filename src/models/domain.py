"""
Domain models for retail / quick-commerce purchasing system.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NodeTier(str, Enum):
    DARK_STORE = "dark_store"           # Micro-fulfillment center (MFC)
    CENTRAL_HUB = "central_hub"         # Regional distribution center (CDC)
    STORE = "retail_store"              # Traditional retail front


class POStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    EXPEDITED = "expedited"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    DELIVERED = "delivered"


class Product(BaseModel):
    sku: str = Field(..., description="Unique Stock Keeping Unit identifier")
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category (Dairy, Beverages, Snacks, etc.)")
    unit_cost: float = Field(..., description="Standard purchasing cost per unit in USD")
    unit_price: float = Field(..., description="Retail selling price per unit in USD")
    unit_volume_cbm: float = Field(default=0.01, description="Unit physical volume in cubic meters")
    shelf_life_days: int = Field(default=30, description="Product shelf life in days")
    is_perishable: bool = Field(default=False, description="Whether item requires refrigerated cold-chain")


class Supplier(BaseModel):
    id: str = Field(..., description="Supplier unique ID")
    name: str = Field(..., description="Supplier company name")
    reliability_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Historical fulfillment reliability (0.0 - 1.0)")
    standard_lead_time_days: int = Field(..., description="Standard delivery lead time in days")
    expedited_lead_time_days: Optional[int] = Field(None, description="Expedited lead time if available")
    expedited_fee_per_unit: float = Field(default=0.0, description="Additional fee per unit for expedited shipping")
    moq: int = Field(default=100, description="Minimum Order Quantity")
    incremental_pack_size: int = Field(default=1, description="Pack batch increment (e.g. multiples of 10 or 50)")
    catalog_skus: List[str] = Field(default_factory=list, description="SKUs provided by this supplier")
    unit_cost_overrides: Dict[str, float] = Field(default_factory=dict, description="Custom unit cost per SKU")
    stock_available: Dict[str, int] = Field(default_factory=dict, description="Current stock available at supplier")


class FulfillmentNode(BaseModel):
    id: str = Field(..., description="Node ID (e.g. MFC-North, CDC-01)")
    name: str = Field(..., description="Node display name")
    tier: NodeTier = Field(default=NodeTier.DARK_STORE)
    max_storage_units: int = Field(..., description="Total warehouse capacity in units")
    current_occupied_units: int = Field(default=0, description="Currently occupied units")
    available_storage_units: int = Field(..., description="Remaining storage capacity")
    daily_budget_usd: float = Field(default=25000.0, description="Daily available purchasing budget")
    remaining_budget_usd: float = Field(default=25000.0, description="Remaining budget today")


class InventoryRecord(BaseModel):
    sku: str
    node_id: str
    on_hand_units: int
    reserved_units: int = 0
    available_units: int
    safety_stock_units: int
    reorder_point_units: int
    daily_sales_velocity: float = Field(..., description="Average daily sales units")
    recent_trend_multiplier: float = Field(default=1.0, description="Sales surge factor (1.0 = normal, 2.5 = 2.5x surge)")


class PurchaseOrder(BaseModel):
    po_id: str
    sku: str
    supplier_id: str
    node_id: str
    quantity: int
    unit_cost: float
    total_cost: float
    status: POStatus = POStatus.SUBMITTED
    created_at_day: int = 0
    expected_delivery_day: int
    is_expedited: bool = False
    notes: Optional[str] = None
    original_quantity: Optional[int] = None
