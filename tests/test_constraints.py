"""
Unit tests for constraint verification logic: Storage, Budget, MOQ, Runway math.
"""

import pytest
from src.data.erp_database import erp_db
from src.tools.validation_tools import validate_purchase_order, simulate_inventory_trajectory


def setup_function():
    erp_db.reset_to_seed()


def test_storage_overflow_prevention():
    """Verify that WMS rejects PO exceeding storage limit."""
    res = erp_db.create_purchase_order(
        sku="SKU-401",
        supplier_id="SUP-401",
        node_id="MFC-South",
        quantity=300  # Node only has 100 available!
    )
    assert res["success"] is False
    assert res["error_code"] == "WMS_STORAGE_CAPACITY_EXCEEDED"


def test_budget_overrun_prevention():
    """Verify that ERP holds PO exceeding remaining daily budget."""
    node = erp_db.get_node("MFC-South")
    node.remaining_budget_usd = 50.0  # Artificially constrain budget

    res = erp_db.create_purchase_order(
        sku="SKU-401",
        supplier_id="SUP-401",
        node_id="MFC-South",
        quantity=50  # 50 * $8.50 = $425 > $50
    )
    assert res["success"] is False
    assert res["error_code"] == "ERP_BUDGET_EXCEEDED"


def test_inventory_simulation_stockout_detection():
    """Verify simulation accurately calculates stockout days when demand surges."""
    sim = simulate_inventory_trajectory(sku="SKU-305", node_id="MFC-Central", horizon_days=10)
    assert sim["stockout_detected"] is True
    assert sim["first_stockout_day"] == 1
    assert sim["total_lost_sales_units"] > 0
