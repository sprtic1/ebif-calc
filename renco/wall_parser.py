"""Parse raw ArchiCAD wall data into typed Wall objects.

Handles unit conversion (metric→inches), composite filtering,
geometry validation, ID assignment, and flag generation.
"""

import logging
import math
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

M2IN = 39.3701
THICKNESS_RESIDENTIAL = 6.0
THICKNESS_COMMERCIAL = 8.0
THICKNESS_TOL = 0.5

# GUIDs for walls requiring special treatment
GUID_ANGLED = "c4dfc8cb-75ce-437f-a7c8-07d76b7b76ce"

_WALL_ID_RE = re.compile(r"^WALL-(\d{3})X?$", re.IGNORECASE)


@dataclass
class Opening:
    type: str       # "door" or "window"
    width_in: float
    height_in: float


@dataclass
class Wall:
    guid: str
    wall_id: str        # WALL-001, WALL-003X etc
    story_name: str
    length_in: float
    height_in: float
    thickness_in: float
    series: str         # "residential" or "commercial"
    composite_name: str
    openings: list[Opening] = field(default_factory=list)
    arc_angle: float = 0.0
    flags: list[str] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""
    floor_index: int = 0
    x_coord: float = 0.0   # for sort ordering
    is_editable: bool = True


def _len_from_coords(beg: dict, end: dict) -> float:
    """Fallback: compute 2D plan length from coordinates (meters → inches)."""
    dx = end.get("x", 0) - beg.get("x", 0)
    dy = end.get("y", 0) - beg.get("y", 0)
    return math.sqrt(dx * dx + dy * dy) * M2IN


def _classify(thickness_in: float) -> str:
    if abs(thickness_in - THICKNESS_RESIDENTIAL) <= THICKNESS_TOL:
        return "residential"
    if abs(thickness_in - THICKNESS_COMMERCIAL) <= THICKNESS_TOL:
        return "commercial"
    return "commercial"


