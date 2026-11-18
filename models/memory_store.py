"""
Persistent Memory & Tracking Store for Multi-Agent Loan Underwriting.
Records every evaluated application, calculates real-time portfolio statistics,
and maintains an active registry of defaulting and high-risk applicants.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationHistoryItem(BaseModel):
    id: str
    applicant_id: str
    applicant_name: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    monthly_income: Optional[float] = None
    existing_emis: float = 0.0
    requested_amount: Optional[float] = None
    tenure_months: Optional[int] = None
    computed_monthly_emi: Optional[float] = None
    cibil_score: Optional[int] = None
    past_defaults: int = 0
    decision: str  # SANCTION, DECLINE, REFER
    decision_reason: str
    one_paragraph_justification: str
    counter_offer_proposed: bool = False
    counter_offer_max_loan: Optional[float] = None
    counter_offer_extended_tenure: Optional[int] = None


class UnderwritingMemoryStore:
    """Manages persistent loan application memory and real-time portfolio tracking."""

    def __init__(self, memory_file_path: Optional[str] = None, bureau_file_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.memory_path = Path(memory_file_path) if memory_file_path else (base_dir / "data" / "underwriting_history.json")
        self.bureau_path = Path(bureau_file_path) if bureau_file_path else (base_dir / "data" / "bureau_records.json")
        
        self.history: List[Dict[str, Any]] = []
        self._load_memory()

    def _load_memory(self) -> None:
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        else:
            self.history = []

    def _save_memory(self) -> None:
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"[MemoryStore Error] Failed to persist memory: {e}")

    def record_decision(self, record: Any) -> Dict[str, Any]:
        """Extracts facts from SharedUnderwritingRecord and stores them in persistent history."""
        app = record.application
        dec_val = record.decision.value if record.decision else "UNKNOWN"
        bureau = record.bureau_profile

        entry = {
            "id": f"EVAL-{len(self.history) + 1:04d}",
            "applicant_id": app.applicant_id,
            "applicant_name": app.applicant_name,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "monthly_income": record.extracted_monthly_income,
            "existing_emis": record.extracted_existing_emis,
            "requested_amount": record.extracted_requested_amount,
            "tenure_months": record.extracted_tenure_months,
            "computed_monthly_emi": record.computed_monthly_emi,
            "emi_to_income_ratio": record.emi_to_income_ratio,
            "cibil_score": bureau.cibil_score if bureau else None,
            "past_defaults": bureau.past_defaults if bureau else 0,
            "decision": dec_val,
            "decision_reason": record.decision_reason or "",
            "one_paragraph_justification": record.one_paragraph_justification or "",
            "counter_offer_proposed": bool(record.counter_offer and record.counter_offer.eligible_for_counter_offer),
            "counter_offer_max_loan": record.counter_offer.max_eligible_loan_amount if (record.counter_offer and record.counter_offer.eligible_for_counter_offer) else None,
            "counter_offer_extended_tenure": record.counter_offer.extended_tenure_months if (record.counter_offer and record.counter_offer.eligible_for_counter_offer) else None,
        }

        self.history.append(entry)
        self._save_memory()
        return entry

    def get_statistics(self) -> Dict[str, Any]:
        """Calculates comprehensive portfolio statistics."""
        total = len(self.history)
        sanctioned = sum(1 for h in self.history if h.get("decision") == "SANCTION")
        declined = sum(1 for h in self.history if h.get("decision") == "DECLINE")
        referred = sum(1 for h in self.history if h.get("decision") == "REFER")

        sanctioned_amount = sum(h.get("requested_amount", 0.0) or 0.0 for h in self.history if h.get("decision") == "SANCTION")
        total_requested = sum(h.get("requested_amount", 0.0) or 0.0 for h in self.history if h.get("requested_amount"))
        
        approved_emis = [h.get("computed_monthly_emi") for h in self.history if h.get("decision") == "SANCTION" and h.get("computed_monthly_emi")]
        avg_emi = round(sum(approved_emis) / len(approved_emis), 2) if approved_emis else 0.0

        scores = [h.get("cibil_score") for h in self.history if h.get("cibil_score") is not None]
        avg_cibil = round(sum(scores) / len(scores), 1) if scores else 0.0

        counter_offers_count = sum(1 for h in self.history if h.get("counter_offer_proposed"))

        # Defaulters in evaluated records
        eval_defaulters_count = len({h["applicant_id"] for h in self.history if (h.get("past_defaults") or 0) > 0})

        return {
            "total_evaluated": total,
            "sanctioned_count": sanctioned,
            "declined_count": declined,
            "referred_count": referred,
            "sanction_rate_percent": round((sanctioned / total) * 100, 1) if total > 0 else 0.0,
            "total_sanctioned_amount": round(sanctioned_amount, 2),
            "total_requested_amount": round(total_requested, 2),
            "average_approved_emi": avg_emi,
            "average_cibil_score": avg_cibil,
            "counter_offers_count": counter_offers_count,
            "evaluated_defaulters_count": eval_defaulters_count,
        }

    def get_defaulters_registry(self) -> List[Dict[str, Any]]:
        """
        Retrieves all applicants with recorded defaults from both the bureau database
        and evaluation history.
        """
        defaulters_map: Dict[str, Dict[str, Any]] = {}

        # 1. From bureau store
        if self.bureau_path.exists():
            try:
                with open(self.bureau_path, "r", encoding="utf-8") as f:
                    bureau_data = json.load(f)
                    for app_id, rec in bureau_data.items():
                        defaults = rec.get("past_defaults", 0)
                        if defaults > 0:
                            defaulters_map[app_id] = {
                                "applicant_id": app_id,
                                "applicant_name": self._lookup_name(app_id),
                                "cibil_score": rec.get("cibil_score", 0),
                                "past_defaults": defaults,
                                "active_loans": rec.get("active_loans", 0),
                                "late_payments_last_2yrs": rec.get("late_payment_count_last_2yrs", 0),
                                "credit_remarks": rec.get("credit_remarks", "Write-offs recorded in bureau store"),
                                "status": "CONFIRMED_DEFAULTER",
                                "source": "Bureau Records Database",
                            }
            except Exception:
                pass

        # 2. Cross-reference with evaluation history
        for h in self.history:
            app_id = h.get("applicant_id")
            defaults = h.get("past_defaults", 0)
            if defaults > 0 and app_id:
                if app_id not in defaulters_map:
                    defaulters_map[app_id] = {
                        "applicant_id": app_id,
                        "applicant_name": h.get("applicant_name", "Unknown"),
                        "cibil_score": h.get("cibil_score", 0),
                        "past_defaults": defaults,
                        "active_loans": 0,
                        "late_payments_last_2yrs": 0,
                        "credit_remarks": h.get("decision_reason", "Flagged in underwriting evaluation"),
                        "status": "FLAGGED_APPLICANT",
                        "source": "Application Evaluation History",
                    }
                else:
                    # Update name if known
                    if not defaulters_map[app_id].get("applicant_name") and h.get("applicant_name"):
                        defaulters_map[app_id]["applicant_name"] = h.get("applicant_name")

        return list(defaulters_map.values())

    def _lookup_name(self, app_id: str) -> str:
        name_map = {
            "APP-101": "Alice Sharma",
            "APP-102": "David Khan",
            "APP-103": "Charlie Verma",
            "APP-104": "Bob Mehta",
            "APP-105": "Franklyn Roy",
        }
        for h in self.history:
            if h.get("applicant_id") == app_id and h.get("applicant_name"):
                return h["applicant_name"]
        return name_map.get(app_id, "Registered Borrower")

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self.history))[:limit]

    def add_defaulter(self, defaulter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adds a defaulter to the persistent bureau store and updates in-memory registry."""
        app_id = defaulter_data["applicant_id"].strip().upper()
        bureau = {}
        if self.bureau_path.exists():
            try:
                with open(self.bureau_path, "r", encoding="utf-8") as f:
                    bureau = json.load(f)
            except Exception:
                bureau = {}

        name = defaulter_data.get("applicant_name", "").strip() or self._lookup_name(app_id)
        cibil = int(defaulter_data.get("cibil_score") or 550)
        defaults = max(1, int(defaulter_data.get("past_defaults") or 1))
        loans = int(defaulter_data.get("active_loans") or 0)
        late = int(defaulter_data.get("late_payments_last_2yrs") or 0)
        remarks = defaulter_data.get("credit_remarks", "").strip() or "Manually flagged defaulter; multiple delinquent credit accounts"

        record = {
            "applicant_id": app_id,
            "applicant_name": name,
            "cibil_score": cibil,
            "past_defaults": defaults,
            "active_loans": loans,
            "late_payment_count_last_2yrs": late,
            "credit_remarks": remarks,
        }
        bureau[app_id] = record
        self.bureau_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.bureau_path, "w", encoding="utf-8") as f:
            json.dump(bureau, f, indent=2)

        return record

    def remove_defaulter(self, applicant_id: str) -> bool:
        """Removes a defaulter from the persistent bureau store."""
        app_id = applicant_id.strip().upper()
        if self.bureau_path.exists():
            try:
                with open(self.bureau_path, "r", encoding="utf-8") as f:
                    bureau = json.load(f)
                if app_id in bureau:
                    del bureau[app_id]
                    with open(self.bureau_path, "w", encoding="utf-8") as f:
                        json.dump(bureau, f, indent=2)
                    return True
            except Exception:
                pass
        return False

    def clear(self) -> None:
        self.history = []
        self._save_memory()
