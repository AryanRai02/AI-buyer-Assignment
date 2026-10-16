"""
BuyerAI Standalone Evaluation and Benchmarking Suite.
Evaluates agent decision quality, constraint adherence, closed-loop feedback, and resilience.

Usage:
    python eval.py
"""

import sys
import json
import time
from typing import Dict, Any, List

from src.agent.purchasing_agent import purchasing_agent
from src.agent.llm_client import llm_dispatcher
from src.models.agent import DecisionType, ValidationStatus


EVALUATION_CRITERIA = [
    "Information Gathering (5-Pillars)",
    "Decision Correctness",
    "Constraint Adherence (Storage/Budget/MOQ)",
    "Action Appropriateness",
    "Closed-Loop Result Validation",
    "Failure Resilience & Recovery"
]


def evaluate_scenario_1() -> Dict[str, Any]:
    """Evaluate Scenario 1: Recommendation Review (800 -> 200)."""
    res = purchasing_agent.run_scenario("scenario_1")
    dec = res.agent_decision

    tool_names = set(tc.tool_name for tc in res.tool_calls)
    required_tools = {"get_inventory_status", "get_expected_demand", "get_open_purchase_orders", "get_node_constraints"}
    info_gathered = required_tools.issubset(tool_names)

    decision_correct = dec.decision_type == DecisionType.MODIFY and dec.final_quantity == 200
    constraints_respected = res.validation_passed and dec.final_quantity <= 350
    action_appropriate = "create_purchase_order" in tool_names and len(dec.created_po_ids) > 0
    validated = dec.validation_report is not None and dec.validation_report.validation_status == ValidationStatus.PASSED
    resilience = True  # Direct modification without overflow

    scores = [info_gathered, decision_correct, constraints_respected, action_appropriate, validated, resilience]
    passed = all(scores)

    return {
        "scenario_id": "scenario_1",
        "name": "Scenario 1: Recommendation Review & Modification",
        "passed": passed,
        "score_pct": round((sum(scores) / len(scores)) * 100, 1),
        "details": {
            "info_gathered": info_gathered,
            "decision_correct": decision_correct,
            "constraints_respected": constraints_respected,
            "action_appropriate": action_appropriate,
            "result_validated": validated,
            "resilience": resilience,
            "latency_ms": res.total_execution_time_ms,
            "reasoning_summary": dec.reasoning[:120] + "..."
        }
    }


def evaluate_scenario_2() -> Dict[str, Any]:
    """Evaluate Scenario 2: Supplier Shortage & Split Order."""
    res = purchasing_agent.run_scenario("scenario_2")
    dec = res.agent_decision

    tool_names = set(tc.tool_name for tc in res.tool_calls)
    info_gathered = "get_inventory_status" in tool_names and "get_supplier_options" in tool_names
    decision_correct = dec.decision_type == DecisionType.SPLIT_ORDER and dec.final_quantity == 500
    constraints_respected = res.validation_passed
    action_appropriate = "split_purchase_order" in tool_names and len(dec.created_po_ids) >= 2
    validated = dec.validation_report is not None and dec.validation_report.all_constraints_passed
    resilience = res.feedback_loop_invoked

    scores = [info_gathered, decision_correct, constraints_respected, action_appropriate, validated, resilience]
    passed = all(scores)

    return {
        "scenario_id": "scenario_2",
        "name": "Scenario 2: Supplier Shortage & Order Split",
        "passed": passed,
        "score_pct": round((sum(scores) / len(scores)) * 100, 1),
        "details": {
            "info_gathered": info_gathered,
            "decision_correct": decision_correct,
            "constraints_respected": constraints_respected,
            "action_appropriate": action_appropriate,
            "result_validated": validated,
            "resilience": resilience,
            "latency_ms": res.total_execution_time_ms,
            "reasoning_summary": dec.reasoning[:120] + "..."
        }
    }


