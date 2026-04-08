"""Greedy fill block calculator — per wall block quantities.

No API calls. Pure computation only.
"""

import logging
import math
from dataclasses import dataclass, field

from .block_catalog import BlockCatalog
from .wall_parser import Wall, Opening

logger = logging.getLogger(__name__)


@dataclass
class WallResult:
    wall: Wall
    courses: int = 0
    blocks: dict = field(default_factory=dict)   # {block_id: count}
    total_blocks: int = 0
    weight_lbs: float = 0.0


def calculate_wall(wall: Wall, catalog: BlockCatalog) -> WallResult:
    """Calculate block quantities for a single wall using greedy fill + running bond."""
    result = WallResult(wall=wall)
    mod_h = catalog.module_height

    if wall.height_in < mod_h or wall.length_in <= 0:
        return result

    num_courses = math.floor(wall.height_in / mod_h)
    result.courses = num_courses

    series = wall.series
    half = catalog.half_block(series)
    half_len = half["length_in"]

    # Build opening spans per course
    spans = _opening_spans(wall.openings, num_courses, mod_h)

    blocks: dict[str, int] = {}

    for ci in range(num_courses):
        is_offset = (ci % 2 == 1)
        blocked = spans.get(ci, [])
        segments = _fillable_segments(wall.length_in, blocked)

        for s_start, s_end in segments:
            seg_len = s_end - s_start
            if seg_len <= 0:
                continue
            cb = _fill_segment(seg_len, series, is_offset, catalog)
            for bid, cnt in cb.items():
                blocks[bid] = blocks.get(bid, 0) + cnt

    result.blocks = blocks
    result.total_blocks = sum(blocks.values())

    # Weight
    for bid, cnt in blocks.items():
        b = catalog.get(bid)
        result.weight_lbs += cnt * b["weight_lbs"]
    result.weight_lbs = round(result.weight_lbs, 1)

    return result


def _opening_spans(openings: list[Opening], courses: int, mod_h: float) -> dict[int, list]:
    spans: dict[int, list] = {}
    h_off = 0.0
    for op in openings:
        # Without sill data, assume openings start at floor level
        top = op.height_in
        sc = 0
        ec = math.ceil(top / mod_h)
        for c in range(max(0, sc), min(courses, ec)):
            spans.setdefault(c, []).append((h_off, h_off + op.width_in))
        h_off += op.width_in
    return spans


def _fillable_segments(wall_len: float, blocked: list) -> list:
    if not blocked:
        return [(0.0, wall_len)]
    blocked.sort(key=lambda s: s[0])
    segs = []
    pos = 0.0
    for bs, be in blocked:
        bs = max(0.0, bs)
        be = min(wall_len, be)
        if bs > pos:
            segs.append((pos, bs))
        pos = max(pos, be)
    if pos < wall_len:
        segs.append((pos, wall_len))
    return segs


def _fill_segment(length: float, series: str, is_offset: bool, catalog: BlockCatalog) -> dict:
    blocks: dict[str, int] = {}
    rem = length

    if is_offset and rem > 0:
        half = catalog.half_block(series)
        hl = half["length_in"]
        if rem >= hl:
            blocks[half["id"]] = 1
            rem -= hl

    for b in catalog.blocks_longest_first(series):
        bl = b["length_in"]
        if bl <= 0:
            continue
        cnt = math.floor(rem / bl)
        if cnt > 0:
            blocks[b["id"]] = blocks.get(b["id"], 0) + cnt
            rem -= cnt * bl

    return blocks
