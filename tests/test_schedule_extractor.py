"""Tests for schedule_extractor — uses mock data, no live Archicad needed."""

import json
from pathlib import Path

import pytest

MOCK_DIR = Path(__file__).parent / "mock_data"


def load_mock():
    with open(MOCK_DIR / "sample_elements.json") as f:
        return json.load(f)


def test_mock_data_loads():
    data = load_mock()
    assert "schedules" in data
    assert "project_name" in data


def test_mock_has_expected_schedules():
    data = load_mock()
    schedules = data["schedules"]
    assert "appliances" in schedules
    assert "furniture" in schedules
    assert "lighting" in schedules


def test_appliance_count():
    data = load_mock()
    assert len(data["schedules"]["appliances"]) == 2


def test_furniture_has_required_fields():
    data = load_mock()
    for item in data["schedules"]["furniture"]:
        assert "Element ID" in item
        assert "Vendor" in item
        assert "Zone" in item


def test_is_yes_helper():
    from ebif.schedule_extractor import _is_yes
    assert _is_yes("Yes")
    assert _is_yes("yes")
    assert _is_yes("TRUE")
    assert _is_yes("1")
    assert not _is_yes("No")
    assert not _is_yes("")
    assert not _is_yes(None)
    assert not _is_yes("False")
