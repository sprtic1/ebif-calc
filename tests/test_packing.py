"""Tests for packing logic."""

import json
from pathlib import Path
import pytest

from renco.block_catalog import BlockCatalog
from renco.wall_parser import parse_walls, assign_ids, run_checks
from renco.calculator import calculate_wall
from renco.aggregator import aggregate, ProjectTotals
from renco.packing import calculate_packing

CFG = Path(__file__).parent.parent / "config"
MOCK = Path(__file__).parent / "mock_data" / "sample_walls.json"


@pytest.fixture
def catalog():
    return BlockCatalog(str(CFG / "blocks.json"))


def _totals(catalog):
    with open(MOCK) as f:
        raw = json.load(f)
    renco, _ = parse_walls(raw)
    assign_ids(renco)
    results = [calculate_wall(w, catalog) for w in renco]
    return aggregate(results, catalog, "Test")


class TestPacking:
    def test_basic(self, catalog):
        t = _totals(catalog)
        p = calculate_packing(t, catalog, str(CFG / "containers.json"))
        assert p.total_pallets > 0
        assert p.containers_required >= 1

    def test_empty(self, catalog):
        t = ProjectTotals()
        p = calculate_packing(t, catalog, str(CFG / "containers.json"))
        assert p.total_pallets == 0
        assert p.containers_required == 0

    def test_pallet_positions(self, catalog):
        t = _totals(catalog)
        p = calculate_packing(t, catalog, str(CFG / "containers.json"))
        for pal in p.pallets:
            assert pal.container >= 1
            assert pal.layer >= 1

    def test_weight_calculated(self, catalog):
        t = _totals(catalog)
        p = calculate_packing(t, catalog, str(CFG / "containers.json"))
        assert p.total_weight_lbs > 0

    def test_heavy_scenario(self, catalog):
        """Many blocks should need multiple containers."""
        t = ProjectTotals(blocks_by_type={"COM-16": 5000})
        t.total_blocks = 5000
        p = calculate_packing(t, catalog, str(CFG / "containers.json"))
        assert p.containers_required >= 2
