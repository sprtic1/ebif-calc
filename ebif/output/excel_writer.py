"""EID-Branded Excel Writer — generates multi-tab workbook with all schedules.

Two modes:
  - Template mode (Step 1): Pre-populated with Archicad data, blanks for manual entry.
    Uses a stable filename so the user edits and re-saves in place.
  - Final mode (Step 2): Full workbook with QC tab after publish.

Uses EID brand colors: Olive #868C54, Sage #C2C8A2, Warm Gray #737569.
"""

import logging
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, NamedStyle
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# EID Brand Colors
OLIVE = "868C54"
SAGE = "C2C8A2"
WARM_GRAY = "737569"
WHITE = "FFFFFF"
LIGHT_YELLOW = "FFFFF0"

# Fonts
HEADER_FONT = Font(name="Lato", bold=True, color=WHITE, size=10)
BODY_FONT = Font(name="Arial Narrow", color="2C2C2C", size=10)
TITLE_FONT = Font(name="Lato", bold=True, color=OLIVE, size=14)
SUBTITLE_FONT = Font(name="Lato", color=WARM_GRAY, size=11)
BLANK_FONT = Font(name="Arial Narrow", color="999999", size=10, italic=True)

# Fills
HEADER_FILL = PatternFill(start_color=OLIVE, end_color=OLIVE, fill_type="solid")
ALT_ROW_FILL = PatternFill(start_color=SAGE, end_color=SAGE, fill_type="solid")
WHITE_FILL = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")
EDITABLE_FILL = PatternFill(start_color=LIGHT_YELLOW, end_color=LIGHT_YELLOW, fill_type="solid")

# Borders
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


def _auto_width(ws, min_width: int = 10, max_width: int = 40):
    """Auto-fit column widths based on content."""
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        max_len = min_width
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 100), min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)) + 2, max_width))
        ws.column_dimensions[col_letter].width = max_len


def _write_header_row(ws, row: int, columns: list[str]):
    """Write a styled header row."""
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=row, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def _write_data_rows(ws, start_row: int, rows: list[dict], columns: list[str]):
    """Write data rows with alternating color."""
    for i, data_row in enumerate(rows):
        row_num = start_row + i
        fill = ALT_ROW_FILL if i % 2 == 0 else WHITE_FILL
        for col_idx, col_name in enumerate(columns, start=1):
            val = data_row.get(col_name, "")
            if val is None:
                val = ""
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.font = BODY_FONT
            cell.fill = fill
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True)


def write_summary_sheet(wb: Workbook, schedules: dict, schedule_defs: list[dict],
                        project_name: str, qc_issues: list[dict], mode: str = "template"):
    """Write the Summary tab."""
    ws = wb.active
    ws.title = "Summary"

    # Title
    ws.cell(row=1, column=1, value="EBIF-CALC").font = Font(name="Lato", bold=True, color=OLIVE, size=20)
    ws.cell(row=2, column=1, value="Ellis Building Intelligence Framework").font = SUBTITLE_FONT
    ws.cell(row=3, column=1, value=project_name).font = Font(name="Arial Narrow", color=WARM_GRAY, size=11)

    mode_label = "Working Document (Step 1 — fill in spec data)" if mode == "template" else "Published Report (Step 2)"
    ws.cell(row=4, column=1, value=mode_label).font = Font(
        name="Arial Narrow", color=OLIVE, size=10, bold=True, italic=True)
    ws.cell(row=5, column=1, value=f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}").font = Font(
        name="Arial Narrow", color=WARM_GRAY, size=9, italic=True)

    # Schedule summary table
    row = 7
    if mode == "template":
        headers = ["#", "Schedule", "Elements", "Fields Populated", "Fields Blank"]
    else:
        headers = ["#", "Schedule", "Elements", "Warnings", "Complete"]
    _write_header_row(ws, row, headers)

    row = 8
    total_elements = 0
    for idx, sdef in enumerate(schedule_defs, start=1):
        sid = sdef["id"]
        sched_rows = schedules.get(sid, [])
        count = len(sched_rows)
        total_elements += count

        if mode == "template":
            populated, blank = _count_fill_status(sched_rows, sdef.get("columns", []))
            vals = [idx, sdef["name"], count, populated, blank]
        else:
            warnings = sum(1 for q in qc_issues if q["schedule"] == sdef["name"] and q["severity"] == "Warning")
            complete = count - warnings if count > 0 else 0
            vals = [idx, sdef["name"], count, warnings, complete]

        fill = ALT_ROW_FILL if idx % 2 == 0 else WHITE_FILL
        for col_idx, val in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = BODY_FONT
            cell.fill = fill
            cell.border = THIN_BORDER
        row += 1

    # Totals row
    for col_idx, val in enumerate(["", "TOTAL", total_elements, "", ""], start=1):
        cell = ws.cell(row=row, column=col_idx, value=val)
        cell.font = Font(name="Lato", bold=True, color=OLIVE, size=10)
        cell.border = THIN_BORDER

    _auto_width(ws)
    logger.info("Summary tab: %d schedules, %d total elements", len(schedule_defs), total_elements)


