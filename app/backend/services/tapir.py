"""Tapir API Service — connects to Archicad via the Tapir Add-On.

Reuses the existing ebif/ pipeline modules for connection, property
discovery, and schedule extraction. Provides preview (counts only)
and full extraction for the web app.
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Add project root to sys.path so we can import ebif/ modules
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ebif.api_bridge import ArchicadConnection
from ebif.property_discovery import discover_all_properties, build_schedule_guid_map
from ebif.schedule_extractor import extract_all_schedules, extract_schedule


def _load_settings():
    settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
    with open(os.path.normpath(settings_path), 'r') as f:
        return json.load(f)


def _load_schedule_defs():
    """Load schedule definitions from config/schedules.json."""
    config_path = os.path.join(_PROJECT_ROOT, 'config', 'schedules.json')
    with open(config_path, 'r') as f:
        data = json.load(f)
    return data.get('schedules', [])


def get_port():
    """Return the Tapir port from settings.json."""
    settings = _load_settings()
    return settings.get('tapir_port', 19724)


def connect(port=None):
    """Connect to Archicad via Tapir. Raises ConnectionError on failure."""
    if port is None:
        port = get_port()
    # Set env var for modules that read it directly
    os.environ['_EBIF_AC_PORT'] = str(port)
    try:
        conn = ArchicadConnection(port=port)
        return conn
    except ConnectionError:
        raise
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to Archicad on port {port} — is it running with Tapir?"
        ) from e


def preview_counts(port=None):
    """Connect to Archicad, discover properties, and return element counts per schedule.

    Returns:
        dict with keys:
            counts: {schedule_id: int}
            schedules: [{id, name, count}]
            total: int
    """
    conn = connect(port)
    schedule_defs = _load_schedule_defs()
    p = conn.base_url.split(':')[-1]
    port_int = int(p) if p.isdigit() else get_port()

    # Discover properties and resolve GUIDs
    all_props = discover_all_properties(port_int)
    schedule_defs = build_schedule_guid_map(all_props, schedule_defs)

    # Extract counts by checking toggle properties
    counts = {}
    schedule_list = []
    total = 0

    # Pre-cache elements by type
    all_types = set()
    for sdef in schedule_defs:
        all_types.update(sdef['element_types'])

    cache = {}
    for etype in sorted(all_types):
        elems = conn.get_elements_by_type(etype)
        for e in elems:
            e['_type'] = etype
        cache[etype] = elems

    for sdef in schedule_defs:
        toggle_guid = sdef.get('toggle_guid')
        if not toggle_guid:
            counts[sdef['id']] = 0
            schedule_list.append({'id': sdef['id'], 'name': sdef['name'], 'count': 0})
            continue

        # Get elements of relevant types
        elements = []
        for etype in sdef['element_types']:
            elements.extend(cache.get(etype, []))

        if not elements:
            counts[sdef['id']] = 0
            schedule_list.append({'id': sdef['id'], 'name': sdef['name'], 'count': 0})
            continue

        # Check toggle property
        toggle_values = conn.get_property_values(
            elements,
            [{'propertyId': {'guid': toggle_guid}}],
        )

        count = 0
        for i, elem in enumerate(elements):
            if i < len(toggle_values):
                pvs = toggle_values[i].get('propertyValues', [])
                if pvs:
                    pv = pvs[0].get('propertyValue', {})
                    val = pv.get('value')
                    if isinstance(val, dict):
                        val = val.get('nonLocalizedValue', val.get('displayValue', str(val)))
                    if _is_yes(val):
                        count += 1

        counts[sdef['id']] = count
        total += count
        schedule_list.append({'id': sdef['id'], 'name': sdef['name'], 'count': count})

    return {
        'counts': counts,
        'schedules': schedule_list,
        'total': total,
    }


def full_extract(port=None):
    """Connect to Archicad, discover properties, extract all schedule data.

    Returns:
        dict with keys:
            schedules: {schedule_id: [row_dicts]}
            schedule_defs: list of schedule defs (with resolved GUIDs)
            counts: {schedule_id: int}
            total: int
    """
    conn = connect(port)
    schedule_defs = _load_schedule_defs()
    p = conn.base_url.split(':')[-1]
    port_int = int(p) if p.isdigit() else get_port()

    # Discover properties and resolve GUIDs
    all_props = discover_all_properties(port_int)
    schedule_defs = build_schedule_guid_map(all_props, schedule_defs)

    # Extract all schedules
    schedules = extract_all_schedules(conn, schedule_defs)

    counts = {sid: len(rows) for sid, rows in schedules.items()}
    total = sum(counts.values())

    return {
        'schedules': schedules,
        'schedule_defs': schedule_defs,
        'counts': counts,
        'total': total,
    }


def _is_yes(value):
    """Check if a property value represents Yes/True."""
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ('yes', 'true', '1', 'on')
