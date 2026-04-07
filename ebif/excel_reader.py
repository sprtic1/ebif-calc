"""Excel Reader — reads completed EID schedule files back into pipeline data.

Used in Step 2 (Publish) to read the individual schedule Excel files after
manual data entry and convert them back into structured schedule data.

Reads individual files: Appliances.xlsx, Furniture.xlsx, etc.
"""

import logging
from pathlib import Path

from openpyxl import load_workbook

logger = logging.getLogger(__name__)


def read_schedule_file(
    filepath: Path,
    schedule_def: dict,
) -> list[dict]:
    """Read a single schedule Excel file and return row data.

    Expects the data table to start at row 5 (header) with data from row 6,
    matching the write_schedule_file format. Falls back to row 1 header if
    row 5 doesn't look like a header.
    """
    wb = load_workbook(str(filepath), data_only=True)
    ws = wb.active

    # Try row 5 first (standard template format), fall back to row 1
    rows_data = list(ws.iter_rows(min_row=1, values_only=False))
    if not rows_data:
        return []

    header_row_idx = _find_header_row(rows_data)
    if header_row_idx is None:
        logger.warning("No header row found in %s", filepath.name)
        return []

    headers = []
    for cell in rows_data[header_row_idx]:
        val = cell.value
        headers.append(str(val).strip() if val is not None else "")

    if not any(headers):
        return []

    # Read data rows after header
    result = []
    for row in rows_data[header_row_idx + 1:]:
        entry = {}
        all_empty = True
        for col_idx, cell in enumerate(row):
            if col_idx < len(headers) and headers[col_idx]:
                val = cell.value
                if val is not None:
                    val = str(val).strip() if not isinstance(val, (int, float)) else val
                    all_empty = False
                else:
                    val = ""
                entry[headers[col_idx]] = val

        if not all_empty:
            entry.setdefault("_guid", "")
            entry.setdefault("_type", "")
            entry.setdefault("Qty", 1)
            result.append(entry)

    return result


def _find_header_row(rows_data: list) -> int | None:
    """Find the header row index (0-based) by looking for 'Element ID'."""
    for i, row in enumerate(rows_data[:10]):  # check first 10 rows
        for cell in row:
            if cell.value and str(cell.value).strip() == "Element ID":
                return i
    return None


def read_all_schedules(
    output_dir: Path,
    schedule_defs: list[dict],
) -> dict[str, list[dict]]:
    """Read all individual schedule Excel files from the output directory.

    Looks for {ScheduleName}.xlsx for each schedule definition.
    Returns dict mapping schedule_id -> list of row dicts.
    """
    schedules: dict[str, list[dict]] = {}
    files_read = 0

    for sdef in schedule_defs:
        sname = sdef["name"]
        filepath = output_dir / f"{sname}.xlsx"

        if filepath.exists():
            rows = read_schedule_file(filepath, sdef)
            schedules[sdef["id"]] = rows
            if rows:
                files_read += 1
                logger.info("Read '%s': %d rows", filepath.name, len(rows))
        else:
            schedules[sdef["id"]] = []

    total = sum(len(v) for v in schedules.values())
    active = sum(1 for v in schedules.values() if v)
    logger.info("Read %d files: %d elements across %d active schedules", files_read, total, active)
    return schedules


def has_schedule_files(output_dir: Path, schedule_defs: list[dict]) -> bool:
    """Check if any schedule Excel files exist in the output directory."""
    for sdef in schedule_defs:
        filepath = output_dir / f"{sdef['name']}.xlsx"
        if filepath.exists():
            return True
    return False
