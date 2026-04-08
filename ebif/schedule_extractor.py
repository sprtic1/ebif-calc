"""Schedule Extractor — reads Archicad elements and filters by schedule toggle.

For each EID schedule category, this module:
1. Fetches all elements of the relevant types
2. Checks the toggle property (INCLUDE IN [X] SCHEDULE? = Yes)
3. Extracts all relevant properties for included elements
4. Returns structured schedule data ready for Excel/JSON output

Uses direct GUID lookup from schedules.json — no slow property name resolution.
"""

import logging
from typing import Any

from ebif.api_bridge import ArchicadConnection, P_ELEMENT_ID

logger = logging.getLogger(__name__)


def _is_yes(value: Any) -> bool:
    """Check if a property value represents Yes/True."""
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("yes", "true", "1", "on")


def extract_schedule(
    conn: ArchicadConnection,
    schedule_def: dict,
    all_elements_cache: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Extract a single schedule's data from Archicad.

    Args:
        conn: Active Archicad connection
        schedule_def: Schedule definition from schedules.json (with GUIDs)
        all_elements_cache: Optional cache of elements by type

    Returns:
        List of element dicts with all column properties filled in.
    """
    sched_name = schedule_def["name"]
    toggle_guid = schedule_def.get("toggle_guid")

    if not toggle_guid:
        logger.warning("Skipping schedule '%s' — no toggle_guid defined", sched_name)
        return []

    # Get elements of the relevant types
    elements = []
    for etype in schedule_def["element_types"]:
        if all_elements_cache and etype in all_elements_cache:
            elements.extend(all_elements_cache[etype])
        else:
            elems = conn.get_elements_by_type(etype)
            for e in elems:
                e["_type"] = etype
            elements.extend(elems)

    if not elements:
        logger.info("Schedule '%s': 0 elements of types %s", sched_name, schedule_def["element_types"])
        return []

    # Check toggle property for all elements
    toggle_values = conn.get_property_values(
        elements,
        [{"propertyId": {"guid": toggle_guid}}],
    )

    # Filter to included elements
    included = []
    for i, elem in enumerate(elements):
        if i < len(toggle_values):
            pvs = toggle_values[i].get("propertyValues", [])
            if pvs:
                pv = pvs[0].get("propertyValue", {})
                val = pv.get("value")
                # Handle enum values (singleEnum returns dict)
                if isinstance(val, dict):
                    val = val.get("nonLocalizedValue", val.get("displayValue", str(val)))
                if _is_yes(val):
                    included.append(elem)

    if not included:
        logger.info("Schedule '%s': 0 included (of %d checked)", sched_name, len(elements))
        return []

    # Build property GUID list from schedule_columns.json definition
    col_defs = schedule_def.get("_column_defs", [])
    resolved_guids = schedule_def.get("_resolved_col_guids", {})
    ebif_uid_guid = schedule_def.get("_ebif_uid_guid", "")

    # Collect GUIDs to fetch: EBIF UID + all column GUIDs
    prop_guids = []
    prop_labels = []
    if ebif_uid_guid:
        prop_guids.append(ebif_uid_guid)
        prop_labels.append("EBIF UID")
    for col in col_defs:
        guid = resolved_guids.get(col["label"], "")
        if guid:
            prop_guids.append(guid)
            prop_labels.append(col["label"])

    # Fetch all properties for included elements
    rows = conn.fetch_element_properties(included, prop_guids)

    # Map GUID keys back to readable column names
    result = []
    for row in rows:
        ebif_uid = row.get(ebif_uid_guid, "") if ebif_uid_guid else ""
        entry = {
            "_guid": row["_guid"],
            "_type": row.get("_type", ""),
            "EBIF UID": ebif_uid if ebif_uid else row["_guid"],
        }
        for label, guid in zip(prop_labels, prop_guids):
            if label == "EBIF UID":
                continue
            val = row.get(guid, "")
            entry[label] = val if val is not None else ""
        # Qty defaults to 1 per element
        entry["Qty"] = 1
        result.append(entry)

    logger.info("Schedule '%s': %d elements included", sched_name, len(result))
    return result


def extract_all_schedules(
    conn: ArchicadConnection,
    schedule_defs: list[dict],
) -> dict[str, list[dict]]:
    """Extract all schedules.

    Returns a dict mapping schedule_id -> list of element rows.
    """
    # Pre-cache elements by type to avoid redundant API calls
    all_types = set()
    for sdef in schedule_defs:
        all_types.update(sdef["element_types"])

    cache: dict[str, list[dict]] = {}
    for etype in sorted(all_types):
        elems = conn.get_elements_by_type(etype)
        for e in elems:
            e["_type"] = etype
        cache[etype] = elems
        logger.info("Cached %d %s elements", len(elems), etype)

    # Extract each schedule
    schedules: dict[str, list[dict]] = {}
    total_included = 0
    for sdef in schedule_defs:
        rows = extract_schedule(conn, sdef, all_elements_cache=cache)
        schedules[sdef["id"]] = rows
        total_included += len(rows)

    logger.info("Total: %d elements across %d active schedules",
                total_included,
                sum(1 for v in schedules.values() if v))
    return schedules
