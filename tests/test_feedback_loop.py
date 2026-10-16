"""
Dedicated tests for closed-loop validation and error recovery handling.
"""

import pytest
from src.data.erp_database import erp_db
from src.agent.feedback_loop import feedback_engine
from src.models.agent import ValidationStatus


def setup_function():
    erp_db.reset_to_seed()


def test_feedback_recovery_from_wms_storage_rejection():
    """
    Test that when an initial PO is rejected by WMS due to storage overflow,
    the feedback engine intercepts the failure, selects CDC-01 hub rerouting,
    executes the reroute, and returns ValidationStatus.RECOVERED.
    """
    failed_action_result = {
        "success": False,
        "error_code": "WMS_STORAGE_CAPACITY_EXCEEDED",
        "message": "Storage space exceeded at MFC-South"
    }

    context = {
        "sku": "SKU-401",
        "supplier_id": "SUP-401",
        "node_id": "MFC-South",
        "quantity": 300
    }

    val_report, rec_action, rec_trace, rec_tool_calls = feedback_engine.evaluate_and_recover(
        action_name="create_purchase_order",
        action_result=failed_action_result,
        context=context
    )

    assert val_report.validation_status == ValidationStatus.RECOVERED
    assert val_report.all_constraints_passed is True
    assert val_report.recovery_attempted is True
    assert rec_action is not None
    assert rec_action["success"] is True
    assert rec_action["hub_node_id"] == "CDC-01"
    assert len(rec_trace) > 0
    assert len(rec_tool_calls) > 0


def test_feedback_recovery_from_supplier_stockout():
    """
    Test that when a supplier announces partial stockout,
    the feedback loop detects the shortfall and splits with an alternate supplier.
    """
    failed_action_result = {
        "success": False,
        "error_code": "SUPPLIER_STOCKOUT",
        "message": "Supplier only has 250 units",
        "available_stock": 250,
        "requested_quantity": 500
    }

    context = {
        "sku": "SKU-204",
        "supplier_id": "SUP-201",
        "node_id": "MFC-Central",
        "po_id": "PO-202"
    }

    val_report, rec_action, rec_trace, rec_tool_calls = feedback_engine.evaluate_and_recover(
        action_name="create_purchase_order",
        action_result=failed_action_result,
        context=context
    )

    assert val_report.validation_status == ValidationStatus.RECOVERED
    assert rec_action is not None
    assert rec_action["success"] is True
    assert rec_action["secondary_quantity"] == 250
