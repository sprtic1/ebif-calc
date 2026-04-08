"""Property Discovery — auto-discovers property GUIDs from the live Archicad model.

Property GUIDs are project-specific in Archicad. This module fetches all
user-defined properties and resolves built-in properties, then maps them
to the column definitions in schedule_columns.json.
"""

import json
import logging
import requests
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def discover_all_properties(port: int) -> list[dict]:
    """Fetch all user-defined properties from Archicad and return their details.

    Returns list of dicts with keys: guid, group, name, type.
    """
    base_url = f"http://localhost:{port}"

    def ac(cmd, params=None):
        payload = {"command": cmd}
        if params:
            payload["parameters"] = params
        r = requests.post(base_url, json=payload, timeout=30)
        return r.json()

    # Get all user-defined property IDs
    r = ac("API.GetAllPropertyIds", {"propertyType": "UserDefined"})
    if not r.get("succeeded"):
        logger.error("Failed to get property IDs: %s", r.get("error"))
        return []

    prop_ids = r["result"]["propertyIds"]
    logger.info("Found %d user-defined properties", len(prop_ids))

    # Get details in batches of 50
    all_defs = []
    for i in range(0, len(prop_ids), 50):
        batch = prop_ids[i:i + 50]
        dr = ac("API.GetDetailsOfProperties", {"properties": batch})
        if dr.get("succeeded"):
            for pd in dr["result"].get("propertyDefinitions", []):
                d = pd.get("propertyDefinition", {})
                all_defs.append({
                    "guid": d.get("propertyId", {}).get("guid", ""),
                    "group": d.get("group", {}).get("name", ""),
                    "name": d.get("name", ""),
                    "type": d.get("type", ""),
                })

    logger.info("Discovered %d property definitions", len(all_defs))
    return all_defs


def build_schedule_guid_map(
    all_properties: list[dict],
    schedule_defs: list[dict],
) -> list[dict]:
    """Match discovered properties to schedule definitions and fill in GUIDs.

    Updates each schedule_def in-place with the correct toggle_guid and
    property GUIDs for the current project.

    Returns the updated schedule_defs.
    """
    # Build lookup: (group_name, prop_name) -> guid
    lookup: dict[tuple[str, str], str] = {}
    for p in all_properties:
        key = (p["group"], p["name"])
        lookup[key] = p["guid"]

    # Build a secondary lookup that strips common prefixes (EID/EBIF) for fuzzy matching
    # This handles projects that use "EBIF APPLIANCES" vs "EID APPLIANCES"
    def _normalize_group(name: str) -> str:
        """Strip EID/EBIF prefix for fuzzy group matching."""
        for prefix in ("EBIF ", "EID "):
            if name.upper().startswith(prefix):
                return name[len(prefix):]
        return name

    norm_lookup: dict[tuple[str, str], str] = {}
    for p in all_properties:
        norm_key = (_normalize_group(p["group"]), p["name"])
        norm_lookup[norm_key] = p["guid"]

    # Also build group name map: normalized -> actual group name found in project
    actual_groups: dict[str, str] = {}
    for p in all_properties:
        norm = _normalize_group(p["group"])
        actual_groups[norm] = p["group"]

    matched_toggles = 0
    matched_props = 0

    for sdef in schedule_defs:
        group = sdef.get("group", "")
        norm_group = _normalize_group(group)

        # Match toggle property — search by normalized group name
        toggle_guid = ""
        # Look for any "INCLUDE IN..." property in the matching group
        for p in all_properties:
            if _normalize_group(p["group"]) == norm_group and "INCLUDE IN" in p["name"].upper():
                toggle_guid = p["guid"]
                break

        if toggle_guid:
            sdef["toggle_guid"] = toggle_guid
            matched_toggles += 1
        else:
            sdef["toggle_guid"] = ""
            logger.warning("Toggle not found for '%s': group='%s'", sdef["name"], group)

        # Discover ALL data properties in this group directly from Archicad
        # (ignoring whatever was hardcoded in schedules.json)
        resolved_props = {}
        discovered_columns = []
        skip_names = {"INCLUDE IN", "EBIF UID"}  # toggles and UID handled separately
        for p in all_properties:
            if _normalize_group(p["group"]) != norm_group:
                continue
            if any(skip in p["name"].upper() for skip in skip_names):
                continue
            resolved_props[p["name"]] = p["guid"]
            discovered_columns.append(p["name"])
            matched_props += 1
        sdef["properties"] = resolved_props
        sdef["columns"] = discovered_columns

    # Find EBIF UID property (primary key — in EID/EBIF GENERAL PROPERTIES)
    ebif_uid_guid = norm_lookup.get(("GENERAL PROPERTIES", "EBIF UID"), "")
    if ebif_uid_guid:
        for sdef in schedule_defs:
            sdef["_ebif_uid_guid"] = ebif_uid_guid
        logger.info("Found EBIF UID: %s", ebif_uid_guid)
    else:
        logger.warning("EBIF UID property not found — using Archicad GUID as fallback")

    # Resolve schedule_columns.json column definitions into GUIDs
    _resolve_column_defs(schedule_defs, all_properties, norm_lookup, port=None)

    logger.info("Matched %d/%d toggles, %d property GUIDs",
                matched_toggles, len(schedule_defs), matched_props)
    return schedule_defs


