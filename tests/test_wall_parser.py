"""Tests for wall_parser — parsing, filtering, ID assignment, checks."""

import json
from pathlib import Path
import pytest

from renco.wall_parser import parse_walls, assign_ids, run_checks

MOCK = Path(__file__).parent / "mock_data" / "sample_walls.json"


def _load():
    with open(MOCK) as f:
        return json.load(f)


class TestParseWalls:
    def test_renco_filter(self):
        renco, excluded = parse_walls(_load())
        # 5 Renco (wall-001..004, wall-007), 2 excluded (curved, basic)
        assert len(renco) == 5
        assert len(excluded) == 2

    def test_curved_excluded(self):
        _, excluded = parse_walls(_load())
        curved = [w for w in excluded if w.excluded and "curved" in w.exclude_reason.lower()]
        assert len(curved) >= 1

    def test_non_renco_excluded(self):
        _, excluded = parse_walls(_load())
        non_renco = [w for w in excluded if w.excluded and not w.composite_name]
        assert len(non_renco) >= 1

    def test_length_from_coords(self):
        renco, _ = parse_walls(_load())
        w1 = next(w for w in renco if w.guid == "wall-001")
        assert abs(w1.length_in - 120.0) < 1  # 3.048m ≈ 120in

    def test_height_conversion(self):
        renco, _ = parse_walls(_load())
        w1 = next(w for w in renco if w.guid == "wall-001")
        assert abs(w1.height_in - 96.0) < 1  # 2.4384m ≈ 96in

    def test_thickness_series(self):
        renco, _ = parse_walls(_load())
        w1 = next(w for w in renco if w.guid == "wall-001")
        assert w1.series == "commercial"
        w2 = next(w for w in renco if w.guid == "wall-002")
        assert w2.series == "residential"

    def test_openings_parsed(self):
        renco, _ = parse_walls(_load())
        w3 = next(w for w in renco if w.guid == "wall-003")
        assert len(w3.openings) == 1
        assert w3.openings[0].type == "door"
        assert abs(w3.openings[0].width_in - 36.0) < 1


class TestAssignIds:
    def test_sequential(self):
        renco, _ = parse_walls(_load())
        assign_ids(renco)
        ids = [w.wall_id for w in renco]
        assert ids[0] == "WALL-001"
        assert ids[-1] == f"WALL-{len(renco):03d}"

    def test_preserves_existing(self):
        renco, _ = parse_walls(_load())
        renco[0].wall_id = "WALL-005"
        assign_ids(renco)
        # WALL-005 should be first (preserved), others fill 1..
        assert renco[0].wall_id.startswith("WALL-00")


class TestRunChecks:
    def test_non_modular_flagged(self):
        renco, _ = parse_walls(_load())
        assign_ids(renco)
        from renco.block_catalog import BlockCatalog
        cat = BlockCatalog(str(Path(__file__).parent.parent / "config" / "blocks.json"))
        run_checks(renco, cat)
        w4 = next(w for w in renco if w.guid == "wall-004")
        assert any("Non-modular" in f for f in w4.flags)
        assert w4.wall_id.endswith("X")

    def test_clean_wall_no_flags(self):
        renco, _ = parse_walls(_load())
        assign_ids(renco)
        from renco.block_catalog import BlockCatalog
        cat = BlockCatalog(str(Path(__file__).parent.parent / "config" / "blocks.json"))
        run_checks(renco, cat)
        w1 = next(w for w in renco if w.guid == "wall-001")
        assert w1.flags == []
        assert not w1.wall_id.endswith("X")
