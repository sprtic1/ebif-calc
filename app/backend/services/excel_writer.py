"""EBIF Master Template Excel Writer — writes Archicad data into the template.

Fixed column layout for ALL 16 schedule tabs:
  A = EBIF UID       (Archicad)
  B = QTY            (Archicad)
  C = Tear Sheet #   (Archicad)
  D = Location       (Archicad)
  E–K = MANUAL       (never touch — Manufacturer, Model, Size, Finish, Notes, Cost, URL)
  L+ = Reference     (Archicad — additional reference data after manual columns)

Exception: Decorative Lighting tab has manual columns E–M, reference starts at N.

Row 4 = header row. Data starts at row 5.
Old PQ formulas in A–D are replaced with actual Archicad values.
On refresh, clears A–D and reference columns from row 5 down, NEVER touches manual columns.

Uses openpyxl with keep_vba=True to preserve macros.
"""

import logging
import os

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

logger = logging.getLogger(__name__)

# EID Brand Colors
OLIVE = "868C54"
WARM_GRAY = "737569"
WHITE = "FFFFFF"

# Styling
BODY_FONT = Font(name="Arial Narrow", color="2C2C2C", size=10)
HEADER_FONT = Font(name="Lato", bold=True, color=WHITE, size=10)
HEADER_FILL = PatternFill(start_color=OLIVE, end_color=OLIVE, fill_type="solid")
LOCKED_FILL = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")
LOCKED_ALT_FILL = PatternFill(start_color="DCDCDC", end_color="DCDCDC", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)

# Fixed Archicad columns (1-indexed): A=1, B=2, C=3, D=4
ARCHICAD_COLS = {
    1: "EBIF UID",
    2: "Qty",
    3: "TEAR SHEET #",
    4: "Location",
}

HEADER_ROW = 4
DATA_START = 5

# Manual column ranges (1-indexed, inclusive) — NEVER write to these
# Most tabs: E(5) through K(11)
MANUAL_RANGE_DEFAULT = (5, 11)    # E–K
# Decorative Lighting: E(5) through M(13)
MANUAL_RANGE_LIGHTING = (5, 13)   # E–M

# Reference data starts after manual columns
REF_START_DEFAULT = 12   # column L
REF_START_LIGHTING = 14  # column N

# Schedule ID for Decorative Lighting
LIGHTING_ID = "decorative_lighting"


def write_to_master(
    project_folder,
    schedules,
    schedule_defs,
    on_progress=None,
):
    """Write Archicad data into the project's EBIF Master Template.xlsm.

    Args:
        project_folder: Full path to the project folder
        schedules: dict mapping schedule_id -> list of row dicts
        schedule_defs: list of schedule definition dicts (with resolved column info)
        on_progress: Optional callback(step, total, schedule_name) called after each category

    Returns:
        dict mapping schedule_id -> number of rows written
    """
    xlsm_path = os.path.join(project_folder, 'EBIF', 'EXCEL', 'MASTER', 'EBIF Master Template.xlsm')

    if not os.path.exists(xlsm_path):
        raise FileNotFoundError(f"EBIF Master Template not found: {xlsm_path}")

    wb = load_workbook(xlsm_path, keep_vba=True)
    result = {}
    total_steps = len(schedule_defs)

    for step, sdef in enumerate(schedule_defs, start=1):
        sid = sdef['id']
        sname = sdef['name']
        rows = schedules.get(sid, [])

        if on_progress:
            on_progress(step, total_steps, sname)

        if not rows:
            result[sid] = 0
            continue

        # Find matching sheet — tabs have emoji prefixes (e.g. "🍳 Appliances")
        ws = _find_sheet(wb, sname)

        if ws is None:
            logger.warning("Sheet not found for '%s' — skipping", sname)
            result[sid] = 0
            continue

        # Determine reference column start based on schedule type
        is_lighting = (sid == LIGHTING_ID)
        ref_start = REF_START_LIGHTING if is_lighting else REF_START_DEFAULT
        manual_range = MANUAL_RANGE_LIGHTING if is_lighting else MANUAL_RANGE_DEFAULT

        # Build list of reference column labels (additional Archicad data after manual cols)
        archicad_labels = sdef.get('_archicad_col_labels', [])
        # Filter out the 4 fixed columns already handled
        fixed_labels = set(ARCHICAD_COLS.values())
        ref_labels = [lbl for lbl in archicad_labels if lbl not in fixed_labels]

        # Clear old Archicad data from row 5 downward (columns A–D + reference columns)
        _clear_archicad_data(ws, ref_start, len(ref_labels), manual_range)

        # Write data rows starting at row 5
        for i, row_data in enumerate(rows):
            row_num = DATA_START + i

            # A = EBIF UID
            _write_cell(ws, row_num, 1, row_data.get('EBIF UID', ''), i)
            # B = QTY
            _write_cell(ws, row_num, 2, row_data.get('Qty', 1), i)
            # C = Tear Sheet #
            _write_cell(ws, row_num, 3, row_data.get('TEAR SHEET #', ''), i)
            # D = Location
            _write_cell(ws, row_num, 4, row_data.get('Location', ''), i)

            # Reference columns (L+ or N+ for lighting)
            for j, lbl in enumerate(ref_labels):
                col_idx = ref_start + j
                _write_cell(ws, row_num, col_idx, row_data.get(lbl, ''), i)

        # Write reference column headers at row 4 if we have any
        for j, lbl in enumerate(ref_labels):
            col_idx = ref_start + j
            cell = ws.cell(row=HEADER_ROW, column=col_idx, value=lbl)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = THIN_BORDER

        result[sid] = len(rows)
        logger.info("Wrote %d rows to sheet '%s'", len(rows), ws.title)

    wb.save(xlsm_path)
    logger.info("Saved EBIF Master Template: %s", xlsm_path)
    return result


