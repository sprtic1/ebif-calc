"""MCP Bridge — assembles raw MCP API responses into the pipeline's raw_walls format.

Converts between the MCP ArchiCAD tool response format and the dict format
expected by wall_parser.parse_walls(). Also handles display-string parsing
(feet-inches → meters) since MCP returns formatted property values.
"""

import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

IN2M = 0.0254  # inches to meters
FT2M = 0.3048  # feet to meters

# Property GUIDs (ArchiCAD built-in)
P_WIDTH = "3799b10a-61c5-4566-bf9c-eaa9ce49196e"
P_HEIGHT = "c4b62357-1289-4d43-a3f6-ab02b192864c"
P_THICKNESS = "a7b55e43-7c56-4c9e-836d-7a56f1d9d760"
P_ELEMENT_ID = "7e221f33-829b-4fbc-a670-e74dabce6289"
P_COMPOSITE = "704e9212-3e21-4790-bae4-cf3de2395481"
P_STRUCTURE = "98a26d3b-3baf-4019-be7a-09285ffa597c"
P_REF_LINE_LENGTH = "736276cc-0825-4738-a2e8-cdd740c7f635"

# Property list for wall fetch (order matters — matches index in assembly)
WALL_PROPERTIES = [
    {"propertyId": {"guid": P_WIDTH}},
    {"propertyId": {"guid": P_HEIGHT}},
    {"propertyId": {"guid": P_THICKNESS}},
    {"propertyId": {"guid": P_ELEMENT_ID}},
    {"propertyId": {"guid": P_COMPOSITE}},
    {"propertyId": {"guid": P_STRUCTURE}},
    {"propertyId": {"guid": P_REF_LINE_LENGTH}},
]

# Property list for opening fetch
OPENING_PROPERTIES = [
    {"propertyId": {"guid": P_WIDTH}},
    {"propertyId": {"guid": P_HEIGHT}},
]

# Regex for feet-inches display strings: 10'-6", 0'-8", 10', 6"
_FT_IN_RE = re.compile(
    r"""(?:(\d+(?:\.\d+)?)\s*')    # feet part (optional)
        (?:\s*-?\s*                  # optional separator
        (\d+(?:\.\d+)?)\s*")?       # inches part (optional)
    |   (\d+(?:\.\d+)?)\s*"         # inches only
    """,
    re.VERBOSE,
)


def parse_display_to_meters(s: str) -> float:
    """Parse ArchiCAD display string (feet-inches) to meters.

    Handles: "10'-6\"", "0'-8\"", "10'", "8\"", "3.048", plain numbers.
    """
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)

    s = str(s).strip()
    if not s:
        return 0.0

    m = _FT_IN_RE.search(s)
    if m:
        ft = float(m.group(1) or 0)
        inches = float(m.group(2) or 0)
        inches_only = m.group(3)
        if inches_only is not None:
            return float(inches_only) * IN2M
        return ft * FT2M + inches * IN2M

    # Fallback: try as plain number (already in meters)
    try:
        return float(s)
    except ValueError:
        logger.warning("Cannot parse display value: %r", s)
        return 0.0


def _pv(prop_values: list, idx: int) -> str | None:
    """Extract property value at index from MCP propertyValues list."""
    if idx < len(prop_values) and "propertyValue" in prop_values[idx]:
        return prop_values[idx]["propertyValue"].get("value")
    return None


def assemble_walls(
    elements: dict,
    details: dict,
    properties: dict,
    stories: dict,
    opening_data: dict,
    editable_guids: set[str] | None = None,
) -> list[dict]:
    """Assemble raw_walls list from MCP API responses.

    Args:
        elements: Response from elements_get_elements_by_type(Wall)
        details: Response from elements_get_details_of_elements(walls)
        properties: Response from properties_get_property_values_of_elements(walls, 7 props)
        stories: Response from project_get_stories
        opening_data: Dict with keys 'doors' and 'windows', each containing
                      {elements, details, properties} from their respective MCP calls.
        editable_guids: Set of GUIDs that passed the IsEditable filter.
                        If None, all walls are assumed editable.

    Returns:
        List of wall dicts in the format expected by wall_parser.parse_walls().
    """
    elems = elements.get("elements", [])
    dets = details.get("detailsOfElements", [])
    pvs = properties.get("propertyValuesForElements", [])

    # Build story map
    story_list = stories.get("stories", [])
    story_map = {s["index"]: s["name"] for s in story_list}

    # Build openings map
    openings = _assemble_openings(opening_data)

    walls = []
    for i, el in enumerate(elems):
        guid = el["elementId"]["guid"]
        det = dets[i] if i < len(dets) else {}
        dd = det.get("details", {})
        fi = det.get("floorIndex", 0)

        pv = pvs[i]["propertyValues"] if i < len(pvs) else []

        width_val = _pv(pv, 0)
        height_val = _pv(pv, 1)
        thickness_val = _pv(pv, 2)
        eid = str(_pv(pv, 3) or "")
        composite = _pv(pv, 4)
        structure = str(_pv(pv, 5) or "Basic")
        ref_line_len_val = _pv(pv, 6)

        # MCP returns display strings — parse to meters
        width_m = parse_display_to_meters(width_val)
        height_m = parse_display_to_meters(height_val)
        thickness_m = parse_display_to_meters(thickness_val)
        ref_line_length_m = parse_display_to_meters(ref_line_len_val)

        walls.append({
            "guid": guid,
            "element_id": eid,
            "beg": dd.get("begCoordinate", {}),
            "end": dd.get("endCoordinate", {}),
            "arc_angle": dd.get("arcAngle", 0.0) or 0.0,
            "floor_index": int(fi),
            "story_name": story_map.get(int(fi), f"Floor {int(fi)}"),
            "height_m": dd.get("height", 0) or 0,
            "width_m": width_m,
            "height_prop_m": height_m,
            "thickness_m": thickness_m,
            "ref_line_length_m": ref_line_length_m,
            "composite_name": composite,
            "structure_type": structure,
            "openings": openings.get(guid.upper(), []),
            "is_editable": guid in editable_guids if editable_guids is not None else True,
        })

    logger.info("Assembled %d wall records from MCP data", len(walls))
    return walls


