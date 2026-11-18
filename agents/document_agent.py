"""
Document Agent Module.
Specialist agent responsible for document validation and financial data extraction.
"""
from __future__ import annotations

from typing import Any, Dict
from semantic_kernel import Kernel
from tools.document_tools import DocumentTools
from models.schemas import SharedUnderwritingRecord


class DocumentAgent:
    """Specialist agent for validating application documents and extracting financial figures."""

    INSTRUCTIONS = (
        "You are the Document Specialist Agent for loan underwriting. Your role is strictly "
        "to validate that required application documents and fields are present, and extract "
        "verified income, existing EMIs, and requested loan parameters. If income is missing, "
        "you must report it as missing rather than estimating or assuming it."
    )

    def __init__(self, kernel: Kernel | None = None):
        self.kernel = kernel or Kernel()
        self.tools = DocumentTools()
        if "document_tools" not in self.kernel.plugins:
            self.kernel.add_plugin(self.tools, plugin_name="document_tools")

    def process(self, shared_record: SharedUnderwritingRecord) -> SharedUnderwritingRecord:
        """
        Executes document validation and field extraction against the shared record.
        Updates shared state in-place and records audit trail.
        """
        raw_app = shared_record.application.model_dump()

        # Tool 1: Completeness & mandatory fields validation
        val_result = self.tools.validate_application_completeness(raw_app)
        shared_record.is_valid = val_result["is_complete"]
        shared_record.validation_errors = val_result["missing_fields"]

        shared_record.add_trace(
            agent_name="DocumentAgent",
            action="validate_application_completeness",
            tool_used="DocumentTools.validate_application_completeness",
            status=val_result["status"],
            details=val_result,
        )

        if not val_result["is_complete"]:
            return shared_record

        # Tool 2: Extraction of financial values
        extract_result = self.tools.extract_financial_fields(raw_app)
        shared_record.extracted_monthly_income = extract_result["monthly_income"]
        shared_record.extracted_existing_emis = extract_result["existing_emis"]
        shared_record.extracted_requested_amount = extract_result["requested_amount"]
        shared_record.extracted_tenure_months = extract_result["tenure_months"]

        shared_record.add_trace(
            agent_name="DocumentAgent",
            action="extract_financial_fields",
            tool_used="DocumentTools.extract_financial_fields",
            status="SUCCESS",
            details=extract_result,
        )

        return shared_record
