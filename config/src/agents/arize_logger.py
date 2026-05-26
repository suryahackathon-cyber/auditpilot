"""
AuditPilot — Arize Observability Logger
Traces all AI Validation Agent decisions to Arize Phoenix for
monitoring, drift detection, and human feedback loop integration.

Built with Claude Code via UiPath for Coding Agents.

Setup:
    pip install arize-phoenix openinference-instrumentation-anthropic

Arize Phoenix Docs: https://docs.arize.com/phoenix
"""

import os
import json
import datetime
from typing import Optional

# Arize Phoenix — open source LLM observability
try:
    import phoenix as px
    from phoenix.trace import SpanContext
    from openinference.semconv.trace import SpanAttributes, DocumentAttributes
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from phoenix.otel import register
    ARIZE_AVAILABLE = True
except ImportError:
    ARIZE_AVAILABLE = False
    print("[AuditPilot] Arize Phoenix not installed. Run: pip install arize-phoenix")


# ── Configuration ──────────────────────────────────────────────────────────────

PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006")
PROJECT_NAME = "auditpilot-validation-agent"


def init_arize():
    """
    Initialize Arize Phoenix tracer.
    Call once at the start of each audit run.
    """
    if not ARIZE_AVAILABLE:
        print("[Arize] Skipping init — Phoenix not installed.")
        return None

    tracer_provider = register(
        project_name=PROJECT_NAME,
        endpoint=f"{PHOENIX_ENDPOINT}/v1/traces",
    )

    print(f"[Arize] Phoenix tracer initialized → {PHOENIX_ENDPOINT}")
    print(f"[Arize] View traces at: {PHOENIX_ENDPOINT}")
    return tracer_provider


# ── Core Trace Functions ────────────────────────────────────────────────────────

def log_validation(
    validation_result: dict,
    llm_input: str,
    llm_output: str,
    latency_ms: float,
    run_id: str,
) -> str:
    """
    Log a single screenshot validation to Arize Phoenix.

    Args:
        validation_result: Output from validation_agent.validate_screenshot()
        llm_input: The prompt sent to the LLM
        llm_output: Raw LLM response text
        latency_ms: Time taken for LLM call in milliseconds
        run_id: Unique ID for this audit run (e.g. "2026-05")

    Returns:
        span_id: The trace span ID for reference
    """
    if not ARIZE_AVAILABLE:
        print(f"[Arize] Would log: {validation_result['metadata']}")
        return "mock-span-id"

    tracer = trace.get_tracer(PROJECT_NAME)
    meta = validation_result.get("metadata", {})

    with tracer.start_as_current_span("screenshot_validation") as span:
        # Core identifiers
        span.set_attribute("run_id", run_id)
        span.set_attribute("tool_name", meta.get("tool", "unknown"))
        span.set_attribute("connection_name", meta.get("connection", "unknown"))
        span.set_attribute("tab_name", meta.get("tab", "unknown"))

        # LLM input/output
        span.set_attribute(SpanAttributes.INPUT_VALUE, llm_input)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, llm_output)

        # Validation outcome
        span.set_attribute("is_valid", validation_result.get("is_valid", False))
        span.set_attribute("confidence", validation_result.get("confidence", 0.0))
        span.set_attribute("action", validation_result.get("action", "unknown"))
        span.set_attribute("anomaly_count", len(validation_result.get("anomalies", [])))
        span.set_attribute("anomalies", json.dumps(validation_result.get("anomalies", [])))
        span.set_attribute("summary", validation_result.get("summary", ""))

        # Performance
        span.set_attribute("latency_ms", latency_ms)
        span.set_attribute("timestamp", datetime.datetime.utcnow().isoformat())

        span_id = format(span.get_span_context().span_id, "016x")
        return span_id


def log_human_feedback(
    span_id: str,
    human_decision: str,
    reviewer_id: str,
    notes: str = "",
    run_id: str = "",
):
    """
    Log human reviewer decision back to Arize as ground truth feedback.
    Called when a Maestro Case is resolved by a human reviewer.

    This closes the feedback loop:
    Agent decision → Human override → Arize learns what's correct

    Args:
        span_id: The span ID returned from log_validation()
        human_decision: "approved" or "rejected"
        reviewer_id: ID or name of the human reviewer
        notes: Optional reviewer notes
        run_id: Audit run ID
    """
    if not ARIZE_AVAILABLE:
        print(f"[Arize] Would log human feedback: {human_decision} by {reviewer_id}")
        return

    tracer = trace.get_tracer(PROJECT_NAME)

    with tracer.start_as_current_span("human_feedback") as span:
        span.set_attribute("parent_span_id", span_id)
        span.set_attribute("run_id", run_id)
        span.set_attribute("human_decision", human_decision)
        span.set_attribute("reviewer_id", reviewer_id)
        span.set_attribute("reviewer_notes", notes)
        span.set_attribute("feedback_timestamp", datetime.datetime.utcnow().isoformat())

        # Label for model evaluation — was the agent right?
        span.set_attribute("agent_was_correct", human_decision == "approved")

    print(f"[Arize] Human feedback logged: {human_decision} by {reviewer_id} for span {span_id}")


