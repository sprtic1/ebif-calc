"""JSON Writer — produces clean JSON for the website dashboard.

Generates ebif_data.json consumed by the project dashboard page.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def build_dashboard_json(
    schedules: dict[str, list[dict]],
    schedule_defs: list[dict],
    qc_issues: list[dict],
    project_name: str,
    pipeline_duration_sec: float = 0.0,
) -> dict:
    """Build the full JSON structure for the website dashboard.

    Returns a dict ready for json.dump().
    """
    # Schedule summaries
    schedule_summaries = []
    total_elements = 0
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        count = len(rows)
        total_elements += count
        warnings = sum(1 for q in qc_issues if q["schedule"] == sdef["name"] and q["severity"] == "Warning")
        schedule_summaries.append({
            "id": sid,
            "name": sdef["name"],
            "count": count,
            "warnings": warnings,
            "columns": sdef.get("columns", []),
        })

    # Clean schedule data (remove internal fields)
    clean_schedules = {}
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        if rows:
            clean_rows = []
            for row in rows:
                clean = {k: v for k, v in row.items() if not k.startswith("_")}
                clean_rows.append(clean)
            clean_schedules[sid] = clean_rows

    # QC summary
    qc_summary = {
        "total": len(qc_issues),
        "warnings": sum(1 for q in qc_issues if q["severity"] == "Warning"),
        "info": sum(1 for q in qc_issues if q["severity"] == "Info"),
        "items": qc_issues[:200],  # cap at 200 for website
    }

    # Completion metrics
    active_schedules = sum(1 for s in schedule_summaries if s["count"] > 0)
    completion_pct = round(active_schedules / len(schedule_defs) * 100, 1) if schedule_defs else 0

    return {
        "project_name": project_name,
        "generated_at": datetime.now().isoformat(),
        "pipeline_duration_sec": round(pipeline_duration_sec, 1),
        "version": "1.0",
        "summary": {
            "total_elements": total_elements,
            "active_schedules": active_schedules,
            "total_schedules": len(schedule_defs),
            "completion_pct": completion_pct,
            "qc_warnings": qc_summary["warnings"],
        },
        "schedule_summaries": schedule_summaries,
        "schedules": clean_schedules,
        "qc": qc_summary,
    }


def write_json(
    data: dict,
    output_dir: Path,
    filename_prefix: str = "ebif_data",
) -> Path:
    """Write JSON to file.

    Returns the path to the written file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{filename_prefix}_{timestamp}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("JSON: %s", filepath)
    return filepath
