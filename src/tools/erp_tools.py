"""
ERP & Operational Information Retrieval Tools for Buyer Agent.
"""

from typing import Dict, Any, List, Optional
from src.data.erp_database import erp_db


def get_inventory_status(sku: str, node_id: str) -> Dict[str, Any]:
    """
    Retrieve on-hand stock, available inventory, safety stock, reorder point,
    daily velocity, and sales trend factor for a product at a node.
    """
    inv = erp_db.get_inventory(sku, node_id)
    if not inv:
        return {"found": False, "error": f"No inventory record for {sku} at {node_id}"}

    # Calculate current inventory runway in days
    effective_velocity = inv.daily_sales_velocity * inv.recent_trend_multiplier
    runway_days = round(inv.available_units / effective_velocity, 1) if effective_velocity > 0 else 999.0

    return {
        "found": True,
        "sku": inv.sku,
        "node_id": inv.node_id,
        "on_hand_units": inv.on_hand_units,
        "available_units": inv.available_units,
        "safety_stock_units": inv.safety_stock_units,
        "reorder_point_units": inv.reorder_point_units,
        "baseline_daily_velocity": inv.daily_sales_velocity,
        "recent_trend_multiplier": inv.recent_trend_multiplier,
        "effective_daily_demand": round(effective_velocity, 1),
        "current_runway_days": runway_days,
        "is_under_safety_stock": inv.available_units < inv.safety_stock_units
    }


def get_expected_demand(sku: str, node_id: str, horizon_days: int = 10) -> Dict[str, Any]:
    """
    Calculate projected customer demand over a given planning horizon (days),
    accounting for current trend factors (e.g. surges or seasonal shifts).
    """
    inv = erp_db.get_inventory(sku, node_id)
    if not inv:
        return {"found": False, "error": f"No demand forecast found for {sku} at {node_id}"}

    effective_velocity = inv.daily_sales_velocity * inv.recent_trend_multiplier
    baseline_total = round(inv.daily_sales_velocity * horizon_days, 1)
    effective_total = round(effective_velocity * horizon_days, 1)
    surge_delta = round(effective_total - baseline_total, 1)

    return {
        "found": True,
        "sku": sku,
        "node_id": node_id,
        "horizon_days": horizon_days,
        "baseline_daily_sales": inv.daily_sales_velocity,
        "recent_trend_multiplier": inv.recent_trend_multiplier,
        "effective_daily_demand": round(effective_velocity, 1),
        "projected_demand_total": effective_total,
        "baseline_demand_total": baseline_total,
        "surge_detected": inv.recent_trend_multiplier > 1.25,
        "surge_additional_units": max(0.0, surge_delta)
    }


def get_open_purchase_orders(sku: Optional[str] = None, node_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve all open / in-transit purchase orders for a SKU and/or fulfillment node.
    """
    pos = erp_db.get_open_purchase_orders(sku=sku, node_id=node_id)
    total_in_transit = sum(p.quantity for p in pos)

    return {
        "count": len(pos),
        "total_units_in_transit": total_in_transit,
        "purchase_orders": [p.model_dump() for p in pos]
    }


def get_supplier_options(sku: str) -> Dict[str, Any]:
    """
    Retrieve all suppliers offering this SKU, including cost, lead times, MOQ,
    expedited options, reliability score, and current supplier inventory.
    """
    suppliers = erp_db.get_suppliers_for_sku(sku)
    product = erp_db.get_product(sku)
    base_cost = product.unit_cost if product else 0.0

    options = []
    for s in suppliers:
        unit_cost = s.unit_cost_overrides.get(sku, base_cost)
        avail = s.stock_available.get(sku, 999999)
        options.append({
            "supplier_id": s.id,
            "name": s.name,
            "unit_cost": unit_cost,
            "standard_lead_time_days": s.standard_lead_time_days,
            "expedited_lead_time_days": s.expedited_lead_time_days,
            "expedited_fee_per_unit": s.expedited_fee_per_unit,
            "moq": s.moq,
            "incremental_pack_size": s.incremental_pack_size,
            "reliability_score": s.reliability_score,
            "stock_available": avail
        })

    # Sort options by lead time then cost
    options.sort(key=lambda x: (x["standard_lead_time_days"], x["unit_cost"]))

    return {
        "sku": sku,
        "supplier_count": len(options),
        "suppliers": options
    }


def get_node_constraints(node_id: str) -> Dict[str, Any]:
    """
    Retrieve physical storage and financial budget constraints for a fulfillment node.
    """
    node = erp_db.get_node(node_id)
    if not node:
        return {"found": False, "error": f"Node {node_id} not found"}

    utilization_pct = round((node.current_occupied_units / node.max_storage_units) * 100, 1)

    return {
        "found": True,
        "node_id": node.id,
        "name": node.name,
        "tier": node.tier.value,
        "max_storage_units": node.max_storage_units,
        "current_occupied_units": node.current_occupied_units,
        "available_storage_units": node.available_storage_units,
        "storage_utilization_pct": utilization_pct,
        "daily_budget_usd": node.daily_budget_usd,
        "remaining_budget_usd": node.remaining_budget_usd
    }
