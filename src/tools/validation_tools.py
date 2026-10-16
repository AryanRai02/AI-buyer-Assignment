"""
Validation and Feedback Simulation Tools for AI Purchasing Agent.
Ensures every purchasing decision adheres to hard physical, financial, and operational constraints.
"""

from typing import Dict, Any, List
from src.data.erp_database import erp_db
from src.models.agent import ValidationReport, ValidationStatus, ConstraintCheckResult


def validate_purchase_order(po_id: str, horizon_days: int = 5) -> ValidationReport:
    """
    Perform multi-constraint validation on an executed purchase order:
    1. PO existence and confirmation in ERP
    2. Warehouse storage limit invariant
    3. Node purchasing budget invariant
    4. Supplier MOQ adherence
    5. Inventory stockout prevention simulation
    """
    po = erp_db.get_purchase_order(po_id)
    if not po:
        return ValidationReport(
            validation_status=ValidationStatus.FAILED,
            all_constraints_passed=False,
            checks=[
                ConstraintCheckResult(
                    constraint_name="PO Existence",
                    passed=False,
                    threshold_value="Registered PO",
                    actual_value="NOT_FOUND",
                    severity="ERROR",
                    message=f"Purchase order {po_id} does not exist in ERP."
                )
            ],
            error_details=f"PO {po_id} not found."
        )

    product = erp_db.get_product(po.sku)
    node = erp_db.get_node(po.node_id)
    supplier = erp_db.get_supplier(po.supplier_id)
    inv = erp_db.get_inventory(po.sku, po.node_id)

    checks: List[ConstraintCheckResult] = []

    # Check 1: Supplier MOQ
    if supplier:
        moq_passed = po.quantity >= supplier.moq
        checks.append(ConstraintCheckResult(
            constraint_name="Supplier Minimum Order Quantity (MOQ)",
            passed=moq_passed,
            threshold_value=supplier.moq,
            actual_value=po.quantity,
            margin=float(po.quantity - supplier.moq),
            severity="ERROR" if not moq_passed else "INFO",
            message=f"Order quantity {po.quantity} meets supplier MOQ ({supplier.moq})" if moq_passed
                    else f"Order quantity {po.quantity} violates supplier MOQ ({supplier.moq})!"
        ))

    # Check 2: Warehouse Physical Storage
    if node:
        storage_passed = node.available_storage_units >= 0
        utilization_pct = round((node.current_occupied_units / node.max_storage_units) * 100, 1)
        checks.append(ConstraintCheckResult(
            constraint_name="Warehouse Storage Capacity",
            passed=storage_passed,
            threshold_value=node.max_storage_units,
            actual_value=node.current_occupied_units,
            margin=float(node.available_storage_units),
            severity="ERROR" if not storage_passed else "INFO",
            message=f"Storage capacity verified: {node.current_occupied_units}/{node.max_storage_units} units ({utilization_pct}% occupied, {node.available_storage_units} remaining)"
                    if storage_passed else f"STORAGE OVERFLOW: Capacity exceeded by {abs(node.available_storage_units)} units!"
        ))

    # Check 3: Budget Authorization
    if node:
        budget_passed = node.remaining_budget_usd >= 0
        checks.append(ConstraintCheckResult(
            constraint_name="Purchasing Budget Limit",
            passed=budget_passed,
            threshold_value=node.daily_budget_usd,
            actual_value=node.remaining_budget_usd,
            margin=float(node.remaining_budget_usd),
            severity="ERROR" if not budget_passed else "INFO",
            message=f"Budget approved: ${node.remaining_budget_usd:,.2f} remaining out of ${node.daily_budget_usd:,.2f}"
                    if budget_passed else f"BUDGET DEFICIT: Over-budget by ${abs(node.remaining_budget_usd):,.2f}!"
        ))

    # Check 4: Stockout Prevention Runway Simulation
    sim = simulate_inventory_trajectory(po.sku, po.node_id, horizon_days=horizon_days)
    stockout_prevented = not sim.get("stockout_detected", False)
    checks.append(ConstraintCheckResult(
        constraint_name="Stockout Prevention Invariant",
        passed=stockout_prevented,
        threshold_value="0 stockout days",
        actual_value=f"{sim.get('stockout_days', 0)} stockout days",
        severity="WARNING" if not stockout_prevented else "INFO",
        message="Stockout successfully averted across planning horizon." if stockout_prevented
                else f"Stockout risk remains: Projected stockout on Day {sim.get('first_stockout_day')}!"
    ))

    all_passed = all(c.passed for c in checks if c.severity == "ERROR")
    util_pct = (node.current_occupied_units / node.max_storage_units * 100) if node else 0.0

    return ValidationReport(
        validation_status=ValidationStatus.PASSED if all_passed else ValidationStatus.FAILED,
        all_constraints_passed=all_passed,
        checks=checks,
        erp_confirmation={
            "po_id": po.po_id,
            "status": po.status.value,
            "quantity": po.quantity,
            "total_cost": po.total_cost,
            "delivery_day": po.expected_delivery_day
        },
        projected_runway_days=sim.get("runway_days", 0.0),
        stockout_prevented=stockout_prevented,
        storage_utilization_pct=round(util_pct, 1),
        budget_impact_usd=po.total_cost,
        error_details=None if all_passed else "One or more operational constraints failed validation."
    )


def simulate_inventory_trajectory(sku: str, node_id: str, horizon_days: int = 14) -> Dict[str, Any]:
    """
    Day-by-day inventory simulation accounting for daily demand,
    safety stock, and incoming purchase order receipts.
    """
    inv = erp_db.get_inventory(sku, node_id)
    if not inv:
        return {"error": "Inventory record not found"}

    pos = erp_db.get_open_purchase_orders(sku=sku, node_id=node_id)
    daily_demand = inv.daily_sales_velocity * inv.recent_trend_multiplier

    trajectory = []
    current_stock = float(inv.available_units)
    stockout_detected = False
    first_stockout_day = None
    stockout_days_count = 0
    total_lost_sales = 0.0

    for day in range(1, horizon_days + 1):
        # Add incoming orders scheduled for this day
        incoming_today = sum(p.quantity for p in pos if p.expected_delivery_day == day)
        current_stock += incoming_today

        # Subtract day's sales
        if current_stock >= daily_demand:
            current_stock -= daily_demand
        else:
            lost = daily_demand - current_stock
            total_lost_sales += lost
            current_stock = 0.0
            stockout_days_count += 1
            if not stockout_detected:
                stockout_detected = True
                first_stockout_day = day

        trajectory.append({
            "day": day,
            "incoming_units": incoming_today,
            "demand_units": round(daily_demand, 1),
            "closing_stock": round(current_stock, 1),
            "is_stockout": current_stock == 0.0
        })

    runway = round(inv.available_units / daily_demand, 1) if daily_demand > 0 else 999.0

    return {
        "sku": sku,
        "node_id": node_id,
        "horizon_days": horizon_days,
        "daily_demand": round(daily_demand, 1),
        "runway_days": runway,
        "stockout_detected": stockout_detected,
        "first_stockout_day": first_stockout_day,
        "stockout_days": stockout_days_count,
        "total_lost_sales_units": round(total_lost_sales, 1),
        "trajectory": trajectory
    }
