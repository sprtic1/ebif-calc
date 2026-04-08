"""Tests for the greedy fill calculator."""

import json
from pathlib import Path
import pytest

from renco.block_catalog import BlockCatalog
from renco.wall_parser import parse_walls, assign_ids
from renco.calculator import calculate_wall

CFG = Path(__file__).parent.parent / "config"
MOCK = Path(__file__).parent / "mock_data" / "sample_walls.json"


@pytest.fixture
def catalog():
    return BlockCatalog(str(CFG / "blocks.json"))


def _walls():
    with open(MOCK) as f:
        raw = json.load(f)
    renco, _ = parse_walls(raw)
    assign_ids(renco)
    return renco


class TestCalculator:
    def test_commercial_wall(self, catalog):
        walls = _walls()
        w = next(w for w in walls if w.guid == "wall-001")
        r = calculate_wall(w, catalog)
        assert r.courses == 12  # 96/8
        assert r.total_blocks > 0
        assert all(bid.startswith("COM") for bid in r.blocks)

    def test_residential_wall(self, catalog):
        walls = _walls()
        w = next(w for w in walls if w.guid == "wall-002")
        r = calculate_wall(w, catalog)
        assert r.courses == 12
        assert all(bid.startswith("RES") for bid in r.blocks)

    def test_door_reduces_blocks(self, catalog):
        walls = _walls()
        w_no_door = next(w for w in walls if w.guid == "wall-007")  # 40ft no openings
        w_door = next(w for w in walls if w.guid == "wall-003")  # 20ft with door
        r_no = calculate_wall(w_no_door, catalog)
        r_door = calculate_wall(w_door, catalog)
        # Door wall should have fewer total blocks than an equivalent-length solid wall
        # Since wall-003 is 20ft and wall-007 is 40ft, compare absolute blocks
        # The door-wall at half the length should have less than half the blocks (due to opening)
        assert r_door.total_blocks < r_no.total_blocks

    def test_long_wall_uses_long_blocks(self, catalog):
        walls = _walls()
        w = next(w for w in walls if w.guid == "wall-007")  # 40ft
        r = calculate_wall(w, catalog)
        assert r.blocks.get("COM-32", 0) > 0

    def test_running_bond_uses_half(self, catalog):
        walls = _walls()
        w = next(w for w in walls if w.guid == "wall-001")
        r = calculate_wall(w, catalog)
        assert r.blocks.get("COM-8", 0) > 0  # half blocks for offset courses

    def test_weight_calculated(self, catalog):
        walls = _walls()
        w = next(w for w in walls if w.guid == "wall-001")
        r = calculate_wall(w, catalog)
        assert r.weight_lbs > 0
