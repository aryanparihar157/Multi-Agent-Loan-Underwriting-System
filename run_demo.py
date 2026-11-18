"""
Interactive Runner & Trace Visualizer for Multi-Agent Loan Underwriting.
Executes all test scenarios and outputs detailed multi-agent traces.
"""
from __future__ import annotations

import json
from pathlib import Path
from agents.underwriting_manager import UnderwritingManager
from models.schemas import DecisionEnum


def print_banner(text: str) -> None:
    line = "=" * 80
    print(f"\n{line}\n  {text}\n{line}")


def print_section(title: str) -> None:
    print(f"\n--- {title} " + "-" * (75 - len(title)))


def format_currency(val: float | None) -> str:
    return f"${val:,.2f}" if val is not None else "N/A"


def run_all_scenarios():
    base_dir = Path(__file__).resolve().parent
    bureau_path = base_dir / "data" / "bureau_records.json"
    apps_path = base_dir / "data" / "sample_applications.json"
    run_log_path = base_dir / "run_log.md"

    # Reset or prepare run_log header
    header = (
        "# Multi-Agent Loan Underwriting System - Execution Run Log\n\n"
        "> **Architecture**: Manager-Worker Delegation  \n"
        "> **Framework**: Semantic Kernel  \n"
        "> **Course**: CSE476 Agentic AI and Intelligent Automation (Task 2 / Project 2)  \n"
        "> **Rules**: Reducing-balance EMI (deterministic), Stated 40% income cap, In-memory Bureau Store.  \n\n"
        "---\n"
    )
    with open(run_log_path, "w", encoding="utf-8") as f:
        f.write(header)

    manager = UnderwritingManager(
        annual_interest_rate=10.5,
        bureau_data_path=str(bureau_path),
        run_log_path=str(run_log_path),
    )

    with open(apps_path, "r", encoding="utf-8") as f:
        scenarios_data = json.load(f)

    scenario_labels = {
        "scenario_1_sanction": "SCENARIO 1: Ideal Prime Applicant (Expected: SANCTION)",
        "scenario_2_decline_affordability": "SCENARIO 2: High Debt / Excessive EMI (Expected: DECLINE + COUNTER-OFFER)",
        "scenario_3_refer_missing_income": "SCENARIO 3: Incomplete Document / Missing Income (Expected: REFER / HALT)",
        "scenario_4_decline_credit_risk": "SCENARIO 4: Bad Credit History / Past Defaults (Expected: DECLINE)",
    }

    print_banner("CSE476 CA2: MULTI-AGENT LOAN UNDERWRITING SYSTEM DEMO")
    print(f"Loaded {len(scenarios_data)} test scenarios.")
    print("Coordination: Manager-Worker Delegation | Memory: Shared In-Memory Blackboard")

    for key, app_dict in scenarios_data.items():
        title = scenario_labels.get(key, key)
        print_banner(title)

        print_section("1. INCOMING APPLICATION PAYLOAD")
        print(f"  • Applicant ID     : {app_dict.get('applicant_id')}")
        print(f"  • Applicant Name   : {app_dict.get('applicant_name')}")
        print(f"  • Monthly Income   : {format_currency(app_dict.get('monthly_income'))}")
        print(f"  • Existing EMIs    : {format_currency(app_dict.get('existing_emis'))}")
        print(f"  • Requested Amount : {format_currency(app_dict.get('requested_amount'))}")
        print(f"  • Requested Tenure : {app_dict.get('tenure_months')} months")
        print(f"  • Purpose          : {app_dict.get('purpose')}")

        print_section("2. MULTI-AGENT PIPELINE EXECUTION")
        record = manager.evaluate_application(app_dict)

        for step_idx, trace in enumerate(record.agent_trace, 1):
            symbol = "✓" if trace.status in ("SUCCESS", "PASS") else ("!" if trace.status == "INITIALIZED" else "✗")
            print(f"  [{step_idx}] [{symbol}] Agent: {trace.agent_name:<22} Action: {trace.action}")
            print(f"      Tool Called: {trace.tool_used}")

        print_section("3. UNDERWRITING DECISION & SYNTHESIS")
        dec = record.decision.value if record.decision else "UNKNOWN"
        badge = "🟢 [SANCTIONED]" if dec == "SANCTION" else ("🔴 [DECLINED]" if dec == "DECLINE" else "🟡 [REFERRED]")

        print(f"  Decision Outcome     : {badge}")
        print(f"  Computed Monthly EMI : {format_currency(record.computed_monthly_emi)}")
        if record.emi_to_income_ratio is not None:
            print(f"  EMI to Income Ratio  : {record.emi_to_income_ratio:.1%} (Cap: 40.0%)")
        print(f"  Affordability Check  : {record.affordability_verdict or 'N/A'}")
        if record.bureau_profile:
            print(f"  Bureau Score / Tier  : CIBIL {record.bureau_profile.cibil_score} ({record.credit_risk_level})")

        if record.counter_offer and record.counter_offer.eligible_for_counter_offer:
            print("\n  [Group-of-3 Add-on: Counter-Offer Proposals]:")
            print(f"    - Max Eligible Loan Amount : {format_currency(record.counter_offer.max_eligible_loan_amount)} (EMI: {format_currency(record.counter_offer.max_amount_emi)})")
            if record.counter_offer.extended_tenure_months:
                print(f"    - Extended Tenure Option   : {record.counter_offer.extended_tenure_months} months (New EMI: {format_currency(record.counter_offer.extended_tenure_emi)})")
            print(f"    - Guidance Note            : {record.counter_offer.recommendation_note}")

        print("\n  Underwriting Justification (One Paragraph):")
        print(f"  \"{record.one_paragraph_justification}\"")

    print_banner("ALL SCENARIOS EVALUATED. FULL LOG APPENDED TO run_log.md")


if __name__ == "__main__":
    run_all_scenarios()
