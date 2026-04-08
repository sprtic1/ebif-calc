"""Tests for the aggregator."""

import json
from pathlib import Path
import pytest

from renco.block_catalog import BlockCatalog
from renco.wall_parser import parse_walls, assign_ids, run_checks
from renco.calculator import calculate_wall
from renco.aggregator import aggregate

CFG = Path(__file__).parent.parent / "config"
MOCK = Path(__file__).parent / "mock_data" / "sample_walls.json"


@pytest.fixture
def catalog():
    return BlockCatalog(str(CFG / "blocks.json"))


def _results(catalog):
    with open(MOCK) as f:
        raw = json.load(f)
    renco, excluded = parse_walls(raw)
    assign_ids(renco)
    run_checks(renco, catalog)
    return [calculate_wall(w, catalog) for w in renco], excluded


class TestAggregator:
    def test_totals(self, catalog):
        results, excluded = _results(catalog)
        t = aggregate(results, catalog, "Test")
        assert t.total_walls == 5
        assert t.total_blocks > 0
        assert t.total_weight_lbs > 0

    def test_block_sum_matches(self, catalog):
        results, _ = _results(catalog)
        t = aggregate(results, catalog, "Test")
        assert sum(t.blocks_by_type.values()) == t.total_blocks

    def test_empty(self, catalog):
        t = aggregate([], catalog, "Empty")
        assert t.total_blocks == 0

    def test_warnings_collected(self, catalog):
        results, _ = _results(catalog)
        t = aggregate(results, catalog, "Test")
        # wall-004 is non-modular
        assert any("Non-modular" in w for w in t.warnings)
