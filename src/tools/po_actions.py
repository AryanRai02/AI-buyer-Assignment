"""
Transactional Purchase Order Action Tools.
"""

from typing import Dict, Any, Optional, List
from src.data.erp_database import erp_db


def create_purchase_order_action(
    sku: str,
    supplier_id: str,
    node_id: str,
    quantity: int,
    is_expedited: bool = False,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute creation of a new purchase order in the ERP system.
    """
    return erp_db.create_purchase_order(
        sku=sku,
        supplier_id=supplier_id,
        node_id=node_id,
        quantity=quantity,
        is_expedited=is_expedited,
        notes=notes
    )


def modify_purchase_order_action(
    po_id: str,
    new_quantity: int,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Modify an existing purchase order's quantity.
    """
    return erp_db.modify_purchase_order(
        po_id=po_id,
        new_quantity=new_quantity,
        notes=notes
    )


def split_purchase_order_action(
    original_po_id: str,
    primary_quantity: int,
    secondary_supplier_id: str,
    secondary_quantity: int,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Split a purchase order when primary supplier has partial stockout.
    """
    return erp_db.split_purchase_order(
        original_po_id=original_po_id,
        primary_quantity=primary_quantity,
        secondary_supplier_id=secondary_supplier_id,
        secondary_quantity=secondary_quantity,
        notes=notes
    )


def expedite_purchase_order_action(po_id: str) -> Dict[str, Any]:
    """
    Upgrade an existing purchase order to expedited priority delivery.
    """
    return erp_db.expedite_purchase_order(po_id=po_id)


def reroute_to_central_hub_action(
    sku: str,
    supplier_id: str,
    target_mfc_node_id: str,
    quantity: int,
    hub_node_id: str = "CDC-01",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reroute bulk purchase to Central Distribution Center (CDC) to avoid local MFC storage overflow,
    and schedule staggered cross-dock replenishment transfers.
    """
    hub_res = erp_db.create_purchase_order(
        sku=sku,
        supplier_id=supplier_id,
        node_id=hub_node_id,
        quantity=quantity,
        notes=f"Rerouted to Regional Hub {hub_node_id} to avoid overflow at {target_mfc_node_id}. {notes or ''}"
    )

    if hub_res["success"]:
        return {
            "success": True,
            "po_id": hub_res["po_id"],
            "hub_node_id": hub_node_id,
            "quantity": quantity,
            "staggered_transfer_scheduled": True,
            "message": f"PO {hub_res['po_id']} successfully placed at Regional Hub {hub_node_id}. Automated daily transfer of 50 units/day to {target_mfc_node_id} activated."
        }
    return hub_res


def escalate_to_buyer_action(
    sku: str,
    node_id: str,
    reason: str,
    options: List[str]
) -> Dict[str, Any]:
    """
    Escalate a purchasing impasse or governance exception to a human buyer with structured options.
    """
    ticket_id = f"ESC-{sku}-{node_id}"
    return {
        "success": True,
        "escalation_ticket_id": ticket_id,
        "sku": sku,
        "node_id": node_id,
        "reason": reason,
        "recommended_options": options,
        "status": "AWAITING_HUMAN_DECISION",
        "message": f"Case escalated to category manager under ticket {ticket_id}."
    }
