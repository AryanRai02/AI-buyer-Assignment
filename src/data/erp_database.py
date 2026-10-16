"""
Mock ERP and WMS Database Engine with transactional updates and validation hooks.
"""

from typing import Dict, List, Optional, Any
from copy import deepcopy
import uuid

from src.models.domain import (
    Product, Supplier, FulfillmentNode, InventoryRecord, PurchaseOrder,
    POStatus, NodeTier
)
from src.data.seed_data import (
    DEFAULT_PRODUCTS, DEFAULT_NODES, DEFAULT_SUPPLIERS,
    DEFAULT_INVENTORY, DEFAULT_POS
)


class ERPDatabase:
    """
    Transactional ERP & WMS simulation state.
    Provides idempotent resets, transactional updates, and strict constraint validation.
    """

    def __init__(self):
        self.products: Dict[str, Product] = {}
        self.nodes: Dict[str, FulfillmentNode] = {}
        self.suppliers: Dict[str, Supplier] = {}
        self.inventory: Dict[str, InventoryRecord] = {}  # key: f"{sku}:{node_id}"
        self.purchase_orders: Dict[str, PurchaseOrder] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.reset_to_seed()

    def reset_to_seed(self):
        """Reset all tables to fresh seed state."""
        self.products = {p.sku: deepcopy(p) for p in DEFAULT_PRODUCTS}
        self.nodes = {n.id: deepcopy(n) for n in DEFAULT_NODES}
        self.suppliers = {s.id: deepcopy(s) for s in DEFAULT_SUPPLIERS}
        self.inventory = {f"{i.sku}:{i.node_id}": deepcopy(i) for i in DEFAULT_INVENTORY}
        self.purchase_orders = {po.po_id: deepcopy(po) for po in DEFAULT_POS}
        self.audit_log.clear()

    # --- Query Methods ---

    def get_product(self, sku: str) -> Optional[Product]:
        return self.products.get(sku)

    def get_all_products(self) -> List[Product]:
        return list(self.products.values())

    def get_node(self, node_id: str) -> Optional[FulfillmentNode]:
        return self.nodes.get(node_id)

    def get_all_nodes(self) -> List[FulfillmentNode]:
        return list(self.nodes.values())

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        return self.suppliers.get(supplier_id)

    def get_all_suppliers(self) -> List[Supplier]:
        return list(self.suppliers.values())

    def get_suppliers_for_sku(self, sku: str) -> List[Supplier]:
        return [s for s in self.suppliers.values() if sku in s.catalog_skus]

    def get_inventory(self, sku: str, node_id: str) -> Optional[InventoryRecord]:
        return self.inventory.get(f"{sku}:{node_id}")

    def get_all_inventory(self) -> List[InventoryRecord]:
        return list(self.inventory.values())

    def get_purchase_order(self, po_id: str) -> Optional[PurchaseOrder]:
        return self.purchase_orders.get(po_id)

    def get_all_purchase_orders(self) -> List[PurchaseOrder]:
        return list(self.purchase_orders.values())

    def get_open_purchase_orders(self, sku: Optional[str] = None, node_id: Optional[str] = None) -> List[PurchaseOrder]:
        results = []
        for po in self.purchase_orders.values():
            if po.status in [POStatus.DRAFT, POStatus.SUBMITTED, POStatus.CONFIRMED, POStatus.PARTIALLY_FULFILLED, POStatus.EXPEDITED]:
                if sku and po.sku != sku:
                    continue
                if node_id and po.node_id != node_id:
                    continue
                results.append(po)
        return results

    # --- Transactional Actions & WMS/ERP Verification ---

    def create_purchase_order(
        self,
        sku: str,
        supplier_id: str,
        node_id: str,
        quantity: int,
        is_expedited: bool = False,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new PO and submits to ERP/WMS.
        Includes pre-commit and post-commit checks.
        """
        product = self.get_product(sku)
        supplier = self.get_supplier(supplier_id)
        node = self.get_node(node_id)

        if not product or not supplier or not node:
            return {
                "success": False,
                "error_code": "ENTITY_NOT_FOUND",
                "message": f"Entity missing: product={bool(product)}, supplier={bool(supplier)}, node={bool(node)}"
            }

        unit_cost = supplier.unit_cost_overrides.get(sku, product.unit_cost)
        if is_expedited:
            unit_cost += supplier.expedited_fee_per_unit

        total_cost = round(unit_cost * quantity, 2)
        lead_time = supplier.expedited_lead_time_days if is_expedited else supplier.standard_lead_time_days

        # WMS Physical Storage Capacity Verification
        if quantity > node.available_storage_units:
            return {
                "success": False,
                "error_code": "WMS_STORAGE_CAPACITY_EXCEEDED",
                "message": f"WMS Dock Rejection: Storage space at {node.name} is {node.available_storage_units} units, but requested PO requires {quantity} units.",
                "node_id": node_id,
                "available_storage": node.available_storage_units,
                "requested_quantity": quantity
            }

        # ERP Budget Verification
        if total_cost > node.remaining_budget_usd:
            return {
                "success": False,
                "error_code": "ERP_BUDGET_EXCEEDED",
                "message": f"ERP Budget Hold: Daily remaining budget is ${node.remaining_budget_usd:,.2f}, but PO requires ${total_cost:,.2f}.",
                "node_id": node_id,
                "remaining_budget": node.remaining_budget_usd,
                "requested_cost": total_cost
            }

        # Supplier Stock Check
        supplier_stock = supplier.stock_available.get(sku, 999999)
        if quantity > supplier_stock:
            return {
                "success": False,
                "error_code": "SUPPLIER_STOCKOUT",
                "message": f"Supplier {supplier.name} has only {supplier_stock} units available, requested {quantity}.",
                "supplier_id": supplier_id,
                "available_stock": supplier_stock,
                "requested_quantity": quantity
            }

        # Deduct budget & storage
        node.current_occupied_units += quantity
        node.available_storage_units -= quantity
        node.remaining_budget_usd -= total_cost

        po_id = f"PO-{uuid.uuid4().hex[:6].upper()}"
        new_po = PurchaseOrder(
            po_id=po_id,
            sku=sku,
            supplier_id=supplier_id,
            node_id=node_id,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            status=POStatus.EXPEDITED if is_expedited else POStatus.CONFIRMED,
            created_at_day=0,
            expected_delivery_day=lead_time,
            is_expedited=is_expedited,
            notes=notes or "Created by AI Purchasing Agent"
        )
        self.purchase_orders[po_id] = new_po

        # Log audit entry
        self.audit_log.append({
            "action": "CREATE_PO",
            "po_id": po_id,
            "sku": sku,
            "quantity": quantity,
            "node_id": node_id,
            "total_cost": total_cost,
            "is_expedited": is_expedited
        })

        return {
            "success": True,
            "po_id": po_id,
            "po": new_po.model_dump(),
            "message": f"Purchase order {po_id} confirmed and registered with WMS & ERP."
        }

    def modify_purchase_order(
        self,
        po_id: str,
        new_quantity: int,
        new_status: Optional[POStatus] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Modify an existing PO quantity or status."""
        po = self.purchase_orders.get(po_id)
        if not po:
            return {"success": False, "error_code": "PO_NOT_FOUND", "message": f"PO {po_id} not found"}

        node = self.get_node(po.node_id)
        quantity_diff = new_quantity - po.quantity

        if quantity_diff > 0 and node and quantity_diff > node.available_storage_units:
            return {
                "success": False,
                "error_code": "WMS_STORAGE_CAPACITY_EXCEEDED",
                "message": f"Cannot increase quantity: requires {quantity_diff} additional units, only {node.available_storage_units} space available."
            }

        # Adjust storage reservation
        if node:
            node.current_occupied_units += quantity_diff
            node.available_storage_units -= quantity_diff
            cost_diff = quantity_diff * po.unit_cost
            node.remaining_budget_usd -= cost_diff

        old_quantity = po.quantity
        po.quantity = new_quantity
        po.total_cost = round(new_quantity * po.unit_cost, 2)
        if new_status:
            po.status = new_status
        if notes:
            po.notes = (po.notes or "") + f" | {notes}"

        self.audit_log.append({
            "action": "MODIFY_PO",
            "po_id": po_id,
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "new_status": po.status.value
        })

        return {
            "success": True,
            "po_id": po_id,
            "po": po.model_dump(),
            "message": f"PO {po_id} modified from {old_quantity} to {new_quantity} units."
        }

    def split_purchase_order(
        self,
        original_po_id: str,
        primary_quantity: int,
        secondary_supplier_id: str,
        secondary_quantity: int,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handles supplier shortage by splitting:
        1. Downsizes original PO to primary_quantity.
        2. Creates secondary PO with alternate supplier for secondary_quantity.
        """
        orig_po = self.purchase_orders.get(original_po_id)
        if not orig_po:
            return {"success": False, "error_code": "PO_NOT_FOUND", "message": f"PO {original_po_id} not found"}

        # Step 1: Update original PO
        orig_modify_res = self.modify_purchase_order(
            po_id=original_po_id,
            new_quantity=primary_quantity,
            new_status=POStatus.PARTIALLY_FULFILLED,
            notes=f"Adjusted to supplier confirmed allocation: {primary_quantity} units"
        )
        if not orig_modify_res["success"]:
            return orig_modify_res

        # Step 2: Create secondary PO
        sec_res = self.create_purchase_order(
            sku=orig_po.sku,
            supplier_id=secondary_supplier_id,
            node_id=orig_po.node_id,
            quantity=secondary_quantity,
            notes=f"Split order for remainder {secondary_quantity} units from {secondary_supplier_id}. Orig: {original_po_id}"
        )

        return {
            "success": sec_res["success"],
            "original_po_id": original_po_id,
            "original_quantity": primary_quantity,
            "secondary_po_id": sec_res.get("po_id"),
            "secondary_quantity": secondary_quantity,
            "secondary_error": sec_res.get("message") if not sec_res["success"] else None,
            "message": f"Split PO executed: {primary_quantity} units with {orig_po.supplier_id}, {secondary_quantity} units with {secondary_supplier_id}."
        }

    def expedite_purchase_order(self, po_id: str) -> Dict[str, Any]:
        """Expedite an existing open PO."""
        po = self.purchase_orders.get(po_id)
        if not po:
            return {"success": False, "error_code": "PO_NOT_FOUND", "message": f"PO {po_id} not found"}

        supplier = self.get_supplier(po.supplier_id)
        if not supplier or not supplier.expedited_lead_time_days:
            return {
                "success": False,
                "error_code": "EXPEDITE_UNAVAILABLE",
                "message": f"Supplier {supplier.name if supplier else 'Unknown'} does not offer expedited shipping."
            }

        surcharge = supplier.expedited_fee_per_unit * po.quantity
        node = self.get_node(po.node_id)
        if node and surcharge > node.remaining_budget_usd:
            return {
                "success": False,
                "error_code": "INSUFFICIENT_EXPEDITE_BUDGET",
                "message": f"Cannot expedite: Surcharge ${surcharge:.2f} exceeds remaining budget ${node.remaining_budget_usd:.2f}."
            }

        po.is_expedited = True
        po.status = POStatus.EXPEDITED
        old_day = po.expected_delivery_day
        po.expected_delivery_day = supplier.expedited_lead_time_days
        po.unit_cost += supplier.expedited_fee_per_unit
        po.total_cost = round(po.quantity * po.unit_cost, 2)
        if node:
            node.remaining_budget_usd -= surcharge

        self.audit_log.append({
            "action": "EXPEDITE_PO",
            "po_id": po_id,
            "old_lead_day": old_day,
            "new_lead_day": po.expected_delivery_day,
            "surcharge": surcharge
        })

        return {
            "success": True,
            "po_id": po_id,
            "new_expected_delivery_day": po.expected_delivery_day,
            "surcharge": surcharge,
            "message": f"PO {po_id} expedited: Delivery accelerated from Day {old_day} to Day {po.expected_delivery_day}."
        }


# Global singleton instance for runtime state
erp_db = ERPDatabase()
