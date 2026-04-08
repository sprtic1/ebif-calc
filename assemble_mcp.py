"""Assemble MCP API responses into _mcp_walls.json for the pipeline."""
import json, sys
from pathlib import Path

BASE = Path(__file__).parent

def load(name):
    p = BASE / name
    return json.load(open(p)) if p.exists() else {}

def main():
    report_guid = sys.argv[1] if len(sys.argv) > 1 else ""
    from renco.mcp_bridge import assemble_walls
    elements = load("_mcp_tmp_elements.json")
    details = load("_mcp_tmp_details.json")
    properties = load("_mcp_tmp_properties.json")
    stories = load("_mcp_tmp_stories.json")
    editable_data = load("_mcp_tmp_editable.json")
    editable_guids = {e["elementId"]["guid"] for e in editable_data.get("elements", [])} if editable_data else None
    opening_data = {
        "doors": {"elements": load("_mcp_tmp_doors_elements.json"), "details": load("_mcp_tmp_doors_details.json"), "properties": load("_mcp_tmp_doors_properties.json")},
        "windows": {"elements": load("_mcp_tmp_windows_elements.json"), "details": load("_mcp_tmp_windows_details.json"), "properties": load("_mcp_tmp_windows_properties.json")},
    }
    walls = assemble_walls(elements, details, properties, stories, opening_data, editable_guids=editable_guids)
    with open(BASE / "_mcp_walls.json", "w") as f:
        json.dump({"walls": walls, "report_guid": report_guid}, f, indent=2)
    print(f"Assembled {len(walls)} walls into _mcp_walls.json")

if __name__ == "__main__":
    main()