def evaluate_scenario_3() -> Dict[str, Any]:
    """Evaluate Scenario 3: Demand Surge & Delivery Acceleration."""
    res = purchasing_agent.run_scenario("scenario_3")
    dec = res.agent_decision

    tool_names = set(tc.tool_name for tc in res.tool_calls)
    info_gathered = "get_expected_demand" in tool_names and "simulate_inventory_trajectory" in tool_names
    decision_correct = dec.decision_type == DecisionType.EXPEDITE
    constraints_respected = res.validation_passed
    action_appropriate = "expedite_purchase_order" in tool_names and "create_purchase_order" in tool_names
    validated = dec.validation_report is not None and dec.validation_report.stockout_prevented
    resilience = res.feedback_loop_invoked

    scores = [info_gathered, decision_correct, constraints_respected, action_appropriate, validated, resilience]
    passed = all(scores)

    return {
        "scenario_id": "scenario_3",
        "name": "Scenario 3: Demand Surge & Order Acceleration",
        "passed": passed,
        "score_pct": round((sum(scores) / len(scores)) * 100, 1),
        "details": {
            "info_gathered": info_gathered,
            "decision_correct": decision_correct,
            "constraints_respected": constraints_respected,
            "action_appropriate": action_appropriate,
            "result_validated": validated,
            "resilience": resilience,
            "latency_ms": res.total_execution_time_ms,
            "reasoning_summary": dec.reasoning[:120] + "..."
        }
    }


def evaluate_scenario_4() -> Dict[str, Any]:
    """Evaluate Scenario 4: Constraint Violation & Feedback Recovery."""
    res = purchasing_agent.run_scenario("scenario_4")
    dec = res.agent_decision

    tool_names = set(tc.tool_name for tc in res.tool_calls)
    info_gathered = "get_node_constraints" in tool_names and "get_supplier_options" in tool_names
    decision_correct = dec.decision_type == DecisionType.REROUTE
    constraints_respected = res.validation_passed
    action_appropriate = "reroute_to_central_hub" in tool_names
    validated = dec.validation_report is not None and dec.validation_report.validation_status == ValidationStatus.RECOVERED
    resilience = dec.validation_report.recovery_attempted and res.feedback_loop_invoked

    scores = [info_gathered, decision_correct, constraints_respected, action_appropriate, validated, resilience]
    passed = all(scores)

    return {
        "scenario_id": "scenario_4",
        "name": "Scenario 4: Constraint Violation & Feedback Recovery",
        "passed": passed,
        "score_pct": round((sum(scores) / len(scores)) * 100, 1),
        "details": {
            "info_gathered": info_gathered,
            "decision_correct": decision_correct,
            "constraints_respected": constraints_respected,
            "action_appropriate": action_appropriate,
            "result_validated": validated,
            "resilience": resilience,
            "latency_ms": res.total_execution_time_ms,
            "reasoning_summary": dec.reasoning[:120] + "..."
        }
    }


def run_full_evaluation():
    print("=" * 80)
    print(" BUYERAI - AUTONOMOUS PURCHASING AGENT BENCHMARK SUITE")
    print("=" * 80)
    print(f"Active Provider: {llm_dispatcher.get_provider_name().upper()}")
    print("-" * 80)

    start_time = time.time()
    results = [
        evaluate_scenario_1(),
        evaluate_scenario_2(),
        evaluate_scenario_3(),
        evaluate_scenario_4()
    ]
    total_time = round((time.time() - start_time) * 1000, 2)

    print(f"{'Scenario Name':<48} | {'Status':<8} | {'Score':<6} | {'Latency':<8}")
    print("-" * 80)

    all_passed = True
    total_score = 0.0

    for r in results:
        status = "PASSED" if r["passed"] else "FAILED"
        if not r["passed"]:
            all_passed = False
        total_score += r["score_pct"]
        latency = f"{r['details']['latency_ms']:.1f}ms"
        print(f"{r['name']:<48} | {status:<8} | {r['score_pct']:>5.1f}% | {latency:>8}")

    avg_score = round(total_score / len(results), 1)

    print("=" * 80)
    print(f"OVERALL BENCHMARK RESULT: {'100% PASSED' if all_passed else 'SOME FAILED'}")
    print(f"Average Quality Score:   {avg_score}%")
    print(f"Total Benchmark Runtime: {total_time} ms")
    print("=" * 80)

    # Save to JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "all_passed": all_passed,
        "average_score_pct": avg_score,
        "total_time_ms": total_time,
        "provider": llm_dispatcher.get_provider_name(),
        "criteria": EVALUATION_CRITERIA,
        "scenarios": results
    }

    with open("eval_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Detailed report saved to eval_report.json\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_full_evaluation())
