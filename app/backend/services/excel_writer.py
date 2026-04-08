"""EBIF Master Template Excel Writer — writes Archicad data into the template.

All Archicad data is written starting at column N (14) onward:
  N = EBIF UID, O = QTY, P = Tear Sheet #, Q = Location,
  R+ = Element Type, Library Part Name, Layer, Classifications, etc.

Columns A–D contain formulas that reference the Archicad data:
  A =N{row}  (EBIF UID)
  B =O{row}  (QTY)
  C =P{row}  (Tear Sheet #)
  D =Q{row}  (Location)

Columns E–K are MANUAL (never touched). L–M are empty (never touched).
Table of Contents tab is never modified.

Row 4 = header row. Data starts at row 5.
On refresh, clears A–D and N onward from row 5 down. Also clears any
stray data in L–M from previous buggy writes.

Excel Table objects are removed before writing to prevent repair errors.

Uses openpyxl with keep_vba=True to preserve macros.
"""

import logging
import os

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# EID Brand Colors
OLIVE = "868C54"
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

HEADER_ROW = 4
DATA_START = 5

# Archicad data starts at column N (14) — NOTHING before this
AC_START = 14  # column N

# Core 4 Archicad fields written at N(14), O(15), P(16), Q(17)
CORE_FIELDS = [
    ("EBIF UID", "EBIF UID"),
    ("QTY", "Qty"),
    ("Tear Sheet #", "TEAR SHEET #"),
    ("Location", "Location"),
]

# Columns A–D get formulas referencing N–Q
FORMULA_COLS = [1, 2, 3, 4]  # A, B, C, D
FORMULA_SRC_COLS = [14, 15, 16, 17]  # N, O, P, Q

# Tabs to skip
SKIP_TABS = {"Table of Contents"}


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

        # Find matching sheet (handles emoji prefixes)
        ws = _find_sheet(wb, sname)

        if ws is None:
            logger.warning("Sheet not found for '%s' — skipping", sname)
            result[sid] = 0
            continue

        # Skip Table of Contents
        if any(skip in ws.title for skip in SKIP_TABS):
            result[sid] = 0
            continue

        # Remove Excel Table objects to prevent repair errors
        _remove_tables(ws)

        # Build list of extra reference labels beyond the core 4
        archicad_labels = sdef.get('_archicad_col_labels', [])
        core_keys = {f[1] for f in CORE_FIELDS}
        ref_labels = [lbl for lbl in archicad_labels if lbl not in core_keys]

        # Total Archicad columns: 4 core + N reference
        total_ac_cols = 4 + len(ref_labels)

        # Clear old data: A–D, L–M (stray), and N onward from row 5 down
        _clear_data(ws, total_ac_cols)

        # Write Archicad data headers at row 4, starting at column N
        all_headers = [f[0] for f in CORE_FIELDS] + ref_labels
        for j, header in enumerate(all_headers):
            col = AC_START + j
            cell = ws.cell(row=HEADER_ROW, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = THIN_BORDER

        # Write data rows
        for i, row_data in enumerate(rows):
            row_num = DATA_START + i

            # Core 4 fields at N(14), O(15), P(16), Q(17)
            _write_cell(ws, row_num, AC_START + 0, row_data.get('EBIF UID', ''), i)
            _write_cell(ws, row_num, AC_START + 1, row_data.get('Qty', 1), i)
            _write_cell(ws, row_num, AC_START + 2, row_data.get('TEAR SHEET #', ''), i)
            _write_cell(ws, row_num, AC_START + 3, row_data.get('Location', ''), i)

            # Extra reference columns at R(18), S(19), T(20), ...
            for j, lbl in enumerate(ref_labels):
                col = AC_START + 4 + j
                _write_cell(ws, row_num, col, row_data.get(lbl, ''), i)

            # Formulas in A–D referencing N–Q
            for dest_col, src_col in zip(FORMULA_COLS, FORMULA_SRC_COLS):
                src_letter = get_column_letter(src_col)
                cell = ws.cell(row=row_num, column=dest_col, value=f"={src_letter}{row_num}")
                cell.font = BODY_FONT
                cell.border = THIN_BORDER
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                cell.fill = LOCKED_ALT_FILL if i % 2 == 0 else LOCKED_FILL

        result[sid] = len(rows)
        logger.info("Wrote %d rows to sheet '%s'", len(rows), ws.title)

    wb.save(xlsm_path)
    logger.info("Saved EBIF Master Template: %s", xlsm_path)
    return result


def _remove_tables(ws):
    """Remove all Excel Table objects from a worksheet.

    Excel Tables (ListObjects) cause repair errors when openpyxl writes
    data into cells that overlap with a table's range. Removing them
    preserves the cell data but eliminates the structured table definition.
    """
    if hasattr(ws, '_tables') and ws._tables:
        table_names = [t.name for t in ws._tables]
        ws._tables = []
        logger.info("Removed %d Excel Table(s) from '%s': %s",
                     len(table_names), ws.title, ', '.join(table_names))


def _find_sheet(wb, schedule_name):
    """Find a sheet by schedule name, handling emoji prefixes.

    Sheets have emoji prefixes like '🍳 Appliances'. We match by checking
    if any sheet name ends with the schedule name.
    """
    if schedule_name in wb.sheetnames:
        return wb[schedule_name]

    for sheet_name in wb.sheetnames:
        # Strip leading non-ASCII characters and spaces (emoji prefix)
        stripped = sheet_name
        while stripped and (not stripped[0].isascii() or stripped[0] == ' '):
            stripped = stripped[1:]
        after_emoji = sheet_name[2:] if len(sheet_name) > 2 else sheet_name

        if stripped == schedule_name or after_emoji == schedule_name:
            return wb[sheet_name]
        if sheet_name.endswith(schedule_name):
            return wb[sheet_name]

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


def _clear_data(ws, total_ac_cols):
    """Clear old Archicad data from row 5 downward.

    Clears:
      - Columns A–D (1–4) — old formulas
      - Columns L–M (12–13) — stray data from previous buggy writes
      - Column N (14) onward — old Archicad data
    NEVER touches columns E–K (5–11) — manual columns.
    """
    max_row = ws.max_row or DATA_START
    if max_row < DATA_START:
        return

    # Determine the furthest column to clear
    max_ac_col = AC_START + total_ac_cols
    furthest = max(max_ac_col, ws.max_column + 1) if ws.max_column else max_ac_col

    for row_num in range(DATA_START, max_row + 1):
        # Clear A–D (formula columns)
        for col in range(1, 5):
            ws.cell(row=row_num, column=col).value = None

        # Clear L–M (12–13) — fix stray data from previous writes
        for col in range(12, 14):
            ws.cell(row=row_num, column=col).value = None

        # Clear N onward (Archicad data columns)
        for col in range(AC_START, furthest):
            ws.cell(row=row_num, column=col).value = None
