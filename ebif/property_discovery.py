"""Property Discovery — auto-discovers property GUIDs from the live Archicad model.

Property GUIDs are project-specific in Archicad. This module fetches all
user-defined properties, matches them by group name and property name,
and builds a GUID map that the schedule extractor uses at runtime.
"""

import logging
import requests
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

        # Match data properties using normalized group name
        props = sdef.get("properties", {})
        resolved_props = {}
        for prop_name, old_guid in props.items():
            new_guid = norm_lookup.get((norm_group, prop_name), "")
            if not new_guid:
                # Try GENERAL PROPERTIES as fallback
                new_guid = norm_lookup.get(("GENERAL PROPERTIES", prop_name), "")
            if new_guid:
                resolved_props[prop_name] = new_guid
                matched_props += 1
            else:
                resolved_props[prop_name] = ""
                logger.debug("Property not found: '%s' in group '%s'", prop_name, group)
        sdef["properties"] = resolved_props

    # Find EBIF UID property (primary key — in EID/EBIF GENERAL PROPERTIES)
    ebif_uid_guid = norm_lookup.get(("GENERAL PROPERTIES", "EBIF UID"), "")
    if ebif_uid_guid:
        for sdef in schedule_defs:
            sdef["_ebif_uid_guid"] = ebif_uid_guid
        logger.info("Found EBIF UID: %s", ebif_uid_guid)
    else:
        logger.warning("EBIF UID property not found — using Archicad GUID as fallback")

    logger.info("Matched %d/%d toggles, %d property GUIDs",
                matched_toggles, len(schedule_defs), matched_props)
    return schedule_defs
