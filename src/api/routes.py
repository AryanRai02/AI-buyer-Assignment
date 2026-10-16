"""
FastAPI REST routes for BuyerAI Dashboard and Agent Execution.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from src.agent.purchasing_agent import purchasing_agent
from src.data.erp_database import erp_db
from src.agent.llm_client import llm_dispatcher
from src.models.agent import ScenarioExecutionResult


router = APIRouter(prefix="/api")

SCENARIOS_META = [
    {
        "id": "scenario_1",
        "title": "Scenario 1: Purchase Recommendation Review",
        "category": "Recommendation Audit",
        "description": "System recommends buying 800 units of Oat Milk. Agent investigates 5 operational pillars, discovers storage and demand constraints, and modifies the order to 200 units.",
        "difficulty": "Standard",
        "key_constraints": ["Warehouse Storage (350 max)", "Supplier MOQ (200 units)", "In-Transit POs (150 units)"]
    },
    {
        "id": "scenario_2",
        "title": "Scenario 2: Supplier Shortage & Split Order",
        "category": "Supply Disruption",
        "description": "Primary supplier notifies 50% stockout on 500-unit PO. Agent analyzes inventory runway (1.2 days), locates alternate supplier, and executes a split purchase order.",
        "difficulty": "Advanced",
        "key_constraints": ["Supplier Stockout (250 available)", "Critical Runway (1.2 days)", "Alternate Sourcing"]
    },
    {
        "id": "scenario_3",
        "title": "Scenario 3: Demand Surge & Delivery Acceleration",
        "category": "Demand Shock",
        "description": "Actual sales surge 3.67x due to local event. Agent detects imminent stockout on Day 1 and accelerates open PO via expedited freight (24h arrival).",
        "difficulty": "Advanced",
        "key_constraints": ["Sales Surge (267% increase)", "Stockout Invariant", "Expedited Transit Surcharge"]
    },
    {
        "id": "scenario_4",
        "title": "Scenario 4: Constraint Violation & Feedback Recovery",
        "category": "Closed-Loop Feedback",
        "description": "Recommends 600 bulk water units, but local dark store storage is only 100 units. Agent tests dock, catches WMS rejection, and autonomously recovers by rerouting to Regional Hub CDC-01.",
        "difficulty": "Expert",
        "key_constraints": ["Physical Storage Saturation", "WMS Dock Rejection Feedback", "Hub Rerouting & Cross-Dock"]
    }
]


@router.get("/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "active_llm_provider": llm_dispatcher.get_provider_name(),
        "erp_db_status": "connected",
        "total_products": len(erp_db.products),
        "total_nodes": len(erp_db.nodes)
    }


@router.get("/scenarios")
def list_scenarios():
    return SCENARIOS_META


class ScenarioRunRequest(BaseModel):
    custom_params: Optional[Dict[str, Any]] = None


@router.post("/run-scenario/{scenario_id}")
def run_scenario_endpoint(scenario_id: str, req: Optional[ScenarioRunRequest] = None) -> Dict[str, Any]:
    valid_ids = ["scenario_1", "scenario_2", "scenario_3", "scenario_4"]
    if scenario_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found. Choose from {valid_ids}")

    custom_params = req.custom_params if req else None
    result = purchasing_agent.run_scenario(scenario_id, custom_params=custom_params)
    return result.model_dump()


@router.post("/run-all-scenarios")
def run_all_scenarios_endpoint():
    """Run full evaluation suite across all 4 scenarios."""
    results = []
    all_passed = True
    total_time = 0.0

    for meta in SCENARIOS_META:
        res = purchasing_agent.run_scenario(meta["id"])
        results.append(res.model_dump())
        if not res.validation_passed:
            all_passed = False
        total_time += res.total_execution_time_ms

    return {
        "all_passed": all_passed,
        "scenarios_tested": len(results),
        "total_time_ms": round(total_time, 2),
        "active_provider": llm_dispatcher.get_provider_name(),
        "results": results
    }


@router.get("/state")
def get_current_state() -> Dict[str, Any]:
    return {
        "nodes": [n.model_dump() for n in erp_db.get_all_nodes()],
        "products": [p.model_dump() for p in erp_db.get_all_products()],
        "suppliers": [s.model_dump() for s in erp_db.get_all_suppliers()],
        "inventory": [i.model_dump() for i in erp_db.get_all_inventory()],
        "purchase_orders": [po.model_dump() for po in erp_db.get_all_purchase_orders()],
        "audit_log": erp_db.audit_log[-20:]
    }


@router.post("/reset")
def reset_state() -> Dict[str, Any]:
    erp_db.reset_to_seed()
    return {"status": "success", "message": "ERP & WMS state successfully reset to seed data."}


class ApprovalRequest(BaseModel):
    ticket_id: str
    approved: bool
    notes: str = ""


@router.post("/approve-escalation")
def approve_escalation(req: ApprovalRequest):
    return {
        "success": True,
        "ticket_id": req.ticket_id,
        "status": "APPROVED" if req.approved else "REJECTED",
        "notes": req.notes,
        "message": f"Escalation {req.ticket_id} marked as {'APPROVED' if req.approved else 'REJECTED'} by buyer."
    }
