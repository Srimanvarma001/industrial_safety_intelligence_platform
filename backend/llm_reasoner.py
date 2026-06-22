import json
import os
from pathlib import Path

OISD_PATH = Path(__file__).parent / "data" / "oisd_excerpts.json"

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=api_key)
            except ImportError:
                pass
    return _openai_client


def _load_corpus() -> list[dict]:
    with open(OISD_PATH) as f:
        return json.load(f)


def _keyword_match(keywords: list[str], text: str) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def retrieve_relevant_regulations(zone: dict) -> list[dict]:
    corpus = _load_corpus()
    query_terms = []

    if zone.get("permit"):
        query_terms.append(zone["permit"])
    if zone.get("maintenance"):
        query_terms.append(zone["maintenance"].replace("_", " "))
    if zone.get("changeover"):
        query_terms.append("shift changeover")
    if zone.get("currentGas", 0) > 0:
        query_terms.append("gas")
    if zone.get("workers", 0) > 4:
        query_terms.append("worker safety")

    query_text = " ".join(query_terms)

    scored = []
    for entry in corpus:
        relevance = _keyword_match(entry["keywords"], query_text) + _keyword_match(entry["keywords"], zone.get("name", ""))
        if relevance > 0:
            scored.append((relevance, entry))

    scored.sort(key=lambda x: -x[0])
    return [item[1] for item in scored[:3]]


def _build_prompt(zone: dict, score: int, reasons: list[dict], regulations: list[dict]) -> str:
    factors = "\n".join(f"  - {r['t']} (weight: {r['w']})" for r in reasons)
    reg_text = "\n".join(f"  - {r['standard']} {r['section']}: {r['text']}"
                         for r in regulations) if regulations else "  - (none matched)"

    return f"""You are a safety compliance expert at an industrial plant. Analyze the following zone situation and explain why the combination of conditions is dangerous.

Zone: {zone.get('id')} ({zone.get('name')})
Compound Risk Score: {score}/100
Current Gas: {zone.get('currentGas', 'N/A')} ppm (threshold: {zone.get('gasThresh', 'N/A')} ppm)
Permit: {zone.get('permit', 'none')}
Maintenance: {zone.get('maintenance', 'none')}
Shift Changeover: {zone.get('changeover', False)}
Workers: {zone.get('workers', 0)}

Contributing Factors:
{factors}

Relevant Regulations:
{reg_text}

Write a concise paragraph (3-4 sentences) explaining:
1. Why this specific combination of conditions is dangerous
2. What could go wrong if left unaddressed
3. What makes this situation urgent

Focus on the compound nature of the risk — no single factor triggered this alone."""


def _call_openai(prompt: str) -> str | None:
    client = _get_openai_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[llm] OpenAI API error: {e}")
        return None


def _generate_fallback_explanation(zone: dict, score: int, reasons: list[dict]) -> str:
    explanation = (
        f"Zone {zone['id']} ({zone['name']}) has a compound risk score of {score}/100 "
        f"classified as {_get_label(score)}.\n\n"
        f"Contributing factors:\n" +
        "\n".join(f"  * {r['t']} (weight: {r['w']})" for r in reasons)
    )

    reason_text = str(reasons).lower()
    if "hot work" in reason_text and "gas" in reason_text:
        explanation += (
            "\n\nHot work creates an ignition source. Rising gas levels in the same zone mean "
            "flammable atmosphere is accumulating. A single spark could trigger an explosion — "
            "this is the exact compound condition that led to the Vizag incident."
        )
    if "confined space" in reason_text:
        explanation += (
            "\nConfined space entry during elevated gas readings is extremely hazardous. "
            "Workers inside have limited egress. Gas accumulation in confined spaces "
            "reaches dangerous concentrations faster than in open areas."
        )
    if "changeover" in reason_text:
        explanation += (
            "\nShift changeover creates a supervision gap. Incoming personnel may not be "
            "fully briefed on active permits and current gas trends. Critical warnings "
            "can be lost during handoff."
        )
    return explanation


def generate_risk_explanation(zone: dict, score: int, reasons: list[dict]) -> dict:
    regulations = retrieve_relevant_regulations(zone)

    prompt = _build_prompt(zone, score, reasons, regulations)
    llm_explanation = _call_openai(prompt)

    if llm_explanation:
        explanation = (
            f"Zone {zone['id']} ({zone['name']}) has a compound risk score of **{score}/100** "
            f"classified as **{_get_label(score)}**.\n\n"
            f"**Contributing factors:**\n"
            + "\n".join(f"  • {r['t']} (weight: {r['w']})" for r in reasons) +
            f"\n\n**Analysis (AI-generated):**\n{llm_explanation}"
        )
    else:
        explanation = _generate_fallback_explanation(zone, score, reasons)

    reg_citations = []
    for reg in regulations:
        reg_citations.append({
            "standard": reg["standard"],
            "section": reg["section"],
            "text": reg["text"],
            "id": reg["id"]
        })

    return {
        "zone_id": zone["id"],
        "zone_name": zone["name"],
        "score": score,
        "label": _get_label(score),
        "explanation": explanation,
        "regulatory_citations": reg_citations,
        "llm_generated": llm_explanation is not None,
    }


def _get_label(score: int) -> str:
    if score >= 80: return "CRITICAL"
    if score >= 61: return "HIGH"
    if score >= 31: return "MEDIUM"
    return "LOW"