def _count_fill_status(rows: list[dict], columns: list[str]) -> tuple[int, int]:
    """Count populated vs blank fields across all rows and columns."""
    populated = 0
    blank = 0
    skip = {"Element ID", "Qty", "Zone", "Room"}
    for row in rows:
        for col in columns:
            if col in skip:
                continue
            val = row.get(col, "")
            if val is not None and str(val).strip() not in ("", "None", "0"):
                populated += 1
            else:
                blank += 1
    return populated, blank


def write_schedule_sheet(wb: Workbook, schedule_def: dict, rows: list[dict]):
    """Write a single schedule tab with all columns."""
    sname = schedule_def["name"]
    tab_name = sname[:31]
    ws = wb.create_sheet(title=tab_name)

    # Columns: Element ID + all schedule columns + Qty
    columns = ["Element ID"] + schedule_def.get("columns", []) + ["Qty"]
    _write_header_row(ws, 1, columns)
    _write_data_rows(ws, 2, rows, columns)
    _auto_width(ws)

    # Freeze top row
    ws.freeze_panes = "A2"

    # Enable auto-filter for easy sorting/filtering
    if rows:
        last_col = get_column_letter(len(columns))
        ws.auto_filter.ref = f"A1:{last_col}{len(rows) + 1}"

    logger.info("Schedule tab '%s': %d rows, %d columns", tab_name, len(rows), len(columns))


def write_qc_sheet(wb: Workbook, qc_issues: list[dict]):
    """Write the QC / Audit tab."""
    ws = wb.create_sheet(title="QC Audit")

    columns = ["Schedule", "Element ID", "Severity", "Message"]
    _write_header_row(ws, 1, columns)

    for i, issue in enumerate(qc_issues):
        row_num = 2 + i
        fill = ALT_ROW_FILL if i % 2 == 0 else WHITE_FILL
        for col_idx, key in enumerate(["schedule", "element_id", "severity", "message"], start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=issue.get(key, ""))
            cell.font = BODY_FONT
            cell.fill = fill
            cell.border = THIN_BORDER

    _auto_width(ws)
    ws.freeze_panes = "A2"
    logger.info("QC tab: %d issues", len(qc_issues))


def write_template(
    schedules: dict[str, list[dict]],
    schedule_defs: list[dict],
    project_name: str,
    output_dir: Path,
    project_slug: str,
) -> Path:
    """Generate the Step 1 Excel template (working document).

    Uses a stable filename so the user can edit and re-save.
    Returns the path to the written file.
    """
    wb = Workbook()

    # Summary (template mode)
    write_summary_sheet(wb, schedules, schedule_defs, project_name, [], mode="template")

    # One tab per active schedule
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        if rows:
            write_schedule_sheet(wb, sdef, rows)

    # Save with stable filename
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ebif_schedule_{project_slug}.xlsx"
    filepath = output_dir / filename
    wb.save(str(filepath))
    logger.info("Excel template: %s", filepath)
    return filepath


def write_published(
    schedules: dict[str, list[dict]],
    schedule_defs: list[dict],
    qc_issues: list[dict],
    project_name: str,
    output_dir: Path,
    project_slug: str,
) -> Path:
    """Generate the Step 2 published Excel with QC tab.

    Returns the path to the written file.
    """
    wb = Workbook()

    # Summary (publish mode)
    write_summary_sheet(wb, schedules, schedule_defs, project_name, qc_issues, mode="publish")

    # Schedule tabs
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        if rows:
            write_schedule_sheet(wb, sdef, rows)

    # QC tab
    if qc_issues:
        write_qc_sheet(wb, qc_issues)

    # Save with timestamp for versioning
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"ebif_published_{project_slug}_{timestamp}.xlsx"
    filepath = output_dir / filename
    wb.save(str(filepath))
    logger.info("Published Excel: %s", filepath)
    return filepath
