"""
AuditPilot — AI Validation Agent
Validates screenshots captured from SaaS tools and detects anomalies.
Integrated with Arize Phoenix for full observability and human feedback loop.
Built with Claude Code via UiPath for Coding Agents.
"""

import base64
import json
import time
import datetime
from pathlib import Path
from arize_logger import (
    init_arize,
    log_validation,
    log_human_feedback,
    log_audit_run_summary,
    check_agent_drift
)


def encode_image(image_path: str) -> str:
    """Encode image to base64 for LLM processing."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def validate_screenshot(
    image_path: str,
    tool_name: str,
    connection_name: str,
    tab_name: str,
    run_id: str,
    previous_report: dict = None
) -> dict:
    """
    Validate a screenshot and detect anomalies.
    Every decision is traced to Arize Phoenix automatically.

    Args:
        image_path: Path to the screenshot file
        tool_name: Name of the SaaS tool (e.g. Fivetran)
        connection_name: Name of the connection
        tab_name: Tab that was captured (e.g. Users, Teams)
        run_id: Audit run ID (e.g. "2026-05") for Arize grouping
        previous_report: Previous month's data for comparison (optional)

    Returns:
        dict with keys:
            - is_valid (bool): Screenshot is usable
            - anomalies (list): List of detected anomalies
            - summary (str): AI-generated summary of the screenshot
            - confidence (float): Confidence score 0-1
            - action (str): "approve", "retry", or "escalate"
            - span_id (str): Arize trace span ID for feedback loop
    """

    start_time = time.time()

    # ── Step 1: Blank/loading check ──────────────────────────────────────────
    if check_blank_screenshot(image_path):
        result = {
            "is_valid": False,
            "anomalies": ["Screenshot appears blank or still loading"],
            "summary": f"Screenshot for {connection_name} ({tab_name}) was blank. Retry needed.",
            "confidence": 0.99,
            "action": "retry",
            "metadata": {
                "tool": tool_name,
                "connection": connection_name,
                "tab": tab_name,
                "image_path": image_path
            }
        }
        span_id = log_validation(
            validation_result=result,
            llm_input="[blank check — no LLM call made]",
            llm_output="[blank screenshot detected]",
            latency_ms=0,
            run_id=run_id
        )
        result["span_id"] = span_id
        return result

    # ── Step 2: Build LLM prompt ─────────────────────────────────────────────
    context = ""
    if previous_report:
        context = f"\nPrevious month data for comparison: {json.dumps(previous_report)}"

    llm_input = f"""You are a compliance auditor reviewing access control screenshots.

Tool: {tool_name}
Connection: {connection_name}
Tab: {tab_name}
{context}

Analyse this screenshot and return a JSON object with:
- anomalies: list of strings describing any access control issues found
- summary: 1-2 sentence plain English summary of what you see
- confidence: float 0-1 representing your confidence in the analysis
- action: "approve" if all looks normal, "escalate" if anomalies found, "retry" if image is unclear

