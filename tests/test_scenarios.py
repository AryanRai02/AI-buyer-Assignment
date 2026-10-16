"""
Automated End-to-End Test Suite for All 4 Purchasing Scenarios.
"""

import pytest
from src.agent.purchasing_agent import purchasing_agent
from src.models.agent import DecisionType, ValidationStatus


def test_scenario_1_recommendation_review():
    """
    Scenario 1: System recommends 800 units of Oat Milk for MFC-North.
    Expected:
    - Agent investigates inventory (220), open PO (150), demand (450), and available storage (350).
    - Detects that 800 violates storage capacity (350 available) and over-purchases.
    - Modifies order to 200 units (satisfying MOQ of 200 and fitting safely in storage).
    - Validation passes.
    """
    result = purchasing_agent.run_scenario("scenario_1")

    assert result.scenario_id == "scenario_1"
    decision = result.agent_decision

    assert decision.decision_type == DecisionType.MODIFY
    assert decision.recommended_quantity == 800
    assert decision.final_quantity == 200
    assert result.validation_passed is True
    assert decision.validation_report is not None
    assert decision.validation_report.validation_status == ValidationStatus.PASSED

    # Verify tool calls were made during investigation
    tool_names = [tc.tool_name for tc in result.tool_calls]
    assert "get_inventory_status" in tool_names
    assert "get_expected_demand" in tool_names
    assert "get_open_purchase_orders" in tool_names
    assert "get_node_constraints" in tool_names
    assert "create_purchase_order" in tool_names
    assert "validate_purchase_order" in tool_names


def test_scenario_2_supplier_shortage_split_order():
    """
    Scenario 2: Supplier notifies that only 250 of 500 units can be supplied.
    Expected:
    - Agent discovers low inventory runway (1.2 days).
    - Locates alternate supplier with stock and fast lead time.
    - Splits PO: 250 with primary, 250 with alternate supplier.
    - Creates secondary PO and validates both.
    """
    result = purchasing_agent.run_scenario("scenario_2")

    assert result.scenario_id == "scenario_2"
    decision = result.agent_decision

    assert decision.decision_type == DecisionType.SPLIT_ORDER
    assert decision.final_quantity == 500
    assert len(decision.created_po_ids) >= 2
    assert result.validation_passed is True
    assert result.feedback_loop_invoked is True

    tool_names = [tc.tool_name for tc in result.tool_calls]
    assert "split_purchase_order" in tool_names
    assert "validate_purchase_order" in tool_names


def test_scenario_3_demand_surge_expedited_delivery():
    """
    Scenario 3: Actual sales surge 3.67x (110 units/day).
    Expected:
    - Agent simulates trajectory: stockout imminent on Day 1 before PO arrives on Day 6.
    - Evaluates expedited freight option (1 day lead time).
    - Expedites PO-301.
    - Re-simulates trajectory: stockout averted (0 stockout days).
    """
    result = purchasing_agent.run_scenario("scenario_3")

    assert result.scenario_id == "scenario_3"
    decision = result.agent_decision

    assert decision.decision_type == DecisionType.EXPEDITE
    assert result.validation_passed is True
    assert decision.validation_report.stockout_prevented is True

    tool_names = [tc.tool_name for tc in result.tool_calls]
    assert "expedite_purchase_order" in tool_names
    assert "simulate_inventory_trajectory" in tool_names
    assert "validate_purchase_order" in tool_names


def test_scenario_4_constraint_violation_and_feedback_recovery():
    """
    Scenario 4: Storage constraint prevents direct execution of 600 bulk units at MFC-South.
    Expected:
    - Direct dock reception is rejected by WMS due to capacity saturation (100 units space).
    - Feedback loop intercepts rejection and diagnoses root cause.
    - Autonomously executes recovery by rerouting to Regional Central Hub (CDC-01) with 13,000 capacity.
    - Validation status is RECOVERED with all constraints passing.
    """
    result = purchasing_agent.run_scenario("scenario_4")

    assert result.scenario_id == "scenario_4"
    decision = result.agent_decision

    assert decision.decision_type == DecisionType.REROUTE
    assert result.validation_passed is True
    assert result.feedback_loop_invoked is True
    assert decision.validation_report.validation_status == ValidationStatus.RECOVERED
    assert decision.validation_report.recovery_attempted is True