def log_audit_run_summary(
    run_id: str,
    total: int,
    approved: int,
    escalated: int,
    retried: int,
    duration_seconds: float,
    output_file: str,
):
    """
    Log a summary span for the entire audit run.
    Useful for tracking run-level metrics in Arize over time.

    Args:
        run_id: Unique audit run ID (e.g. "2026-05")
        total: Total screenshots processed
        approved: Number auto-approved
        escalated: Number escalated to humans
        retried: Number retried due to blank/loading
        duration_seconds: Total run duration
        output_file: Path to generated Excel control document
    """
    if not ARIZE_AVAILABLE:
        print(f"[Arize] Would log run summary for {run_id}")
        return

    tracer = trace.get_tracer(PROJECT_NAME)

    with tracer.start_as_current_span("audit_run_summary") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("total_screenshots", total)
        span.set_attribute("approved_count", approved)
        span.set_attribute("escalated_count", escalated)
        span.set_attribute("retried_count", retried)
        span.set_attribute("approval_rate", approved / total if total > 0 else 0)
        span.set_attribute("duration_seconds", duration_seconds)
        span.set_attribute("output_file", output_file)
        span.set_attribute("run_timestamp", datetime.datetime.utcnow().isoformat())

    print(f"[Arize] Audit run summary logged: {run_id} — {approved}/{total} approved")


# ── Drift Detection Helper ──────────────────────────────────────────────────────

def check_agent_drift(current_approval_rate: float, baseline_rate: float = 0.90) -> dict:
    """
    Simple drift check — is the agent approving significantly
    fewer/more screenshots than usual?

    Args:
        current_approval_rate: This run's approval rate (0-1)
        baseline_rate: Expected approval rate from past runs

    Returns:
        dict with drift status and recommendation
    """
    delta = abs(current_approval_rate - baseline_rate)

    if delta > 0.20:
        return {
            "drift_detected": True,
            "severity": "HIGH",
            "message": f"Agent approval rate ({current_approval_rate:.0%}) deviated {delta:.0%} from baseline ({baseline_rate:.0%}). Review Arize traces.",
            "recommendation": "Check Phoenix dashboard for systematic misclassifications."
        }
    elif delta > 0.10:
        return {
            "drift_detected": True,
            "severity": "MEDIUM",
            "message": f"Mild drift detected ({delta:.0%}). Monitor next run.",
            "recommendation": "Review escalated cases in Phoenix for patterns."
        }
    else:
        return {
            "drift_detected": False,
            "severity": "NONE",
            "message": "Agent behavior within normal range.",
            "recommendation": None
        }


# ── Quickstart ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("AuditPilot — Arize Phoenix Integration")
    print("=" * 40)

    # Start Phoenix locally (for development)
    if ARIZE_AVAILABLE:
        session = px.launch_app()
        print(f"Phoenix running at: {session.url}")
    else:
        print("Install Arize: pip install arize-phoenix openinference-instrumentation-anthropic")

    # Example: log a mock validation
    mock_result = {
        "is_valid": True,
        "anomalies": ["User count increased by 35% vs last month"],
        "summary": "Fivetran Production DB — 3 new users added since last audit.",
        "confidence": 0.87,
        "action": "escalate",
        "metadata": {
            "tool": "Fivetran",
            "connection": "Production DB",
            "tab": "Users",
            "image_path": "screenshots/fivetran_conn1_users.png"
        }
    }

    span_id = log_validation(
        validation_result=mock_result,
        llm_input="Analyse this screenshot for access control anomalies...",
        llm_output="I detected 3 new users added since the last audit run...",
        latency_ms=1240,
        run_id="2026-05"
    )

    print(f"Logged validation span: {span_id}")

    # Simulate human reviewer approving the escalation
    log_human_feedback(
        span_id=span_id,
        human_decision="approved",
        reviewer_id="compliance_reviewer_1",
        notes="New users are part of Q2 onboarding batch — expected.",
        run_id="2026-05"
    )

    print("Done! Check Phoenix dashboard for traces.")