Focus on: unexpected users, missing teams, permission changes, user count spikes vs previous month.
Return ONLY valid JSON, no preamble."""

    # ── Step 3: LLM call (via UiPath Agent Builder) ──────────────────────────
    # This is replaced by the actual Agent Builder invocation in UiPath
    # The Agent Builder calls Claude/GPT with the image + prompt above
    llm_output = _call_llm(llm_input, image_path)
    latency_ms = (time.time() - start_time) * 1000

    # ── Step 4: Parse LLM response ───────────────────────────────────────────
    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        parsed = {
            "anomalies": ["LLM response parsing failed"],
            "summary": "Could not parse agent response. Manual review required.",
            "confidence": 0.0,
            "action": "escalate"
        }

    result = {
        "is_valid": True,
        "anomalies": parsed.get("anomalies", []),
        "summary": parsed.get("summary", ""),
        "confidence": parsed.get("confidence", 0.0),
        "action": parsed.get("action", "escalate"),
        "metadata": {
            "tool": tool_name,
            "connection": connection_name,
            "tab": tab_name,
            "image_path": image_path
        }
    }

    # ── Step 5: Log to Arize Phoenix ─────────────────────────────────────────
    span_id = log_validation(
        validation_result=result,
        llm_input=llm_input,
        llm_output=llm_output,
        latency_ms=latency_ms,
        run_id=run_id
    )
    result["span_id"] = span_id

    return result


def record_human_decision(
    validation_result: dict,
    human_decision: str,
    reviewer_id: str,
    notes: str = "",
    run_id: str = ""
):
    """
    Called by UiPath Maestro Case workflow when a human reviewer
    approves or rejects an escalated anomaly.

    Logs the decision back to Arize to close the feedback loop,
    enabling the agent to improve over time with real ground truth.

    Args:
        validation_result: The original validation dict (contains span_id)
        human_decision: "approved" or "rejected"
        reviewer_id: Reviewer identifier
        notes: Optional notes from reviewer
        run_id: Audit run ID
    """
    span_id = validation_result.get("span_id", "unknown")
    log_human_feedback(
        span_id=span_id,
        human_decision=human_decision,
        reviewer_id=reviewer_id,
        notes=notes,
        run_id=run_id
    )
    print(f"[AuditPilot] Human feedback recorded → Arize span: {span_id}")


def run_audit(connections_config: dict, run_id: str = None) -> dict:
    """
    Main entry point — runs the full validation pass for all tools/connections.
    Called by UiPath Maestro BPMN after RPA captures all screenshots.

    Args:
        connections_config: Loaded from config/connections.json
        run_id: Unique run ID, defaults to current year-month

    Returns:
        Full anomaly report with Arize span IDs for each validation
    """
    if not run_id:
        run_id = datetime.datetime.now().strftime("%Y-%m")

    init_arize()

    all_validations = []
    start_time = time.time()

    for tool in connections_config.get("tools", []):
        tool_name = tool["name"]
        for connection in tool.get("connections", []):
            for tab in tool.get("tabs_to_capture", []):
                image_path = f"screenshots/{tool_name.lower()}_{connection['id']}_{tab.lower()}.png"
                result = validate_screenshot(
                    image_path=image_path,
                    tool_name=tool_name,
                    connection_name=connection["name"],
                    tab_name=tab,
                    run_id=run_id
                )
                all_validations.append(result)
                print(f"[{tool_name}] {connection['name']} / {tab} → {result['action'].upper()}")

    # Build summary
    approved = len([v for v in all_validations if v["action"] == "approve"])
    escalated = len([v for v in all_validations if v["action"] == "escalate"])
    retried = len([v for v in all_validations if v["action"] == "retry"])
    total = len(all_validations)
    duration = time.time() - start_time

    output_file = f"outputs/AuditPilot_ControlDoc_{run_id}.xlsx"

    log_audit_run_summary(
        run_id=run_id,
        total=total,
        approved=approved,
        escalated=escalated,
        retried=retried,
        duration_seconds=duration,
        output_file=output_file
    )

    # Drift check
    drift = check_agent_drift(approved / total if total > 0 else 0)
    if drift["drift_detected"]:
        print(f"[Arize] ⚠️  Drift detected ({drift['severity']}): {drift['message']}")

    return {
        "run_id": run_id,
        "total": total,
        "approved": approved,
        "escalated": escalated,
        "retried": retried,
        "validations": all_validations,
        "drift": drift,
        "output_file": output_file
    }


def check_blank_screenshot(image_path: str) -> bool:
    """Check if screenshot is blank or still loading."""
    # Implemented via image analysis in UiPath Agent Builder
    return False


def detect_user_spike(current_count: int, previous_count: int, threshold: float = 0.25) -> bool:
    """Detect if user count has spiked beyond threshold."""
    if previous_count == 0:
        return False
    change = abs(current_count - previous_count) / previous_count
    return change > threshold


def _call_llm(prompt: str, image_path: str) -> str:
    """
    Placeholder for actual LLM call via UiPath Agent Builder.
    In production this is replaced by Agent Builder's LLM invocation
    with the image attached as base64.
    """
    return json.dumps({
        "anomalies": [],
        "summary": "Access control looks normal. No unexpected users or team changes detected.",
        "confidence": 0.95,
        "action": "approve"
    })


if __name__ == "__main__":
    import sys

    # Load config
    with open("config/connections.json") as f:
        config = json.load(f)

    report = run_audit(config)
    print("\n── Audit Complete ──")
    print(f"Total:     {report['total']}")
    print(f"Approved:  {report['approved']}")
    print(f"Escalated: {report['escalated']}")
    print(f"Retried:   {report['retried']}")
    print(f"Output:    {report['output_file']}")
