"""
Tool registry and schema exports for AI Purchasing Agent.
"""

from typing import Dict, Any, Callable
from src.tools.erp_tools import (
    get_inventory_status, get_expected_demand,
    get_open_purchase_orders, get_supplier_options,
    get_node_constraints
)
from src.tools.po_actions import (
    create_purchase_order_action, modify_purchase_order_action,
    split_purchase_order_action, expedite_purchase_order_action,
    reroute_to_central_hub_action, escalate_to_buyer_action
)
from src.tools.validation_tools import (
    validate_purchase_order, simulate_inventory_trajectory
)

# Registry of callable tool functions
TOOL_REGISTRY: Dict[str, Callable] = {
    "get_inventory_status": get_inventory_status,
    "get_expected_demand": get_expected_demand,
    "get_open_purchase_orders": get_open_purchase_orders,
    "get_supplier_options": get_supplier_options,
    "get_node_constraints": get_node_constraints,
    "create_purchase_order": create_purchase_order_action,
    "modify_purchase_order": modify_purchase_order_action,
    "split_purchase_order": split_purchase_order_action,
    "expedite_purchase_order": expedite_purchase_order_action,
    "reroute_to_central_hub": reroute_to_central_hub_action,
    "escalate_to_buyer": escalate_to_buyer_action,
    "validate_purchase_order": validate_purchase_order,
    "simulate_inventory_trajectory": simulate_inventory_trajectory,
}

# JSON Schema declarations for LLM function calling
TOOL_DEFINITIONS = [
    {
        "name": "get_inventory_status",
        "description": "Get current on-hand inventory, available units, safety stock, daily velocity, and runway for a SKU at a node.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Product SKU (e.g. 'SKU-101')"},
                "node_id": {"type": "string", "description": "Fulfillment Node ID (e.g. 'MFC-North')"}
            },
            "required": ["sku", "node_id"]
        }
    },
    {
        "name": "get_expected_demand",
        "description": "Calculate customer demand forecast over a planning horizon (in days) taking into account recent sales trend multipliers.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Product SKU"},
                "node_id": {"type": "string", "description": "Fulfillment Node ID"},
                "horizon_days": {"type": "integer", "description": "Planning horizon in days (default: 10)"}
            },
            "required": ["sku", "node_id"]
        }
    },
    {
        "name": "get_open_purchase_orders",
        "description": "Retrieve active in-transit purchase orders and delivery dates for a SKU and/or node.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Optional SKU filter"},
                "node_id": {"type": "string", "description": "Optional Node ID filter"}
            }
        }
    },
    {
        "name": "get_supplier_options",
        "description": "Retrieve all suppliers offering this SKU, with unit prices, lead times, MOQ, pack sizes, and reliability.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Product SKU"}
            },
            "required": ["sku"]
        }
    },
    {
        "name": "get_node_constraints",
        "description": "Check node storage capacity (max, occupied, available) and purchasing budget limits.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Fulfillment Node ID"}
            },
            "required": ["node_id"]
        }
    },
    {
        "name": "create_purchase_order",
        "description": "Create a new purchase order with a specific supplier for a given quantity at a node.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "supplier_id": {"type": "string"},
                "node_id": {"type": "string"},
                "quantity": {"type": "integer"},
                "is_expedited": {"type": "boolean", "description": "Set true for priority expedited transit"},
                "notes": {"type": "string"}
            },
            "required": ["sku", "supplier_id", "node_id", "quantity"]
        }
    },
    {
        "name": "modify_purchase_order",
        "description": "Modify the quantity of an existing open purchase order.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string", "description": "Purchase order ID (e.g. 'PO-1001')"},
                "new_quantity": {"type": "integer", "description": "Updated quantity"},
                "notes": {"type": "string"}
            },
            "required": ["po_id", "new_quantity"]
        }
    },
    {
        "name": "split_purchase_order",
        "description": "Split an order between a primary supplier and a secondary supplier when the primary faces a stock shortage.",
        "parameters": {
            "type": "object",
            "properties": {
                "original_po_id": {"type": "string"},
                "primary_quantity": {"type": "integer"},
                "secondary_supplier_id": {"type": "string"},
                "secondary_quantity": {"type": "integer"},
                "notes": {"type": "string"}
            },
            "required": ["original_po_id", "primary_quantity", "secondary_supplier_id", "secondary_quantity"]
        }
    },
    {
        "name": "expedite_purchase_order",
        "description": "Upgrade an existing PO to expedited emergency delivery to prevent stockout.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string"}
            },
            "required": ["po_id"]
        }
    },
    {
        "name": "reroute_to_central_hub",
        "description": "Reroute purchase order to Central Hub (CDC) to avoid local store storage overflow, and schedule cross-dock transfers.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "supplier_id": {"type": "string"},
                "target_mfc_node_id": {"type": "string"},
                "quantity": {"type": "integer"},
                "notes": {"type": "string"}
            },
            "required": ["sku", "supplier_id", "target_mfc_node_id", "quantity"]
        }
    },
    {
        "name": "escalate_to_buyer",
        "description": "Escalate to human buyer when policy thresholds are exceeded or an irreconcilable conflict arises.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "node_id": {"type": "string"},
                "reason": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["sku", "node_id", "reason", "options"]
        }
    },
    {
        "name": "validate_purchase_order",
        "description": "Run closed-loop verification on a PO against storage constraints, budget authorization, supplier MOQ, and stockout prevention.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "string"}
            },
            "required": ["po_id"]
        }
    },
    {
        "name": "simulate_inventory_trajectory",
        "description": "Simulate future day-by-day inventory balances, identifying stockout days and lost sales.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "node_id": {"type": "string"},
                "horizon_days": {"type": "integer"}
            },
            "required": ["sku", "node_id"]
        }
    }
]