def _find_sheet(wb, schedule_name):
    """Find a sheet by schedule name, handling emoji prefixes.

    Sheets have emoji prefixes like '🍳 Appliances'. We match by checking
    if any sheet name ends with the schedule name (after the emoji + space).
    """
    # Try exact match first
    if schedule_name in wb.sheetnames:
        return wb[schedule_name]

    # Try matching the part after the emoji prefix
    for sheet_name in wb.sheetnames:
        # Strip leading emoji characters and spaces
        stripped = sheet_name
        while stripped and (not stripped[0].isascii() or stripped[0] == ' '):
            stripped = stripped[1:]
        # Also try stripping just the first 2 chars (emoji + space)
        after_emoji = sheet_name[2:] if len(sheet_name) > 2 else sheet_name

        if stripped == schedule_name or after_emoji == schedule_name:
            return wb[sheet_name]

        # Fuzzy: check if schedule_name is contained at the end
        if sheet_name.endswith(schedule_name):
            return wb[sheet_name]

    # Try truncated (Excel max 31 chars)
    truncated = schedule_name[:31]
    if truncated in wb.sheetnames:
        return wb[truncated]

    return None


def _write_cell(ws, row, col, value, row_index):
    """Write a single cell with Archicad styling."""
    if value is None:
        value = ''
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = BODY_FONT
    cell.border = THIN_BORDER
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    cell.fill = LOCKED_ALT_FILL if row_index % 2 == 0 else LOCKED_FILL


def _clear_archicad_data(ws, ref_start, ref_count, manual_range):
    """Clear old Archicad data from row 5 downward.

    Clears columns A–D (1–4) and reference columns (ref_start onward).
    NEVER touches manual columns (manual_range).
    """
    max_row = ws.max_row or DATA_START
    if max_row < DATA_START:
        return

    manual_start, manual_end = manual_range

    for row_num in range(DATA_START, max_row + 1):
        # Clear columns A–D
        for col in range(1, 5):
            ws.cell(row=row_num, column=col).value = None

        # Clear reference columns after manual range
        for col_offset in range(ref_count):
            col = ref_start + col_offset
            if col < manual_start or col > manual_end:
                ws.cell(row=row_num, column=col).value = None

        # Also clear any leftover data in columns beyond the manual range
        # that might have old PQ formulas
        for col in range(ref_start, ws.max_column + 1):
            if col < manual_start or col > manual_end:
                ws.cell(row=row_num, column=col).value = None
