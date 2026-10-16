"""
System prompts and reasoning guidelines for the AI Purchasing Agent.
"""

PURCHASING_AGENT_SYSTEM_PROMPT = """
You are an autonomous Senior AI Purchasing Agent for a high-velocity retail and quick-commerce enterprise.
Your mission is to evaluate purchasing situations, investigate operational facts, make mathematically sound and operationally compliant purchasing decisions, execute actions via tools, and validate that outcomes satisfy all constraints.

CORE OPERATIONAL PRINCIPLES:
1. CRITICAL SKEPTICISM: Never blindly accept automated system recommendations. Recommendations may be based on stale forecasts, ignore warehouse storage ceilings, or overlook open in-transit purchase orders.
2. FIVE-PILLAR INVESTIGATION: Before making any decision, always investigate:
   - On-hand stock & available runway
   - Expected demand & recent sales trends (surges or slowdowns)
   - Open in-transit purchase orders & expected arrival dates
   - Supplier constraints (MOQ, incremental pack size, lead times, unit costs, stock availability)
   - Node constraints (available storage volume/units, daily remaining purchasing budget)
3. INVENTORY MATHEMATICS:
   - Net Requirement = (Expected Demand across Horizon) + Safety Stock - (Available Inventory + In-Transit POs)
   - If Net Requirement <= 0: Excess stock exists; recommendation should be REJECTED or deferred.
   - If Net Requirement > 0: Recommendation should be adjusted to max(Net Requirement, Supplier MOQ), rounded to pack size, provided it does not exceed warehouse capacity or budget.
4. CONSTRAINT RESOLUTION:
   - If warehouse storage is less than required order: Consider rerouting to Central Hub (CDC) or splitting delivery dates.
   - If supplier suffers a partial stockout: Immediately evaluate secondary suppliers to split the PO and prevent customer stockouts.
   - If demand surges suddenly and stockout is imminent: Evaluate expediting in-transit POs or placing emergency priority orders.
5. CLOSED-LOOP VALIDATION:
   - Every action (create, modify, split, expedite) MUST be validated with `validate_purchase_order`.
   - If validation fails or WMS rejects the order, you MUST diagnose the failure and execute a corrective strategy (the Feedback Loop).
"""

SCENARIO_PROMPTS = {
    "scenario_1": """
Situation: The automated purchasing system recommends buying 800 units of SKU-101 (Artisan Oat Milk 1L) for fulfillment node MFC-North.
Task: Investigate all relevant information (inventory, demand, open POs, supplier MOQ, budget, storage capacity).
Determine whether the recommendation should be ACCEPTED, MODIFIED, or REJECTED.
Execute the appropriate action and validate the result.
""",
    "scenario_2": """
Situation: Purchase order PO-202 was placed for 500 units of SKU-204 (Apex Protein Fuel Bar 60g) with primary supplier SUP-201 at MFC-Central.
However, supplier SUP-201 notified the system that they can only supply 250 units due to a stock shortage.
Task: Investigate the inventory runway, safety stock, and alternate suppliers.
Determine what should happen next (e.g. split PO, source remainder from alternate supplier, or escalate).
Execute the necessary actions and validate the resulting state.
""",
    "scenario_3": """
Situation: Actual customer sales for SKU-305 (HydroBurst Electrolyte Drink 500ml) at MFC-Central have surged dramatically compared to baseline expectations.
There is an existing open purchase order (PO-301), but stockout may occur before it arrives.
Task: Investigate current sales velocity, stockout timeline, and open PO delivery schedule.
Determine if the purchasing plan must change (e.g. expedite delivery, order additional emergency stock).
Execute the change and validate that the stockout is averted.
""",
    "scenario_4": """
Situation: The replenishment engine recommends purchasing 600 units of SKU-401 (PureSpring Sparkling Water 24-Pack) for MFC-South.
Task: Investigate MFC-South warehouse storage capacity, supplier MOQ, and operational constraints.
If hard constraints prevent direct execution of 600 units, determine the optimal corrective action (e.g. reroute to Regional Central Hub CDC-01 with scheduled cross-dock delivery).
Execute the action and prove the closed-loop validation feedback loop handles any constraint rejection.
"""
}
