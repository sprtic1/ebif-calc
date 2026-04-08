"""Aggregate wall-level results into project totals."""

import logging
from dataclasses import dataclass, field

from .block_catalog import BlockCatalog
from .calculator import WallResult

logger = logging.getLogger(__name__)


@dataclass
class ProjectTotals:
    project_name: str = ""
    total_walls: int = 0
    walls_with_flags: int = 0
    excluded_count: int = 0
    blocks_by_type: dict = field(default_factory=dict)
    total_blocks: int = 0
    total_weight_lbs: float = 0.0
    weight_all_confirmed: bool = False
    warnings: list[str] = field(default_factory=list)


def aggregate(results: list[WallResult], catalog: BlockCatalog, project_name: str, excluded_count: int = 0) -> ProjectTotals:
    t = ProjectTotals(project_name=project_name)
    t.total_walls = len(results)
    t.excluded_count = excluded_count

    for wr in results:
        if wr.wall.flags:
            t.walls_with_flags += 1
            for f in wr.wall.flags:
                t.warnings.append(f"Wall {wr.wall.wall_id}: {f}")

        for bid, cnt in wr.blocks.items():
            t.blocks_by_type[bid] = t.blocks_by_type.get(bid, 0) + cnt

    t.total_blocks = sum(t.blocks_by_type.values())

    for bid, cnt in t.blocks_by_type.items():
        b = catalog.get(bid)
        t.total_weight_lbs += cnt * b["weight_lbs"]
    t.total_weight_lbs = round(t.total_weight_lbs, 1)

    t.weight_all_confirmed = all(catalog.get(bid).get("confirmed_weight", False) for bid in t.blocks_by_type)

    logger.info("Totals: %d walls, %d blocks, %.0f lbs, %d warnings",
                t.total_walls, t.total_blocks, t.total_weight_lbs, len(t.warnings))
    return t
