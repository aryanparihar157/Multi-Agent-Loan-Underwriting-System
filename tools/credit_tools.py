"""
Credit-History Tools.
Queries small in-memory prior-record store and evaluates credit bureau risk parameters.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Dict, Optional
from semantic_kernel.functions import kernel_function

# Embedded fallback in-memory prior record store
IN_MEMORY_BUREAU_STORE: Dict[str, Dict[str, Any]] = {
    "APP-101": {
        "applicant_id": "APP-101",
        "cibil_score": 785,
        "past_defaults": 0,
        "active_loans": 1,
        "late_payment_count_last_2yrs": 0,
        "credit_remarks": "Prime credit standing; impeccable repayment record with nationalized banks.",
    },
    "APP-102": {
        "applicant_id": "APP-102",
        "cibil_score": 590,
        "past_defaults": 2,
        "active_loans": 3,
        "late_payment_count_last_2yrs": 4,
        "credit_remarks": "Sub-prime profile; 2 write-offs recorded in last 36 months, multiple overdue alerts.",
    },
    "APP-103": {
        "applicant_id": "APP-103",
        "cibil_score": 710,
        "past_defaults": 0,
        "active_loans": 0,
        "late_payment_count_last_2yrs": 0,
        "credit_remarks": "Clean credit history, low credit card utilization, no delinquencies.",
    },
    "APP-104": {
        "applicant_id": "APP-104",
        "cibil_score": 740,
        "past_defaults": 0,
        "active_loans": 2,
        "late_payment_count_last_2yrs": 0,
        "credit_remarks": "Near-prime profile, good credit mix, payments consistent.",
    },
    "APP-105": {
        "applicant_id": "APP-105",
        "cibil_score": 640,
        "past_defaults": 1,
        "active_loans": 2,
        "late_payment_count_last_2yrs": 1,
        "credit_remarks": "Borderline credit profile, 1 overdue settlement in 2024.",
    },
}


class CreditTools:
    """Credit Assessment Plugin for Semantic Kernel."""

    def __init__(self, data_file: Optional[str] = None):
        self.data_file = data_file
        self.store = dict(IN_MEMORY_BUREAU_STORE)
        if data_file and Path(data_file).exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    self.store.update(file_data)
            except Exception:
                pass

    def add_or_update_record(self, record_data: Dict[str, Any]) -> None:
        """Adds or updates an applicant record in memory and persists to disk."""
        app_id = record_data["applicant_id"].strip()
        self.store[app_id] = record_data
        if self.data_file:
            try:
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(self.store, f, indent=2)
            except Exception as e:
                print(f"[CreditTools Error] Failed to persist bureau record: {e}")

    def remove_record(self, applicant_id: str) -> bool:
        """Removes an applicant record from memory and disk."""
        app_id = applicant_id.strip()
        if app_id in self.store:
            del self.store[app_id]
            if self.data_file:
                try:
                    with open(self.data_file, "w", encoding="utf-8") as f:
                        json.dump(self.store, f, indent=2)
                except Exception:
                    pass
            return True
        return False

    @kernel_function(
        name="query_bureau_records",
        description="Looks up the applicant's prior credit history and bureau profile in the in-memory store.",
    )
    def query_bureau_records(
        self,
        applicant_id: Annotated[str, "The unique applicant ID (e.g., 'APP-101')."],
    ) -> Dict[str, Any]:
        """Tool 1: Looks up the applicant in the in-memory prior record store."""
        cleaned_id = applicant_id.strip()
        record = self.store.get(cleaned_id)
        if record:
            return {
                "found": True,
                "applicant_id": cleaned_id,
                "cibil_score": record["cibil_score"],
                "past_defaults": record.get("past_defaults", 0),
                "active_loans": record.get("active_loans", 0),
                "late_payments_last_2yrs": record.get("late_payment_count_last_2yrs", 0),
                "credit_remarks": record.get("credit_remarks", "No remarks"),
            }

        # Fallback profile for applicants without previous records on file
        return {
            "found": False,
            "applicant_id": cleaned_id,
            "cibil_score": 700,
            "past_defaults": 0,
            "active_loans": 0,
            "late_payments_last_2yrs": 0,
            "credit_remarks": "First-time borrower with clean baseline file.",
        }

    @kernel_function(
        name="assess_credit_risk",
        description="Assesses credit risk, red flags, and bureau score against policy minimums.",
    )
    def assess_credit_risk(
        self,
        cibil_score: Annotated[int, "Bureau CIBIL credit score (300-900)."],
        past_defaults: Annotated[int, "Count of recorded defaults or settlements."],
        late_payments: Annotated[int, "Count of late payment delinquency flags in last 2 years."] = 0,
    ) -> Dict[str, Any]:
        """
        Tool 2: Red-flag check and risk classification.
        Policy Rules:
          - Any past defaults (>0) -> Red Flag (FAIL)
          - CIBIL score < 650 -> High Risk (FAIL)
          - Late payments > 2 -> Red Flag (FAIL)
        """
        red_flags: list[str] = []

        if past_defaults > 0:
            red_flags.append(f"Recorded {past_defaults} major default(s)/write-off(s) in credit history.")
        if cibil_score < 650:
            red_flags.append(f"CIBIL score ({cibil_score}) is below standard cut-off of 650.")
        if late_payments > 2:
            red_flags.append(f"Excessive 30+ DPD delinquencies ({late_payments} occurrences).")

        passed = len(red_flags) == 0

        if cibil_score >= 750 and passed:
            risk_tier = "PRIME"
        elif cibil_score >= 680 and passed:
            risk_tier = "NEAR_PRIME"
        elif passed:
            risk_tier = "MODERATE"
        else:
            risk_tier = "HIGH_RISK"

        justification = (
            f"Credit profile meets underwriting criteria (Score: {cibil_score}, Tier: {risk_tier}, 0 defaults)."
            if passed
            else f"Credit check failed due to red flags: {' '.join(red_flags)}"
        )

        return {
            "credit_check_passed": passed,
            "cibil_score": cibil_score,
            "risk_tier": risk_tier,
            "has_red_flags": not passed,
            "red_flags": red_flags,
            "justification": justification,
        }
