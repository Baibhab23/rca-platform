from __future__ import annotations

import os
from typing import Any, Dict, List

import anthropic

_SYSTEM_PROMPT = """You are an enterprise analytics AI assistant specialized in Root Cause Analysis (RCA) for business operations. Your role is to translate technical anomaly detection and causal inference results into clear, actionable business narratives.

You understand:
- Statistical anomaly detection (Isolation Forest, Z-score, LSTM)
- Causal inference (DoWhy, Granger causality)
- Prescriptive analytics and optimization
- Business domains: finance, sales, manufacturing, supply chain

When given analysis results, produce:
1. A concise executive summary (2-3 sentences)
2. A detailed explanation of root causes in business terms
3. Prioritized, actionable recommendations

Always be concrete, quantitative where possible, and avoid jargon. Frame findings in terms of business impact."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def generate_narrative(
    prescription: Dict[str, Any],
    rca_summary: str,
    root_causes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a business narrative for the full RCA pipeline output."""
    client = _get_client()

    actions_text = "\n".join(
        f"  {i+1}. [{a.get('target_feature', 'N/A')}] {a.get('description', '')} "
        f"(expected impact: {a.get('expected_impact', 0):.3f}, priority: {a.get('priority', i+1)})"
        for i, a in enumerate(prescription.get("actions", []))
    )

    causes_text = "\n".join(
        f"  - {rc.get('feature', 'N/A')}: effect_size={rc.get('effect_size', 0):.3f}, "
        f"confidence={rc.get('confidence', 0):.3f}, method={rc.get('method', 'N/A')}"
        for rc in root_causes[:5]
    )

    user_message = f"""Analyze the following RCA pipeline output and produce a business narrative.

RCA Summary: {rca_summary}

Root Causes Identified:
{causes_text}

Prescribed Actions:
{actions_text}

Please provide:
1. EXECUTIVE SUMMARY: A 2-3 sentence business-level summary
2. ROOT CAUSE EXPLANATION: Clear explanation of what caused the anomaly
3. RECOMMENDATIONS: 3-5 bullet-point actionable recommendations for business stakeholders"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # prompt caching
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    full_text = response.content[0].text
    sections = _parse_sections(full_text)

    return {
        "summary": sections.get("executive_summary", full_text[:300]),
        "explanation": sections.get("root_cause_explanation", ""),
        "recommendations": sections.get("recommendations", []),
        "raw": full_text,
    }


def _parse_sections(text: str) -> Dict[str, Any]:
    """Parse structured sections from Claude's response."""
    lines = text.split("\n")
    sections: Dict[str, Any] = {}
    current_section = None
    buffer: List[str] = []

    section_map = {
        "executive summary": "executive_summary",
        "root cause explanation": "root_cause_explanation",
        "recommendations": "recommendations",
    }

    def flush() -> None:
        if current_section:
            content = "\n".join(buffer).strip()
            if current_section == "recommendations":
                recs = [
                    ln.lstrip("•-* 0123456789.").strip()
                    for ln in content.split("\n")
                    if ln.strip() and not ln.strip().startswith("#")
                ]
                sections[current_section] = [r for r in recs if r]
            else:
                sections[current_section] = content

    for line in lines:
        lower = line.lower().strip().lstrip("#").strip()
        matched = next((v for k, v in section_map.items() if k in lower), None)
        if matched:
            flush()
            buffer = []
            current_section = matched
        else:
            buffer.append(line)

    flush()
    return sections