def _ft_in(inches: float) -> str:
    ft = int(inches // 12)
    rem = round(inches % 12)
    if rem >= 12:
        ft += 1; rem = 0
    return f"{ft}'-{rem}\""


def parse_walls(raw_walls: list[dict], composite_filter: str = "renco") -> tuple[list[Wall], list[Wall]]:
    """Parse raw dicts into Wall objects. Returns (renco_walls, excluded_walls).

    renco_walls: walls with composite containing filter string, not curved/irregular.
    excluded_walls: everything else (non-Renco get excluded=True with reason).
    """
    all_walls: list[Wall] = []
    filt = composite_filter.lower()

    for raw in raw_walls:
        guid = raw["guid"]
        beg = raw.get("beg", {})
        end = raw.get("end", {})

        # Prefer ArchiCAD's Reference Line Length property over coordinate calc
        ref_len_m = raw.get("ref_line_length_m") or 0
        if ref_len_m > 0:
            length_in = ref_len_m * M2IN
        else:
            length_in = _len_from_coords(beg, end)
        height_in = (raw.get("height_m") or 0) * M2IN
        thickness_in = (raw.get("thickness_m") or 0) * M2IN

        # If thickness came as zero, try width
        if thickness_in < 0.1:
            thickness_in = (raw.get("width_m") or 0) * M2IN

        series = _classify(thickness_in)
        composite = raw.get("composite_name") or ""
        openings = [
            Opening(type=o["type"],
                    width_in=(o.get("width_m") or 0) * M2IN,
                    height_in=(o.get("height_m") or 0) * M2IN)
            for o in raw.get("openings", [])
        ]

        wall = Wall(
            guid=guid,
            wall_id=raw.get("element_id", ""),
            story_name=raw.get("story_name", ""),
            length_in=length_in,
            height_in=height_in,
            thickness_in=thickness_in,
            series=series,
            composite_name=composite,
            openings=openings,
            arc_angle=raw.get("arc_angle", 0.0) or 0.0,
            floor_index=raw.get("floor_index", 0),
            x_coord=beg.get("x", 0),
            is_editable=raw.get("is_editable", True),
        )
        all_walls.append(wall)

    # Separate Renco from non-Renco
    renco, non_renco = [], []
    for w in all_walls:
        if w.composite_name and filt in w.composite_name.lower():
            renco.append(w)
        else:
            w.excluded = True
            w.exclude_reason = f"No Renco composite (structure: {raw.get('structure_type', 'Basic')})"
            non_renco.append(w)

    # Geometry checks on Renco walls
    final_renco = []
    for w in renco:
        # Curved wall
        if abs(w.arc_angle) > 0.001:
            w.excluded = True
            w.exclude_reason = f"Curved wall (arcAngle {w.arc_angle:.3f} rad / {abs(w.arc_angle) * 57.2958:.1f} deg) — excluded, requires manual calculation"
            non_renco.append(w)
            continue

        # Known angled/irregular wall
        if w.guid.lower() == GUID_ANGLED.lower():
            w.excluded = True
            w.exclude_reason = "Angled/irregular wall — excluded, requires manual calculation"
            non_renco.append(w)
            continue

        final_renco.append(w)

    logger.info("Parsed %d walls: %d Renco, %d excluded", len(all_walls), len(final_renco), len(non_renco))
    return final_renco, non_renco


def assign_ids(walls: list[Wall]) -> None:
    """Assign WALL-NNN IDs. Preserves existing IDs, fills gaps, sorts by story+x_coord."""
    # Sort: lowest floor first, then x coordinate
    walls.sort(key=lambda w: (w.floor_index, w.x_coord))

    existing: list[tuple[int, Wall]] = []
    new: list[Wall] = []
    for w in walls:
        m = _WALL_ID_RE.match(w.wall_id)
        if m:
            existing.append((int(m.group(1)), w))
        else:
            new.append(w)

    existing.sort(key=lambda x: x[0])

    seq = 1
    for _, w in existing:
        w.wall_id = f"WALL-{seq:03d}"
        seq += 1
    for w in new:
        w.wall_id = f"WALL-{seq:03d}"
        seq += 1


def run_checks(walls: list[Wall], catalog) -> None:
    """Run all 13 geometry/modular checks on Renco walls. Populates wall.flags."""
    from collections import Counter
    guid_counts = Counter(w.guid for w in walls)

    for w in walls:
        # Uneditable wall (locked, reserved, or no access in Teamwork)
        if not w.is_editable:
            w.flags.append("Wall is locked/reserved — not editable in Teamwork")

        closure = catalog.closure_len(w.series)
        field_len = catalog.field_block(w.series)["length_in"]
        mod_h = catalog.module_height

        # 1. Wall too short for one field block
        if w.length_in < field_len:
            w.flags.append(f"Wall shorter than one field block ({w.length_in:.1f}in < {field_len}in — need {field_len - w.length_in:.1f}in more)")

        # 2. Wall shorter than one course
        if w.height_in < mod_h:
            w.flags.append(f"Wall shorter than one course ({w.height_in:.1f}in < {mod_h}in)")

        # 3. Non-modular length (based on 8" Renco module, not closure block)
        mod_unit = mod_h  # 8" — Renco's universal module for both series
        rem = w.length_in % mod_unit
        if rem > 0.1 and (mod_unit - rem) > 0.1:
            nearest_shorter = w.length_in - rem
            nearest_longer = nearest_shorter + mod_unit
            w.flags.append(
                f"Non-modular length: {rem:.1f}in remainder "
                f"(wall {w.length_in:.1f}in — nearest modular: {nearest_shorter:.0f}in or {nearest_longer:.0f}in)"
            )

        # 4. Non-modular height
        h_rem = w.height_in % mod_h
        if h_rem > 0.5 and (mod_h - h_rem) > 0.5:
            w.flags.append(f"Non-modular height: {h_rem:.1f}in remainder ({w.height_in:.1f}in / {mod_h}in courses)")

        # 5. Very short wall
        if 0 < w.length_in < 24:
            w.flags.append(f"Very short wall ({w.length_in:.1f}in < 24in) — verify intent")

        # 6. Duplicate GUID
        if guid_counts[w.guid] > 1:
            w.flags.append(f"Duplicate GUID detected ({guid_counts[w.guid]} walls share this GUID)")

        # Opening checks
        if w.openings:
            total_op_area = 0
            h_off = 0.0
            for i, op in enumerate(w.openings):
                total_op_area += op.width_in * op.height_in
                if op.width_in > w.length_in:
                    w.flags.append(
                        f"Opening {i+1} ({op.type}) wider than wall "
                        f"({op.width_in:.0f}in opening > {w.length_in:.0f}in wall)"
                    )
                if op.height_in > w.height_in:
                    w.flags.append(
                        f"Opening {i+1} ({op.type}) taller than wall "
                        f"({op.height_in:.0f}in opening > {w.height_in:.0f}in wall)"
                    )
                right_gap = w.length_in - (h_off + op.width_in)
                if 0 < h_off < closure:
                    w.flags.append(
                        f"Opening {i+1} ({op.type}) too close to left wall end "
                        f"({h_off:.1f}in gap < {closure}in closure block)"
                    )
                if 0 < right_gap < closure:
                    w.flags.append(
                        f"Opening {i+1} ({op.type}) too close to right wall end "
                        f"({right_gap:.1f}in gap < {closure}in closure block)"
                    )
                h_off += op.width_in

            wall_area = w.length_in * w.height_in
            if wall_area > 0 and total_op_area / wall_area > 0.5:
                pct = total_op_area / wall_area * 100
                wall_sqft = wall_area / 144
                op_sqft = total_op_area / 144
                max_op_sqft = wall_sqft * 0.5
                reduce_sqft = op_sqft - max_op_sqft
                w.flags.append(
                    f"Opening area {pct:.0f}% ({op_sqft:.1f} sqft openings / {wall_sqft:.1f} sqft wall) "
                    f"— reduce openings by {reduce_sqft:.1f} sqft to get below 50%"
                )

    # Apply X suffix
    for w in walls:
        if w.flags:
            if not w.wall_id.endswith("X"):
                w.wall_id += "X"


def renco_report_value(wall: Wall) -> str:
    """Build RENCO REPORT string for a wall."""
    if wall.excluded:
        return wall.exclude_reason
    if not wall.flags:
        return "OK"
    return "; ".join(wall.flags)
