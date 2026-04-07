"""Tests for excel_writer — generates individual files from mock data."""

import json
import tempfile
from pathlib import Path

import pytest

MOCK_DIR = Path(__file__).parent / "mock_data"


def load_mock():
    with open(MOCK_DIR / "sample_elements.json") as f:
        return json.load(f)


def load_schedule_defs():
    config_dir = Path(__file__).parent.parent / "config"
    with open(config_dir / "schedules.json") as f:
        return json.load(f)["schedules"]


def test_write_template_creates_individual_files():
    from ebif.output.excel_writer import write_template

    data = load_mock()
    defs = load_schedule_defs()

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = write_template(
            schedules=data["schedules"],
            schedule_defs=defs,
            project_name="Test Project",
            output_dir=Path(tmpdir),
        )
        # Should have Summary + individual schedule files
        assert len(paths) >= 2
        names = [p.name for p in paths]
        assert "Summary.xlsx" in names
        # Should have at least one schedule file
        assert any(n.endswith(".xlsx") and n != "Summary.xlsx" for n in names)


def test_write_template_creates_appliances_file():
    from ebif.output.excel_writer import write_template

    data = load_mock()
    defs = load_schedule_defs()

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = write_template(
            schedules=data["schedules"],
            schedule_defs=defs,
            project_name="Test Project",
            output_dir=Path(tmpdir),
        )
        names = [p.name for p in paths]
        assert "Appliances.xlsx" in names


def test_write_published_creates_qc_file():
    from ebif.output.excel_writer import write_published

    data = load_mock()
    defs = load_schedule_defs()

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = write_published(
            schedules=data["schedules"],
            schedule_defs=defs,
            qc_issues=[{"schedule": "Furniture", "element_id": "OBJ-011",
                         "guid": "fff-222", "severity": "Warning",
                         "message": "Missing TEAR SHEET #"}],
            project_name="Test Project",
            output_dir=Path(tmpdir),
        )
        names = [p.name for p in paths]
        assert "QC Audit.xlsx" in names


def test_roundtrip_individual_files():
    """Write per-schedule files, read them back, verify data integrity."""
    from ebif.output.excel_writer import write_template
    from ebif.excel_reader import read_all_schedules

    data = load_mock()
    defs = load_schedule_defs()

    with tempfile.TemporaryDirectory() as tmpdir:
        write_template(
            schedules=data["schedules"],
            schedule_defs=defs,
            project_name="Test Project",
            output_dir=Path(tmpdir),
        )
        # Read back
        result = read_all_schedules(Path(tmpdir), defs)
        # Furniture should roundtrip
        assert "furniture" in result
        assert len(result["furniture"]) == len(data["schedules"]["furniture"])