def _resolve_column_defs(
    schedule_defs: list[dict],
    all_properties: list[dict],
    norm_lookup: dict,
    port: int | None = None,
):
    """Resolve schedule_columns.json into GUIDs and attach to schedule defs.

    Each schedule def gets:
      _column_defs: list of {label, source} from schedule_columns.json
      _resolved_col_guids: dict mapping label -> GUID
      columns: list of label strings (for Excel writer)
    """
    config_path = Path(__file__).parent.parent / "config" / "schedule_columns.json"
    if not config_path.exists():
        logger.warning("schedule_columns.json not found — using EBIF group columns")
        return

    col_config = json.load(open(config_path))
    default_cols = col_config.get("_default_columns", [])
    sched_cols = col_config.get("schedules", {})

    # Build user-defined property lookup: (normalized_group, name) -> guid
    # already have norm_lookup from parent function

    # Build a flat user-defined lookup: property_name -> guid (across all groups)
    user_flat: dict[str, str] = {}
    for p in all_properties:
        if p["name"] not in user_flat:
            user_flat[p["name"]] = p["guid"]

    # Build per-schedule-group lookup: name -> guid
    def _normalize_group(name: str) -> str:
        for prefix in ("EBIF ", "EID "):
            if name.upper().startswith(prefix):
                return name[len(prefix):]
        return name

    group_props: dict[str, dict[str, str]] = {}
    for p in all_properties:
        ng = _normalize_group(p["group"])
        if ng not in group_props:
            group_props[ng] = {}
        group_props[ng][p["name"]] = p["guid"]

    # Cache for resolved built-in property GUIDs
    builtin_cache: dict[str, str] = {}

    def resolve_builtin(nonloc_name: str) -> str:
        """Resolve a built-in property name to its GUID."""
        if nonloc_name in builtin_cache:
            return builtin_cache[nonloc_name]
        # We need the API port — get it from the first schedule def's connection info
        # or use direct HTTP
        try:
            import os
            p = int(os.getenv("_EBIF_AC_PORT", "19724"))
            r = requests.post(f"http://localhost:{p}", json={
                "command": "API.GetPropertyIds",
                "parameters": {"properties": [{"type": "BuiltIn", "nonLocalizedName": nonloc_name}]}
            }, timeout=10)
            data = r.json()
            if data.get("succeeded") and data["result"].get("properties"):
                guid = data["result"]["properties"][0].get("propertyId", {}).get("guid", "")
                builtin_cache[nonloc_name] = guid
                return guid
        except Exception:
            pass
        builtin_cache[nonloc_name] = ""
        return ""

    for sdef in schedule_defs:
        sid = sdef["id"]
        col_def = sched_cols.get(sid, default_cols)
        if isinstance(col_def, str) and col_def == "_default_columns":
            col_def = default_cols

        if not col_def:
            continue

        # Resolve each column to a GUID
        resolved: dict[str, str] = {}
        sched_norm_group = _normalize_group(sdef.get("group", ""))
        sched_group_props = group_props.get(sched_norm_group, {})
        general_props = group_props.get("GENERAL PROPERTIES", {})

        for col in col_def:
            label = col["label"]
            source = col["source"]

            if source.startswith("builtin:"):
                nonloc = source[len("builtin:"):]
                resolved[label] = resolve_builtin(nonloc)
            elif source.startswith("user:"):
                prop_name = source[len("user:"):]
                # Look in schedule's EBIF group first, then GENERAL PROPERTIES, then flat
                guid = sched_group_props.get(prop_name, "")
                if not guid:
                    guid = general_props.get(prop_name, "")
                if not guid:
                    guid = user_flat.get(prop_name, "")
                resolved[label] = guid
            else:
                resolved[label] = ""

        sdef["_column_defs"] = col_def
        sdef["_resolved_col_guids"] = resolved
        sdef["columns"] = [c["label"] for c in col_def]

        matched = sum(1 for v in resolved.values() if v)
        logger.debug("Schedule '%s': %d/%d columns resolved", sdef["name"], matched, len(col_def))
