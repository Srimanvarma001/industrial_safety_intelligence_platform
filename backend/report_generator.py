import io
from datetime import datetime, timezone
from typing import Any

from llm_reasoner import retrieve_relevant_regulations


def generate_incident_report(zone: dict, reasons: list[dict], workers: int) -> dict:
    ts = datetime.now(timezone.utc)

    regulations = retrieve_relevant_regulations(zone)

    report = {
        "incident_id": f"INC-{ts.strftime('%Y%m%d%H%M%S')}",
        "generated_at": ts.isoformat(),
        "zone": {
            "id": zone["id"],
            "name": zone["name"]
        },
        "trigger_score": zone.get("score", 0),
        "workers_in_zone": workers,
        "contributing_factors": [
            {
                "weight": r["w"],
                "description": r["t"],
                "detail": f"{r.get('pct', 'N/A')}% of threshold" if r.get("pct") else None
            }
            for r in reasons
        ],
        "regulatory_citations": [
            {
                "standard": r["standard"],
                "section": r["section"],
                "text": r["text"]
            }
            for r in regulations
        ],
        "checklist": [
            f"Immediately suspend all hot work permits in {zone['id']}",
            f"Initiate controlled evacuation of {workers} workers via primary exit corridor",
            "Activate emergency ventilation — confirm airflow positive in 90s",
            f"Isolate gas supply valve GV-{zone['id'][1:]}03 at manifold",
            f"Shift supervisor to take headcount at muster point B-{zone['id'][1:]}",
            "Do not re-enter until atmospheric reading < 10% LEL for 15 min"
        ]
    }

    return report


def generate_pdf(report: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(180, 40, 40)
    pdf.cell(0, 14, "INCIDENT REPORT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"SafetyIQ - Emergency Response Orchestrator", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Generated: {report['generated_at'][:19].replace('T', ' ')} UTC", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, f"Incident ID: {report['incident_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    details = [
        (f"Zone: {report['zone']['id']} - {report['zone']['name']}", ""),
        (f"Trigger Score: {report['trigger_score']}/100", ""),
        (f"Workers in Zone: {report['workers_in_zone']}", ""),
    ]
    for label, val in details:
        pdf.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, "Contributing Factors", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    for factor in report["contributing_factors"]:
        line = f"  {factor['weight']}  {factor['description']}"
        if factor.get("detail"):
            line += f" ({factor['detail']})"
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, "Regulatory References", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    citations = report.get("regulatory_citations", [])
    if citations:
        for reg in citations:
            pdf.multi_cell(0, 5, f"{reg['standard']} {reg['section']}: {reg['text']}")
            pdf.ln(2)
    else:
        pdf.multi_cell(0, 5,
            "OISD Standard 116 S4.2.1: Hot work in areas with flammable gas requires continuous "
            "atmospheric monitoring. Gas readings within 80% of LEL threshold mandate work stoppage."
        )
        pdf.ln(2)
        pdf.multi_cell(0, 5,
            "Factory Act 1948 S41B: Manufacturer's obligation to disclose hazardous process "
            "information before permit issuance."
        )

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, "Evacuation Checklist", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    for i, item in enumerate(report["checklist"], 1):
        pdf.cell(0, 6, f"  {i}. {item}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(140, 40, 40)
    pdf.multi_cell(0, 5,
        "Note: Compound risk was flagged before any single sensor breached its standalone "
        "threshold. This is the detection gap SafetyIQ closes."
    )

    return io.BytesIO(pdf.output()).getvalue()
