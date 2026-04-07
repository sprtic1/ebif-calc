"""Tests for qc_checker — validates quality control logic in both modes."""

import json
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


def test_detects_missing_tear_sheet():
    from ebif.qc_checker import check_schedule

    rows = [
        {"Element ID": "OBJ-011", "_guid": "fff-222", "TEAR SHEET #": "", "Vendor": "West Elm"},
    ]
    issues = check_schedule("furniture", "Furniture", rows, ["TEAR SHEET #", "Vendor"], mode="publish")
    warnings = [i for i in issues if i["severity"] == "Warning"]
    assert len(warnings) >= 1
    assert any("TEAR SHEET #" in w["message"] for w in warnings)


def test_no_issues_for_complete_data():
    from ebif.qc_checker import check_schedule

    rows = [
        {"Element ID": "OBJ-001", "_guid": "aaa-111", "TEAR SHEET #": "TS-A01",
         "MANUFACTURER": "Viking", "MODEL #": "VR36"},
    ]
    issues = check_schedule("appliances", "Appliances", rows, ["TEAR SHEET #", "MANUFACTURER", "MODEL #"], mode="publish")
    warnings = [i for i in issues if i["severity"] == "Warning"]
    assert len(warnings) == 0


def test_extract_mode_is_light():
    from ebif.qc_checker import check_schedule

    rows = [
        {"Element ID": "OBJ-001", "_guid": "aaa-111", "TEAR SHEET #": "TS-A01",
         "MANUFACTURER": "", "MODEL #": ""},  # blank specs but has tear sheet
    ]
    # Extract mode should NOT flag missing MANUFACTURER/MODEL
    issues = check_schedule("appliances", "Appliances", rows, ["TEAR SHEET #", "MANUFACTURER", "MODEL #"], mode="extract")
    assert len(issues) == 0  # tear sheet present, extract mode doesn't check specs


def test_publish_mode_flags_missing_specs():
    from ebif.qc_checker import check_schedule

    rows = [
        {"Element ID": "OBJ-001", "_guid": "aaa-111", "TEAR SHEET #": "TS-A01",
         "MANUFACTURER": "", "MODEL #": ""},
    ]
    issues = check_schedule("appliances", "Appliances", rows, ["TEAR SHEET #", "MANUFACTURER", "MODEL #"], mode="publish")
    # Should flag MANUFACTURER and MODEL # as warnings (important fields)
    warnings = [i for i in issues if i["severity"] == "Warning"]
    assert any("MANUFACTURER" in w["message"] for w in warnings)
    assert any("MODEL #" in w["message"] for w in warnings)


def test_check_all_schedules():
    from ebif.qc_checker import check_all_schedules

    data = load_mock()
    defs = load_schedule_defs()
    issues = check_all_schedules(data["schedules"], defs, mode="publish")
    warnings = [i for i in issues if i["severity"] == "Warning"]
    assert len(warnings) >= 1


def test_completion_metrics():
    from ebif.qc_checker import completion_metrics

    data = load_mock()
    defs = load_schedule_defs()
    m = completion_metrics(data["schedules"], defs)
    assert m["total_rows"] > 0
    assert m["pct_complete"] >= 0
    assert m["complete_rows"] + m["incomplete_rows"] == m["total_rows"]
