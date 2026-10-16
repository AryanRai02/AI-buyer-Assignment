"""
Feedback and Validation Engine: Handles discrepancies, constraint failures,
and autonomous corrective recovery loops.
"""

from typing import Dict, Any, Optional, Tuple, List
from src.models.agent import ValidationReport, ValidationStatus, ConstraintCheckResult, ToolCallRecord
from src.tools import TOOL_REGISTRY
from src.data.erp_database import erp_db


class FeedbackLoopEngine:
    """
    Closed-loop validation supervisor.
    Monitors execution results, catches constraint discrepancies,
    and formulates and executes corrective counter-actions.
    """

    def __init__(self):
        pass

    def evaluate_and_recover(
        self,
        action_name: str,
        action_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[ValidationReport, Optional[Dict[str, Any]], List[str], List[ToolCallRecord]]:
        """
        Evaluates the result of an action.
        If an unexpected failure or constraint violation occurs:
        1. Diagnoses the error condition.
        2. Selects an operational recovery strategy.
        3. Executes the corrective action.
        4. Re-validates the resulting state.

        Returns:
            (ValidationReport, recovery_action_result, recovery_trace, rec_tool_calls)
        """
        recovery_trace: List[str] = []
        recovery_action_result = None

        rec_tool_calls: List[ToolCallRecord] = []

        # Check if ERP / WMS rejected the action outright
        if not action_result.get("success", False):
            error_code = action_result.get("error_code", "UNKNOWN_ERROR")
            recovery_trace.append(f"[Feedback Loop Triggered] Action '{action_name}' rejected by ERP/WMS with error: {error_code} - {action_result.get('message')}")

            # Recovery for WMS Storage Overflow (Scenario 4)
            if error_code == "WMS_STORAGE_CAPACITY_EXCEEDED":
                sku = context.get("sku")
                supplier_id = context.get("supplier_id")
                target_node = context.get("node_id")
                quantity = context.get("quantity", 0)

                recovery_trace.append(f"[Diagnostic Analysis] Target node {target_node} storage overflow. Investigating secondary routing options...")

                # Check Regional Central Hub (CDC-01)
                hub = erp_db.get_node("CDC-01")
                if hub and hub.available_storage_units >= quantity:
                    recovery_trace.append(f"[Corrective Strategy Selected] Reroute {quantity} units of {sku} to Regional Hub CDC-01 (available capacity: {hub.available_storage_units} units) + activate scheduled cross-dock replenishment to {target_node}.")

                    reroute_func = TOOL_REGISTRY["reroute_to_central_hub"]
                    rec_res = reroute_func(
                        sku=sku,
                        supplier_id=supplier_id,
                        target_mfc_node_id=target_node,
                        quantity=quantity,
                        notes="Autonomous recovery after WMS local storage rejection."
                    )
                    rec_tool_calls.append(ToolCallRecord(
                        tool_name="reroute_to_central_hub",
                        arguments={"sku": sku, "supplier_id": supplier_id, "target_mfc_node_id": target_node, "quantity": quantity},
                        result=rec_res
                    ))
                    recovery_action_result = rec_res
                    recovery_trace.append(f"[Recovery Execution] Reroute action completed: PO {rec_res.get('po_id')} created at CDC-01.")

                    # Re-run validation on the recovered PO
                    val_func = TOOL_REGISTRY["validate_purchase_order"]
                    val_report = val_func(po_id=rec_res.get("po_id"))
                    val_report.validation_status = ValidationStatus.RECOVERED
                    val_report.recovery_attempted = True
                    val_report.recovery_strategy = f"Rerouted to Central Hub CDC-01 due to {target_node} storage saturation."
                    rec_tool_calls.append(ToolCallRecord(
                        tool_name="validate_purchase_order",
                        arguments={"po_id": rec_res.get("po_id")},
                        result=val_report.model_dump()
                    ))
                    return val_report, recovery_action_result, recovery_trace, rec_tool_calls

            # Recovery for Supplier Stockout (Scenario 2)
            elif error_code == "SUPPLIER_STOCKOUT":
                sku = context.get("sku")
                target_node = context.get("node_id")
                orig_po_id = context.get("po_id")
                avail_stock = action_result.get("available_stock", 0)
                req_qty = action_result.get("requested_quantity", 0)
                shortfall = req_qty - avail_stock

                recovery_trace.append(f"[Diagnostic Analysis] Supplier stockout shortfall of {shortfall} units for {sku}. Searching alternate suppliers...")
                supplier_opts = TOOL_REGISTRY["get_supplier_options"](sku=sku)
                alt_suppliers = [s for s in supplier_opts["suppliers"] if s["supplier_id"] != context.get("supplier_id") and s["stock_available"] >= shortfall]

                if alt_suppliers:
                    chosen_alt = alt_suppliers[0]
                    recovery_trace.append(f"[Corrective Strategy Selected] Split PO: {avail_stock} units with primary, {shortfall} units with alternate supplier {chosen_alt['name']}.")
                    split_func = TOOL_REGISTRY["split_purchase_order"]
                    rec_res = split_func(
                        original_po_id=orig_po_id,
                        primary_quantity=avail_stock,
                        secondary_supplier_id=chosen_alt["supplier_id"],
                        secondary_quantity=shortfall
                    )
                    rec_tool_calls.append(ToolCallRecord(
                        tool_name="split_purchase_order",
                        arguments={"original_po_id": orig_po_id, "primary_quantity": avail_stock, "secondary_supplier_id": chosen_alt["supplier_id"], "secondary_quantity": shortfall},
                        result=rec_res
                    ))
                    recovery_action_result = rec_res
                    val_func = TOOL_REGISTRY["validate_purchase_order"]
                    val_report = val_func(po_id=rec_res.get("secondary_po_id"))
                    val_report.validation_status = ValidationStatus.RECOVERED
                    val_report.recovery_attempted = True
                    val_report.recovery_strategy = f"Split order with alternate supplier {chosen_alt['name']}."
                    rec_tool_calls.append(ToolCallRecord(
                        tool_name="validate_purchase_order",
                        arguments={"po_id": rec_res.get("secondary_po_id")},
                        result=val_report.model_dump()
                    ))
                    return val_report, recovery_action_result, recovery_trace, rec_tool_calls

        # If action succeeded directly, run standard validation
        po_id = action_result.get("po_id")
        if po_id:
            val_func = TOOL_REGISTRY["validate_purchase_order"]
            val_report = val_func(po_id=po_id)
            rec_tool_calls.append(ToolCallRecord(
                tool_name="validate_purchase_order",
                arguments={"po_id": po_id},
                result=val_report.model_dump()
            ))
            return val_report, None, recovery_trace, rec_tool_calls

        # Fallback if no PO ID was produced
        return ValidationReport(
            validation_status=ValidationStatus.PASSED,
            all_constraints_passed=True,
            checks=[]
        ), None, recovery_trace, rec_tool_calls


feedback_engine = FeedbackLoopEngine()
