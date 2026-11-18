"""
Underwriting Manager Module.
Coordinates specialist agents using Manager-Worker Delegation architecture.
Shared in-memory record carries state; halts and refers when income is missing.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from semantic_kernel import Kernel
from models.schemas import (
    DecisionEnum,
    LoanApplication,
    SharedUnderwritingRecord,
)
from models.memory_store import UnderwritingMemoryStore
from agents.document_agent import DocumentAgent
from agents.emi_agent import EMIComputationAgent
from agents.credit_agent import CreditHistoryAgent
from agents.affordability_agent import AffordabilityAgent
from agents.counter_offer_agent import CounterOfferAgent


class UnderwritingManager:
    """
    Manager Agent orchestrating specialist workers via Manager-Worker delegation.
    Guarantees:
      - Shared applicant record maintained strictly in-memory.
      - Never hallucinates or assumes missing income: halts and refers immediately.
      - EMI is computed via deterministic tool, not model inference.
      - Applies stated income rule (EMI <= 40% net income).
      - If declined on affordability, engages Counter-Offer worker.
      - Produces decision, computed EMI, affordability verdict, and 1-paragraph justification.
      - Maintains an append-only run log.
    """

    def __init__(
        self,
        annual_interest_rate: float = 10.5,
        bureau_data_path: Optional[str] = None,
        run_log_path: str = "run_log.md",
        kernel: Optional[Kernel] = None,
        use_llm: bool = True,
        llm_provider: str = "local",
        local_model_name: str = "qwen3:8b",
        local_endpoint: str = "http://localhost:11434/v1",
    ):
        self.annual_interest_rate = annual_interest_rate
        self.run_log_path = run_log_path
        self.kernel = kernel or Kernel()
        self.use_llm = use_llm
        self.llm_provider = llm_provider
        self.local_model_name = local_model_name
        self.local_endpoint = local_endpoint

        # Instantiate specialist worker agents
        self.doc_agent = DocumentAgent(kernel=self.kernel)
        self.emi_agent = EMIComputationAgent(kernel=self.kernel)
        self.credit_agent = CreditHistoryAgent(kernel=self.kernel, data_file=bureau_data_path)
        self.afford_agent = AffordabilityAgent(kernel=self.kernel)
        self.counter_offer_agent = CounterOfferAgent(kernel=self.kernel)

        # Persistent Memory & Tracking Store
        self.memory_store = UnderwritingMemoryStore(bureau_file_path=bureau_data_path)

    def evaluate_application(self, application_input: Dict[str, Any] | LoanApplication) -> SharedUnderwritingRecord:
        """
        Coordinates the entire underwriting pipeline through delegation to specialists.
        """
        if isinstance(application_input, dict):
            app = LoanApplication(**application_input)
        else:
            app = application_input

        # Initialize shared in-memory blackboard record
        record = SharedUnderwritingRecord(
            application=app,
            annual_interest_rate=self.annual_interest_rate,
        )

        record.add_trace(
            agent_name="UnderwritingManager",
            action="initiate_underwriting",
            tool_used="manager_worker_orchestrator",
            status="INITIALIZED",
            details={"applicant_id": app.applicant_id, "applicant_name": app.applicant_name},
        )

        # -------------------------------------------------------------
        # STAGE 1: Delegate to Document Specialist
        # -------------------------------------------------------------
        record = self.doc_agent.process(record)

        # Mandatory CA2 check: Halt and refer when income is missing rather than assume it
        if not record.is_valid or record.extracted_monthly_income is None or record.extracted_monthly_income <= 0:
            record.decision = DecisionEnum.REFER
            record.decision_reason = (
                f"Halting underwriting pipeline: applicant income is missing or invalid. "
                f"Errors: {', '.join(record.validation_errors) if record.validation_errors else 'Missing income'}."
            )
            record.one_paragraph_justification = (
                f"The loan application for {app.applicant_name} (Applicant ID: {app.applicant_id}) "
                f"has been REFERRED for manual underwriting review. In accordance with credit policy, "
                f"the automated pipeline halted immediately at the Document Verification stage because "
                f"verified monthly income was absent from the application payload. Rather than making "
                f"an assumption or hallucinating an income figure, system governance mandates referring "
                f"the case to human operations for physical salary slip / bank statement verification."
            )
            self._append_to_run_log(record)
            self.memory_store.record_decision(record)
            return record

        # -------------------------------------------------------------
        # STAGE 2: Delegate to EMI Computation Specialist (Deterministic)
        # -------------------------------------------------------------
        record = self.emi_agent.process(record)

        # -------------------------------------------------------------
        # STAGE 3: Delegate to Credit-History Specialist (Bureau Records)
        # -------------------------------------------------------------
        record = self.credit_agent.process(record)

        if not record.credit_check_passed:
            record.decision = DecisionEnum.DECLINE
            record.decision_reason = f"Credit check failed: {record.credit_justification}"
            record.one_paragraph_justification = (
                f"The loan application for {app.applicant_name} (Applicant ID: {app.applicant_id}) "
                f"has been DECLINED due to credit risk factors. Bureau lookup revealed a credit standing "
                f"that breaches underwriting thresholds (CIBIL Score: {record.bureau_profile.cibil_score if record.bureau_profile else 'N/A'}, "
                f"Risk Tier: {record.credit_risk_level}). Specific grounds: {record.credit_justification}. "
                f"The application fails minimum risk acceptance standards."
            )
            self._append_to_run_log(record)
            self.memory_store.record_decision(record)
            return record

        # -------------------------------------------------------------
        # STAGE 4: Delegate to Affordability Specialist (40% Income Rule)
        # -------------------------------------------------------------
        record = self.afford_agent.process(record)

        if not record.affordability_passed:
            # ---------------------------------------------------------
            # STAGE 5: Group-of-3 Add-on -> Engage Counter-Offer Worker
            # ---------------------------------------------------------
            record = self.counter_offer_agent.process(record)

            record.decision = DecisionEnum.DECLINE
            record.decision_reason = (
                f"Affordability threshold breached: computed EMI (${record.computed_monthly_emi:,.2f}) "
                f"represents {record.emi_to_income_ratio:.1%} of monthly income, exceeding the 40% limit."
            )
            
            counter_note = (
                record.counter_offer.recommendation_note
                if record.counter_offer
                else "No viable counter-offer available."
            )

            record.one_paragraph_justification = (
                f"The loan application for {app.applicant_name} (Applicant ID: {app.applicant_id}) "
                f"has been DECLINED as requested because the monthly EMI of ${record.computed_monthly_emi:,.2f} "
                f"exceeds the bank's 40% stated income affordability ceiling for a verified income of "
                f"${record.extracted_monthly_income:,.2f} (maximum allowable EMI is ${record.max_allowed_emi:,.2f}). "
                f"However, the Counter-Offer Worker synthesized the following viable alternatives: {counter_note}"
            )
            self._append_to_run_log(record)
            self.memory_store.record_decision(record)
            return record

        # -------------------------------------------------------------
        # STAGE 6: All Criteria Met -> SANCTION
        # -------------------------------------------------------------
        record.decision = DecisionEnum.SANCTION
        record.decision_reason = (
            f"All underwriting criteria met: EMI (${record.computed_monthly_emi:,.2f}) is within 40% "
            f"income rule ({record.emi_to_income_ratio:.1%}), credit score is {record.bureau_profile.cibil_score if record.bureau_profile else '700+'} with 0 defaults."
        )
        record.one_paragraph_justification = (
            f"The loan application for {app.applicant_name} (Applicant ID: {app.applicant_id}) "
            f"is hereby SANCTIONED. The requested loan of ${record.extracted_requested_amount:,.2f} "
            f"over {record.extracted_tenure_months} months at {record.annual_interest_rate}% annual interest "
            f"yields a reducing-balance monthly EMI of ${record.computed_monthly_emi:,.2f}. Based on verified monthly "
            f"income of ${record.extracted_monthly_income:,.2f}, the proposed EMI consumes {record.emi_to_income_ratio:.1%} "
            f"of income, satisfying the 40% stated income rule (max permitted EMI: ${record.max_allowed_emi:,.2f}). "
            f"Bureau verification confirmed a {record.credit_risk_level} credit profile (CIBIL: {record.bureau_profile.cibil_score if record.bureau_profile else '700+'}) "
            f"with zero historical defaults."
        )

        if self.use_llm:
            self._enrich_with_local_agent(record)

        self._append_to_run_log(record)
        self.memory_store.record_decision(record)
        return record

    def get_statistics(self) -> Dict[str, Any]:
        """Returns aggregate underwriting metrics."""
        return self.memory_store.get_statistics()

    def get_history(self, limit: int = 100) -> list:
        """Returns recent underwriting evaluation history."""
        return self.memory_store.get_history(limit=limit)

    def get_defaulters_registry(self) -> list:
        """Returns all confirmed and flagged defaulting applicants."""
        return self.memory_store.get_defaulters_registry()

    def add_defaulter(self, defaulter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adds or updates a defaulter record across memory and credit tools."""
        rec = self.memory_store.add_defaulter(defaulter_data)
        self.credit_agent.add_defaulter_record(rec)
        return rec

    def remove_defaulter(self, applicant_id: str) -> bool:
        """Removes a defaulter record from memory and credit tools."""
        removed_mem = self.memory_store.remove_defaulter(applicant_id)
        removed_cred = self.credit_agent.remove_defaulter_record(applicant_id)
        return removed_mem or removed_cred

    def _enrich_with_local_agent(self, record: SharedUnderwritingRecord) -> None:
        """Invokes local Qwen LLM agent to synthesize the final executive justification."""
        try:
            from openai import OpenAI
            client = OpenAI(base_url=self.local_endpoint, api_key="ollama", timeout=20.0)

            app = record.application
            prompt = (
                f"You are the senior Underwriting Manager for a bank. Write a single authoritative, "
                f"well-reasoned paragraph justifying the loan decision based strictly on these verified facts:\n"
                f"- Applicant: {app.applicant_name} (ID: {app.applicant_id})\n"
                f"- Decision: {record.decision.value if record.decision else 'PENDING'}\n"
                f"- Decision Grounds: {record.decision_reason}\n"
                f"- Income: USD {record.extracted_monthly_income:,.2f} / month\n"
                f"- Requested Loan: USD {record.extracted_requested_amount:,.2f} ({record.extracted_tenure_months} months @ {record.annual_interest_rate}%)\n"
                f"- Computed Monthly EMI: USD {record.computed_monthly_emi:,.2f}\n"
                f"- EMI to Income: {record.emi_to_income_ratio:.1%} (Bank Policy: maximum 40%)\n"
                f"- Bureau Score: CIBIL {record.bureau_profile.cibil_score if record.bureau_profile else 'N/A'} (Tier: {record.credit_risk_level})\n"
                f"Output only the final paragraph with no filler or markdown preamble."
            )

            resp = client.chat.completions.create(
                model=self.local_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=250,
            )
            content = resp.choices[0].message.content.strip()
            if content:
                record.one_paragraph_justification = content
                record.add_trace(
                    agent_name="UnderwritingManager",
                    action="synthesize_local_llm_justification",
                    tool_used=f"Local Agent ({self.local_model_name} via Ollama)",
                    status="SUCCESS",
                    details={"model": self.local_model_name, "endpoint": self.local_endpoint},
                )
        except Exception as e:
            # Fallback gracefully to deterministic justification if local LLM is unreachable
            record.add_trace(
                agent_name="UnderwritingManager",
                action="synthesize_local_llm_justification",
                tool_used=f"Local Agent ({self.local_model_name})",
                status="FALLBACK_TO_DETERMINISTIC",
                details={"fallback_reason": str(e)},
            )

    def _append_to_run_log(self, record: SharedUnderwritingRecord) -> None:
        """Appends an execution record to the append-only markdown run log."""
        log_entry = [
            f"\n### Execution Event: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Applicant ID**: `{record.application.applicant_id}`",
            f"- **Applicant Name**: {record.application.applicant_name}",
            f"- **Decision**: **`{record.decision.value if record.decision else 'PENDING'}`**",
            f"- **Requested Amount**: ${record.extracted_requested_amount:,.2f}" if record.extracted_requested_amount else "- **Requested Amount**: N/A",
            f"- **Computed Monthly EMI**: ${record.computed_monthly_emi:,.2f}" if record.computed_monthly_emi else "- **Computed Monthly EMI**: N/A",
            f"- **Affordability Verdict**: {record.affordability_verdict or 'N/A'}",
            f"- **Decision Reason**: {record.decision_reason}",
            f"- **Justification**:\n  > {record.one_paragraph_justification}",
            f"- **Multi-Agent Trace Summary**:",
        ]

        for idx, t in enumerate(record.agent_trace, 1):
            log_entry.append(f"  {idx}. **{t.agent_name}** -> `{t.action}` ({t.status}) via `{t.tool_used}`")

        log_text = "\n".join(log_entry) + "\n\n---\n"

        try:
            with open(self.run_log_path, "a", encoding="utf-8") as f:
                f.write(log_text)
        except Exception:
            pass
