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

    # Separate columns by type: properties vs classifications vs literals
    prop_guids = []
    prop_labels = []
    classification_cols = {}  # label -> system name
    literal_cols = {}  # label -> literal value

    if ebif_uid_guid:
        prop_guids.append(ebif_uid_guid)
        prop_labels.append("EBIF UID")

    for col in col_defs:
        label = col["label"]
        resolved = resolved_guids.get(label, "")
        if resolved.startswith("_classification:"):
            classification_cols[label] = resolved[len("_classification:"):]
        elif resolved.startswith("_literal:"):
            literal_cols[label] = resolved[len("_literal:"):]
        elif resolved:
            prop_guids.append(resolved)
            prop_labels.append(label)

    # Fetch property values for included elements
    rows = conn.fetch_element_properties(included, prop_guids)

    # Fetch classification data if needed
    cls_data = {}
    if classification_cols:
        cls_data = _fetch_classifications(conn, included, classification_cols)

    # Map GUID keys back to readable column names
    result = []
    for i, row in enumerate(rows):
        ebif_uid = row.get(ebif_uid_guid, "") if ebif_uid_guid else ""
        elem_guid = row["_guid"]
        entry = {
            "_guid": elem_guid,
            "_type": row.get("_type", ""),
            "EBIF UID": ebif_uid if ebif_uid else elem_guid,
        }
        for label, guid in zip(prop_labels, prop_guids):
            if label == "EBIF UID":
                continue
            val = row.get(guid, "")
            entry[label] = val if val is not None else ""
        # Add classification columns
        for label in classification_cols:
            entry[label] = cls_data.get(elem_guid, {}).get(label, "")
        # Add literal columns
        for label, val in literal_cols.items():
            entry[label] = val
        # Qty defaults to 1 per element
        entry["Qty"] = 1
        result.append(entry)

    logger.info("Schedule '%s': %d elements included", sched_name, len(result))
    return result


def _fetch_classifications(
    conn: ArchicadConnection,
    elements: list[dict],
    classification_cols: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Fetch classification values for elements.

    Args:
        conn: Archicad connection
        elements: list of element dicts with elementId
        classification_cols: mapping of label -> classification system name

    Returns:
        dict mapping element_guid -> {label: "classification id - name"}
    """
    import requests, os
    port = int(os.getenv("_EBIF_AC_PORT", "19724"))
    base = f"http://localhost:{port}"

    def ac(cmd, params=None):
        payload = {"command": cmd}
        if params: payload["parameters"] = params
        return requests.post(base, json=payload, timeout=30).json()

    # Get all classification systems
    sys_r = ac("API.GetAllClassificationSystems")
    if not sys_r.get("succeeded"):
        return {}
    systems = sys_r["result"]["classificationSystems"]

    # Map system names to GUIDs
    sys_name_to_guid = {}
    sys_guid_to_name = {}
    for s in systems:
        sys_name_to_guid[s["name"]] = s["classificationSystemId"]["guid"]
        sys_guid_to_name[s["classificationSystemId"]["guid"]] = s["name"]

    # Figure out which systems we need
    needed_sys_guids = []
    label_to_sys_name = {}
    for label, sys_name in classification_cols.items():
        guid = sys_name_to_guid.get(sys_name, "")
        if guid:
            needed_sys_guids.append(guid)
            label_to_sys_name[label] = sys_name

    if not needed_sys_guids:
        return {}

    # Fetch classifications for all elements at once
    clean_elems = [{"elementId": e["elementId"]} for e in elements]
    sys_ids = [{"classificationSystemId": {"guid": g}} for g in needed_sys_guids]
    cr = ac("API.GetClassificationsOfElements", {"elements": clean_elems, "classificationSystemIds": sys_ids})
    if not cr.get("succeeded"):
        return {}

    # Get all classification items we need to resolve
    item_guids_to_resolve = set()
    for ec in cr["result"]["elementClassifications"]:
        for ci in ec.get("classificationIds", []):
            item_id = ci.get("classificationId", {}).get("classificationItemId", {}).get("guid")
            if item_id:
                item_guids_to_resolve.add(item_id)

    # Resolve classification items to get their id + name
    # Build item lookup by fetching all classifications from needed systems
    item_lookup = {}  # item_guid -> "id - name"
    for sys_guid in set(needed_sys_guids):
        tree_r = ac("API.GetAllClassificationsInSystem", {"classificationSystemId": {"guid": sys_guid}})
        if tree_r.get("succeeded"):
            _walk_classification_tree(tree_r["result"].get("classificationItems", []), item_lookup)

    # Build result: element_guid -> {label: value}
    result = {}
    for i, elem in enumerate(elements):
        elem_guid = elem["elementId"]["guid"]
        result[elem_guid] = {}
        ec = cr["result"]["elementClassifications"][i]
        # Map system GUIDs back to classification values
        sys_guid_to_value = {}
        for ci in ec.get("classificationIds", []):
            sys_g = ci.get("classificationId", {}).get("classificationSystemId", {}).get("guid", "")
            item_g = ci.get("classificationId", {}).get("classificationItemId", {}).get("guid", "")
            if sys_g and item_g:
                sys_guid_to_value[sys_g] = item_lookup.get(item_g, "")

        for label, sys_name in label_to_sys_name.items():
            sys_g = sys_name_to_guid.get(sys_name, "")
            result[elem_guid][label] = sys_guid_to_value.get(sys_g, "")

    logger.info("Fetched classifications for %d elements across %d systems", len(elements), len(needed_sys_guids))
    return result


def _walk_classification_tree(items: list, lookup: dict):
    """Walk a classification tree and build item_guid -> 'id - name' lookup."""
    for item in items:
        ci = item.get("classificationItem", item)
        guid = ci.get("classificationItemId", {}).get("guid", "")
        cid = ci.get("id", "")
        cname = ci.get("name", "")
        if guid:
            lookup[guid] = f"{cid} - {cname}" if cid else cname
        for child in ci.get("children", item.get("children", [])):
            _walk_classification_tree([child], lookup)


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
