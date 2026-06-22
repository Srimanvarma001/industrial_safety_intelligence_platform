import json
import random
from pathlib import Path


OISD_PATH = Path(__file__).parent / "data" / "oisd_excerpts.json"


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


def generate_risk_explanation(zone: dict, score: int, reasons: list[dict]) -> dict:
    regulations = retrieve_relevant_regulations(zone)

    explanation_parts = []
    for r in reasons:
        explanation_parts.append(f"  • {r['t']} (weight: {r['w']})")

    explanation = (
        f"Zone {zone['id']} ({zone['name']}) has a compound risk score of **{score}/100** "
        f"classified as **{_get_label(score)}**.\n\n"
        f"**Contributing factors:**\n"
        + "\n".join(explanation_parts) +
        "\n\n**Why this combination is dangerous:**"
    )

    if any("hot_work" in str(r) for r in reasons) and any("gas" in str(r) for r in reasons):
        explanation += (
            "\nHot work creates an ignition source. Rising gas levels in the same zone mean "
            "flammable atmosphere is accumulating. A single spark could trigger an explosion — "
            "this is the exact compound condition that led to the Vizag incident."
        )
    if any("confined_space" in str(r) for r in reasons):
        explanation += (
            "\nConfined space entry during elevated gas readings is extremely hazardous. "
            "Workers inside have limited egress. Gas accumulation in confined spaces "
            "reaches dangerous concentrations faster than in open areas."
        )
    if any("changeover" in str(r) for r in reasons):
        explanation += (
            "\nShift changeover creates a supervision gap. Incoming personnel may not be "
            "fully briefed on active permits and current gas trends. Critical warnings "
            "can be lost during handoff."
        )

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
        "regulatory_citations": reg_citations
    }


def _get_label(score: int) -> str:
    if score >= 80: return "CRITICAL"
    if score >= 61: return "HIGH"
    if score >= 31: return "MEDIUM"
    return "LOW"
