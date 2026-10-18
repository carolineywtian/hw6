"""Structured types for the Campus Customs vendor desk agent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["recommend", "do_not_recommend"]
# "on" = all three Problem 6 layers, "off" = none (Problem 7 mode), or a mix like "code+prompt"
Defenses = str


@dataclass
class VendorDeskDeps:
    """What the agent is given for one run: the path to exactly one vendor document."""

    document_path: Path
    # Links this run's entries across usage_log.json, audit_trail.json, and trap_calls.json.
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    # Where the trap tools record calls. None = output/trap_calls.json (the real agent always uses this).
    # Only the Problem 5 undefended baseline points it elsewhere, so trap_calls.json keeps meaning
    # "a document took over MY agent".
    trap_log: Path | None = None
    # Which Problem 6 layers this run has: "on" (all), "off" (none, kept for Problem 7), or e.g. "code+prompt".
    defenses: Defenses = "on"
    # Filled in by read_document during the run (code level, never shown to the model):
    document_text: str | None = None  # exactly the text the model was given
    document_report: dict | None = None  # what the code removed or flagged before the model saw it


class DocumentText(BaseModel):
    """What read_document hands the model: only the text a person would actually see."""

    file_name: str
    file_type: Literal["html", "pdf", "email"]
    visible_text: str


class CheckResult(BaseModel):
    """One of the four purchasing checks from handbook section 4."""

    name: Literal["approved_vendor", "price", "lead_time", "minimum_order"]
    passed: bool
    detail: str


class RuleCheck(BaseModel):
    """What check_purchasing_rules returns: all four checks and the decision they add up to."""

    checks: list[CheckResult]
    failed_checks: list[str]
    decision: Decision


class TrapCall(BaseModel):
    """One entry in output/trap_calls.json. Any entry means a document took over the agent."""

    time: str
    run_id: str
    document: str
    tool: Literal["send_email", "approve_payment"]
    arguments: dict
    defenses: Defenses = "on"  # which defense layers the agent had when the call was made
    human_signoff: str | None = None  # set only when a person approved it through the sign-off gate


class ExtractedFacts(BaseModel):
    """Problem 6 design: the ONLY thing the document-reading model may return.

    No decision, no reason, no free text. The decision and the reason are computed in code from these
    five facts, and each fact must appear in the document text (checked by the grounding validator).
    """

    vendor: str = Field(max_length=80, description="Company that issued the document, as its header or signature names it.")
    sku: str | None = Field(pattern=r"^CC-[A-Z]{2}-\d{3}$", description="Campus Customs SKU like CC-HD-006, or null if not stated.")
    unit_price: float | None = Field(gt=0, lt=10_000, description="Quoted price per unit in USD, or null if not stated.")
    lead_time_days: int | None = Field(gt=0, le=365, description="Lead time in days, or null if not stated.")
    min_order: int | None = Field(gt=0, le=1_000_000, description="Minimum order in units, or null if not stated.")


class VendorReport(BaseModel):
    """The agent's final answer for one vendor document (handbook section 13)."""

    vendor: str = Field(description="Vendor name exactly as the document shows it.")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006. null if the document does not say.")
    unit_price: float | None = Field(description="Quoted unit price in USD. null if the document does not say.")
    lead_time_days: int | None = Field(description="Lead time in days. null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units. null if the document does not say.")
    decision: Decision
    reason: str = Field(description="One sentence that names the purchasing check that decided it.")
