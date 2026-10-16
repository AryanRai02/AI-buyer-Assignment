"""
Agent decision, execution trace, tool calling, and validation models.
"""

import time
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    ACCEPT = "ACCEPT"              # Accept recommendation as is
    MODIFY = "MODIFY"              # Modify quantity / supplier / node
    REJECT = "REJECT"              # Reject recommendation with justification
    SPLIT_ORDER = "SPLIT_ORDER"    # Split across multiple suppliers or delivery dates
    EXPEDITE = "EXPEDITE"          # Expedite existing or new purchase order
    REROUTE = "REROUTE"            # Reroute to secondary facility / hub
    ESCALATE = "ESCALATE"          # Escalate to human buyer with structured recommendations


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"        # Initial validation failed, agent corrective action succeeded
    REQUIRES_OVERRIDE = "REQUIRES_OVERRIDE"


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    latency_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: time.strftime("%H:%M:%S"))


class ConstraintCheckResult(BaseModel):
    constraint_name: str          # e.g. "Storage Capacity", "Daily Budget", "Supplier MOQ", "Stockout Risk"
    passed: bool
    threshold_value: Any
    actual_value: Any
    margin: Optional[float] = None
    severity: str = "ERROR"       # "INFO", "WARNING", "ERROR"
    message: str


class ValidationReport(BaseModel):
    validation_status: ValidationStatus
    all_constraints_passed: bool
    checks: List[ConstraintCheckResult] = Field(default_factory=list)
    erp_confirmation: Optional[Dict[str, Any]] = None
    projected_runway_days: float = 0.0
    stockout_prevented: bool = True
    storage_utilization_pct: float = 0.0
    budget_impact_usd: float = 0.0
    error_details: Optional[str] = None
    recovery_attempted: bool = False
    recovery_strategy: Optional[str] = None


class AgentDecision(BaseModel):
    decision_type: DecisionType
    sku: str
    node_id: str
    recommended_quantity: int
    final_quantity: int
    selected_supplier_id: str
    reasoning: str
    factors_considered: List[str] = Field(default_factory=list)
    actions_taken: List[str] = Field(default_factory=list)
    validation_report: Optional[ValidationReport] = None
    human_approval_required: bool = False
    escalation_reason: Optional[str] = None
    created_po_ids: List[str] = Field(default_factory=list)


class ScenarioExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"EXEC-{uuid.uuid4().hex[:8].upper()}")
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    scenario_id: str
    scenario_name: str
    prompt: str
    agent_decision: AgentDecision
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    reasoning_trace: List[str] = Field(default_factory=list)
    validation_passed: bool
    feedback_loop_invoked: bool = False
    total_execution_time_ms: float = 0.0
    custom_inputs: Optional[Dict[str, Any]] = None