def _assemble_openings(opening_data: dict) -> dict[str, list[dict]]:
    """Assemble openings map from MCP door/window responses."""
    result: dict[str, list[dict]] = defaultdict(list)

    for etype in ("doors", "windows"):
        data = opening_data.get(etype, {})
        elems = data.get("elements", {}).get("elements", [])
        dets = data.get("details", {}).get("detailsOfElements", [])
        pvs = data.get("properties", {}).get("propertyValuesForElements", [])

        for j, el in enumerate(elems):
            det = dets[j] if j < len(dets) else {}
            owner = det.get("details", {}).get("ownerElementId", {}).get("guid", "")
            if not owner:
                continue

            pv = pvs[j]["propertyValues"] if j < len(pvs) else []
            w_val = _pv(pv, 0)
            h_val = _pv(pv, 1)

            result[owner.upper()].append({
                "type": etype.rstrip("s"),  # "doors" → "door"
                "width_m": parse_display_to_meters(w_val),
                "height_m": parse_display_to_meters(h_val),
            })

        if elems:
            logger.info("  %d %s mapped to walls", len(elems), etype)

    return dict(result)


def build_writeback_entries(
    renco_walls,
    excluded_renco,
    eid_guid: str,
    report_guid: str,
    renco_report_fn,
) -> list[dict]:
    """Build the writeback entries list for MCP SetPropertyValuesOfElements.

    Args:
        renco_walls: List of calculated Wall objects
        excluded_renco: List of excluded Renco Wall objects
        eid_guid: GUID for Element ID property
        report_guid: GUID for RENCO REPORT property (empty string to skip)
        renco_report_fn: Function that takes a Wall and returns report string

    Returns:
        List of dicts ready for properties_set_property_values_of_elements.
    """
    entries = []
    for w in list(renco_walls) + list(excluded_renco):
        entries.append({
            "elementId": {"guid": w.guid},
            "propertyId": {"guid": eid_guid},
            "propertyValue": {"type": "string", "status": "normal", "value": w.wall_id},
        })
        if report_guid:
            entries.append({
                "elementId": {"guid": w.guid},
                "propertyId": {"guid": report_guid},
                "propertyValue": {"type": "string", "status": "normal", "value": renco_report_fn(w)},
            })
    return entries


def build_clear_entries(guids: list[str], report_guid: str) -> list[dict]:
    """Build entries to clear RENCO REPORT on all walls."""
    if not report_guid:
        return []
    return [
        {
            "elementId": {"guid": g},
            "propertyId": {"guid": report_guid},
            "propertyValue": {"type": "string", "status": "normal", "value": ""},
        }
        for g in guids
    ]


def build_strip_x_entries(
    guids: list[str],
    eid_properties: dict,
    eid_guid: str,
) -> list[dict]:
    """Build entries to strip X suffixes from Element IDs.

    Args:
        guids: All wall GUIDs
        eid_properties: Response from properties_get_property_values_of_elements
                       for just the Element ID property
        eid_guid: GUID for the Element ID property

    Returns:
        List of entries for walls that had X suffixes to strip.
    """
    pvs = eid_properties.get("propertyValuesForElements", [])
    entries = []
    for i, g in enumerate(guids):
        cur = ""
        if i < len(pvs):
            pv = pvs[i].get("propertyValues", [])
            if pv and "propertyValue" in pv[0]:
                cur = str(pv[0]["propertyValue"].get("value", ""))
        clean = re.sub(r"X+$", "", cur, flags=re.IGNORECASE)
        if clean != cur:
            entries.append({
                "elementId": {"guid": g},
                "propertyId": {"guid": eid_guid},
                "propertyValue": {"type": "string", "status": "normal", "value": clean},
            })
    return entries
