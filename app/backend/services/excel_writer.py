"""Master Schedule Excel Writer — writes Archicad data into EBIF Master Template.xlsm.

Opens the project's existing .xlsm workbook, finds each schedule's sheet,
and writes ONLY Archicad-sourced columns. Manual columns (vendor, cost, notes)
are NEVER touched.

Uses openpyxl with keep_vba=True to preserve macros.
"""

import logging
import os

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, Protection

logger = logging.getLogger(__name__)

# EID Brand Colors
OLIVE = "868C54"
SAGE = "C2C8A2"
WARM_GRAY = "737569"
WHITE = "FFFFFF"

# Styling for Archicad data cells
HEADER_FONT = Font(name="Lato", bold=True, color=WHITE, size=10)
HEADER_FILL = PatternFill(start_color=OLIVE, end_color=OLIVE, fill_type="solid")
BODY_FONT = Font(name="Arial Narrow", color="2C2C2C", size=10)
LOCKED_FILL = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")
LOCKED_ALT_FILL = PatternFill(start_color="DCDCDC", end_color="DCDCDC", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)

# Columns that are always Archicad-sourced (locked)
ALWAYS_ARCHICAD = {"EBIF UID", "Element ID", "TEAR SHEET #", "Qty"}


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
        raise FileNotFoundError(f"Master Schedule not found: {xlsm_path}")

    wb = load_workbook(xlsm_path, keep_vba=True)
    result = {}
    total_steps = len(schedule_defs)

    # Build a lookup from schedule name -> schedule def
    sdef_by_name = {}
    sdef_by_id = {}
    for sdef in schedule_defs:
        sdef_by_name[sdef['name']] = sdef
        sdef_by_id[sdef['id']] = sdef

    for step, sdef in enumerate(schedule_defs, start=1):
        sid = sdef['id']
        sname = sdef['name']
        rows = schedules.get(sid, [])

        if on_progress:
            on_progress(step, total_steps, sname)

        if not rows:
            result[sid] = 0
            continue

        # Find matching sheet — try exact name, then truncated (Excel max 31 chars)
        ws = None
        for candidate in [sname, sname[:31]]:
            if candidate in wb.sheetnames:
                ws = wb[candidate]
                break

        if ws is None:
            # Create the sheet if it doesn't exist
            ws = wb.create_sheet(title=sname[:31])
            logger.info("Created new sheet '%s'", sname[:31])

        # Determine which columns are Archicad-sourced (safe to write)
        archicad_labels = set(sdef.get('_archicad_col_labels', []))
        archicad_cols = ALWAYS_ARCHICAD | archicad_labels

        # Build the full column list for this schedule
        all_columns = list(ALWAYS_ARCHICAD) + sdef.get('columns', [])
        # Deduplicate while preserving order
        seen = set()
        columns = []
        for c in all_columns:
            if c not in seen:
                columns.append(c)
                seen.add(c)

        # Find or create header row
        header_row = _find_header_row(ws)

        if header_row is None:
            # No existing header — write fresh starting at row 1
            header_row = 1
            _write_headers(ws, header_row, columns)
            data_start = header_row + 1
            col_map = {col: idx + 1 for idx, col in enumerate(columns)}
        else:
            # Read existing headers to find column positions
            col_map = _read_header_map(ws, header_row)
            # Add any missing Archicad columns at the end
            max_col = max(col_map.values()) if col_map else 0
            for col in columns:
                if col not in col_map and col in archicad_cols:
                    max_col += 1
                    col_map[col] = max_col
                    cell = ws.cell(row=header_row, column=max_col, value=col)
                    cell.font = HEADER_FONT
                    cell.fill = HEADER_FILL
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.border = THIN_BORDER
            data_start = header_row + 1

        # Clear old Archicad data in safe columns only
        _clear_archicad_columns(ws, data_start, col_map, archicad_cols)

        # Write rows — ONLY to Archicad-sourced columns
        for i, row_data in enumerate(rows):
            row_num = data_start + i
            for col_name, col_idx in col_map.items():
                if col_name not in archicad_cols:
                    continue  # NEVER touch manual columns

                val = row_data.get(col_name, '')
                if val is None:
                    val = ''
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.font = BODY_FONT
                cell.border = THIN_BORDER
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                cell.fill = LOCKED_ALT_FILL if i % 2 == 0 else LOCKED_FILL

        result[sid] = len(rows)
        logger.info("Wrote %d rows to sheet '%s'", len(rows), sname[:31])

    wb.save(xlsm_path)
    logger.info("Saved Master Schedule: %s", xlsm_path)
    return result


def _find_header_row(ws):
    """Find the header row by looking for 'Element ID' in the first 15 rows."""
    for row_num in range(1, 16):
        for col_num in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_num, column=col_num)
            if cell.value and str(cell.value).strip() == 'Element ID':
                return row_num
    return None


def _read_header_map(ws, header_row):
    """Read column headers and return {header_name: col_index}."""
    col_map = {}
    for col_num in range(1, ws.max_column + 1):
        val = ws.cell(row=header_row, column=col_num).value
        if val is not None:
            col_map[str(val).strip()] = col_num
    return col_map


def _write_headers(ws, row, columns):
    """Write a styled header row."""
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=row, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def _clear_archicad_columns(ws, data_start, col_map, archicad_cols):
    """Clear existing data in Archicad-sourced columns only."""
    max_row = ws.max_row or data_start
    for row_num in range(data_start, max_row + 1):
        for col_name, col_idx in col_map.items():
            if col_name in archicad_cols:
                ws.cell(row=row_num, column=col_idx).value = None
