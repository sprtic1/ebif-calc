"""Quality Control Checker — detects missing data, unclassified elements, orphans.

Two modes:
  - Extract mode (Step 1): Light check on Archicad data completeness.
  - Publish mode (Step 2): Full check on the Excel working document — flags
    any rows with missing TEAR SHEET #, vendor, model, or other required fields
    as "incomplete" for the dashboard.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Fields that should be populated before publishing
REQUIRED_FIELDS = {"TEAR SHEET #"}
IMPORTANT_FIELDS = {"MANUFACTURER", "MODEL #", "FINISH", "TYPE", "MATERIAL",
                    "ITEM", "STYLE", "VENDOR", "DESCRIPTION"}


def _is_blank(val: Any) -> bool:
    """Check if a value is effectively blank."""
    if val is None:
        return True
    s = str(val).strip()
    return s in ("", "None", "0", "0.0")


def check_schedule(
    schedule_id: str,
    schedule_name: str,
    rows: list[dict],
    columns: list[str],
    mode: str = "publish",
) -> list[dict]:
    """Run QC checks on a single schedule's data.

    Args:
        mode: "extract" for light checks, "publish" for full completeness checks.

    Returns list of QC issue dicts.
    """
    issues = []
    skip = {"Element ID", "Qty", "Zone", "Room", "NOTES", "URL"}

    for row in rows:
        eid = row.get("Element ID", "?")
        guid = row.get("_guid", "")

        # Check TEAR SHEET # (always a warning)
        ts = row.get("TEAR SHEET #")
        if _is_blank(ts):
            issues.append({
                "schedule": schedule_name,
                "element_id": eid,
                "guid": guid,
                "severity": "Warning",
                "message": "Missing TEAR SHEET #",
            })

        if mode == "publish":
            # In publish mode, check all spec columns for completeness
            for col in columns:
                if col in skip or col in REQUIRED_FIELDS:
                    continue
                val = row.get(col)
                if _is_blank(val):
                    # Important fields get Warning, others get Info
                    sev = "Warning" if col.upper() in {f.upper() for f in IMPORTANT_FIELDS} else "Info"
                    issues.append({
                        "schedule": schedule_name,
                        "element_id": eid,
                        "guid": guid,
                        "severity": sev,
                        "message": f"Missing '{col}'",
                    })

    return issues


def check_all_schedules(
    schedules: dict[str, list[dict]],
    schedule_defs: list[dict],
    mode: str = "publish",
) -> list[dict]:
    """Run QC on all schedules.

    Args:
        mode: "extract" for light checks (Step 1), "publish" for full checks (Step 2).

    Returns combined list of QC issues.
    """
    all_issues = []
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        if rows:
            issues = check_schedule(sid, sdef["name"], rows, sdef.get("columns", []), mode=mode)
            all_issues.extend(issues)

    warnings = sum(1 for i in all_issues if i["severity"] == "Warning")
    infos = sum(1 for i in all_issues if i["severity"] == "Info")
    logger.info("QC (%s mode): %d warnings, %d info items", mode, warnings, infos)

    return all_issues


def completion_metrics(
    schedules: dict[str, list[dict]],
    schedule_defs: list[dict],
) -> dict:
    """Calculate completion metrics for the Summary tab.

    Returns dict with total_rows, complete_rows, incomplete_rows, pct_complete.
    """
    total = 0
    complete = 0

    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        columns = sdef.get("columns", [])
        skip = {"Element ID", "Qty", "Zone", "Room", "NOTES", "URL"}

        for row in rows:
            total += 1
            # A row is "complete" if TEAR SHEET # and at least one important field are filled
            ts = row.get("TEAR SHEET #")
            has_ts = not _is_blank(ts)
            has_spec = False
            for col in columns:
                if col in skip or col == "TEAR SHEET #":
                    continue
                if not _is_blank(row.get(col)):
                    has_spec = True
                    break
            if has_ts and has_spec:
                complete += 1

    return {
        "total_rows": total,
        "complete_rows": complete,
        "incomplete_rows": total - complete,
        "pct_complete": round(complete / total * 100, 1) if total > 0 else 0.0,
    }
