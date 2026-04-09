"""Excel Reader — reads current row counts from the EBIF Master Template.

Scans each schedule tab and counts data rows (row 5 onward with data in
column N, the EBIF UID column). This reflects the actual Excel state,
including manual edits.
"""

import logging
import os

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

# EBIF UID column varies per tab (2 cols after last manual column)
AC_START_DEFAULT = 14  # column N — most tabs
AC_START_OVERRIDES = {
    'furniture': 15,            # column O
    'decorative_lighting': 16,  # column P
}
DATA_START = 4

# Schedule tab name mapping (matches schedules.json IDs)
SCHEDULE_TABS = {
    'appliances': 'Appliances',
    'bath_accessories': 'Bath Accessories',
    'cabinetry_hardware': 'Cabinetry Hardware',
    'cabinetry_inserts': 'Cabinetry Inserts',
    'cabinetry_style': 'Cabinetry Style & Species',
    'countertops': 'Countertops',
    'decorative_lighting': 'Decorative Lighting',
    'door_hardware': 'Door Hardware',
    'flooring': 'Flooring',
    'furniture': 'Furniture',
    'lighting_electrical': 'Lighting & Electrical',
    'plumbing': 'Plumbing',
    'shower_glass_mirrors': 'Shower Glass & Mirrors',
    'specialty_equipment': 'Specialty Equipment',
    'surface_finishes': 'Surface Finishes',
    'tile': 'Tile',
}


def read_excel_counts(project):
    """Read row counts per schedule tab from the project's Excel file.

    Args:
        project: Project dict with folder_location, excel_filename, project_name

    Returns dict mapping schedule_id -> count, or None if file not found.
    """
    from services.template import get_excel_path
    xlsm_path = get_excel_path(project)

    if not os.path.exists(xlsm_path):
        return None

    try:
        wb = load_workbook(xlsm_path, read_only=True, data_only=True)
    except Exception as e:
        logger.warning("Could not read Excel file: %s", e)
        return None

    counts = {}
    for sid, tab_name in SCHEDULE_TABS.items():
        ws = _find_sheet(wb, tab_name)
        if ws is None:
            counts[sid] = 0
            continue

        ac_col = AC_START_OVERRIDES.get(sid, AC_START_DEFAULT)
        count = 0
        for row in ws.iter_rows(min_row=DATA_START, min_col=ac_col, max_col=ac_col, values_only=True):
            if row[0] is not None and str(row[0]).strip():
                count += 1
            else:
                break  # stop at first empty EBIF UID
        counts[sid] = count

    wb.close()
    return counts


def _find_sheet(wb, schedule_name):
    """Find sheet by name, handling emoji prefixes."""
    for sheet_name in wb.sheetnames:
        if sheet_name == schedule_name:
            return wb[sheet_name]
        # Strip emoji prefix
        stripped = sheet_name
        while stripped and (not stripped[0].isascii() or stripped[0] == ' '):
            stripped = stripped[1:]
        if stripped == schedule_name:
            return wb[sheet_name]
        if sheet_name.endswith(schedule_name):
            return wb[sheet_name]
    return None
