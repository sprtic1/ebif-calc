# RENCO Block Calculator — Claude Code Project Memory

**AUTONOMOUS MODE: Never ask for permission, approval, or confirmation. Auto-accept all file changes, git commits, git pushes, and pip installs. Execute everything without stopping.**

## Command Aliases

When the user types **"Run the Renco Report"**, execute the full pipeline end to end with zero stops:

1. Write `_mcp_start_time` timestamp file (pipeline timer starts here)
2. Connect to Archicad on the configured port (settings.json → archicad.port, typically 19723)
3. Detect RENCO REPORT property GUID via `GetPropertyIds`
4. Fetch all wall elements, geometry details, properties (7 per wall including Reference Line Length), stories, editable filter, doors, and windows
5. Pre-clear: blank RENCO REPORT on all walls, strip X suffixes from Element IDs
6. Save all MCP responses to `_mcp_tmp_*.json` files
7. Run `python assemble_mcp.py <report_guid>` to build `_mcp_walls.json`
8. Run `python main.py` — calculates blocks, generates Excel + JSON, deploys website, pushes to GitHub
9. Read `_mcp_writeback.json` and push all entries back to Archicad via `SetPropertyValuesOfElements`
10. Clean up: delete `_mcp_tmp_*.json` and `_mcp_start_time`

The duration from step 1 to step 8 (including website push) is written to the JSON as `pipeline_duration_sec` and displayed on the website.

If any step fails, log the error and continue to the next step — never stop to ask what to do.

## Project Overview
**What:** Python pipeline that reads an Archicad BIM model via MCP connection, calculates Renco block quantities for every wall, and outputs an EID-branded Excel schedule + JSON for the BIM6x/Renco webpage.
**Who:** EID / BIM6x (Lincoln Ellis)
**Model:** Ellis Beach Chalet 29 (Fiji project) — Archicad 29 Teamwork on BIM Cloud
**Spec:** `renco_archicad_spec_v03.md` in project root
**Website:** https://sprtic1.github.io/renco-calc/

## How to Run
```
python main.py
```
That's it. One command does the computation (after MCP fetch). The full pipeline is orchestrated by Claude Code using the "Run the Renco Report" command above.

## Folder Structure
```
renco-calc/                          # THIS PROJECT (EID Dropbox)
  main.py                            # Single entry point — runs full pipeline
  assemble_mcp.py                    # Assembles MCP responses into _mcp_walls.json
  CLAUDE.md                          # This file — project memory for Claude Code
  renco_archicad_spec_v03.md         # Full build specification
  requirements.txt                   # requests, openpyxl, pytest
  config/
    settings.json                    # ALL configuration — paths, ports, thresholds
    blocks.json                      # Block catalog — both series, weights
    containers.json                  # 4 ISO container types + GMA pallet specs
  renco/
    __init__.py
    mcp_bridge.py                    # Assembles MCP responses into pipeline format
    wall_parser.py                   # Raw API → Wall objects, filtering, ID assignment, checks
    block_catalog.py                 # JSON-driven catalog loader
    calculator.py                    # Greedy fill + running bond — pure computation
    aggregator.py                    # Wall results → project totals
    packing.py                       # Container packing — greedy fill-first algorithm
    output/
      excel_writer.py                # 5-sheet EID-branded Excel
      json_writer.py                 # Clean JSON for webpage
  tests/
    mock_data/sample_walls.json      # Mock walls for offline testing
    test_wall_parser.py
    test_calculator.py
    test_aggregator.py
    test_packing.py

RENCO-WEBSITE/renco-calc/            # GITHUB PAGES REPO (EID Dropbox)
  index.html                         # Home page — lists all projects as cards
  style.css                          # Shared styles (Playfair Display, DM Sans, DM Mono)
  projects.json                      # Registry of all projects
  ellis-beach-chalet-29/             # Project subpage
    index.html                       # Full block schedule page
    app.js                           # Chart.js donut, tables, shipping diagrams
    data/renco_data.json             # Pipeline output consumed by the page
    assets/model.png                 # Latest project render image
```

## Config: settings.json
All paths, ports, and thresholds live in `config/settings.json`. No hardcoded paths in Python code.
- `archicad.port` — Archicad API port (typically 19723, changes between sessions)
- `paths.website_repo` — full path to the GitHub Pages repo folder (in EID Dropbox)
- `paths.project_renders` — folder containing RENDER*.png files
- `paths.excel_output` — where to save Excel files (blank = project root)
- `project.name` — Archicad project name (used for webpage slug)

## Archicad API Pattern
- Port: from settings.json (typically 19723)
- All communication via MCP tools or direct HTTP to localhost
- Built-in commands: `GetElementsByType`, `GetPropertyValuesOfElements`, `SetPropertyValuesOfElements`
- Tapir commands: `GetDetailsOfElements`, `GetStories`, `FilterElements`
- Property values returned as display strings (feet-inches) — parsed by mcp_bridge.py
- Door/Window elements have `ownerElementId` in details pointing to parent wall GUID

## Critical Property GUIDs
- **Element ID:** `7e221f33-829b-4fbc-a670-e74dabce6289`
- **RENCO REPORT:** Auto-detected every run via `GetPropertyIds` (searches "EID GENERAL PROPERTIES" / "RENCO REPORT")
- **Composite Name:** `704e9212-3e21-4790-bae4-cf3de2395481`
- **Structure Type:** `98a26d3b-3baf-4019-be7a-09285ffa597c`
- **Width/Height/Thickness:** `3799b10a...` / `c4b62357...` / `a7b55e43...`
- **Reference Line Length:** `736276cc-0825-4738-a2e8-cdd740c7f635`

## Wall Length
Wall lengths use the **Reference Line Length** property from Archicad (not 3D length, not coordinate-based calculation). Falls back to coordinate calc only if the property is missing.

## Container Packing Rules
1. Start with the largest container. Fill to 100% — whichever hits first: max weight or max pallet count.
2. Bottom layer fills every floor position before any pallet goes on upper layer.
3. If weight maxes out before pallet count, stop — no second layer.
4. Remaining pallets → smallest container type that fits by both weight and pallet count.
5. Overflow container: split pallets evenly between layers, fill column-first (left columns get both rows before moving right), pushed to one end.
6. Container grid sizes: 40ft = 11 cols × 2 rows per layer, 20ft = 5 cols × 2 rows per layer.
7. Consumables (adhesive cartridges, rubber mallets at 1 per 20 guns) shipped loose, not palletized.

## Block Catalog
- **Commercial (8in):** COM-32, COM-16 (8.5 lbs CONFIRMED), COM-8, COM-4
- **Residential (6in):** RES-30, RES-12, RES-6, RES-3
- Modular unit: 8 inches (Renco universal module for both series)

## Testing
- 26 tests in tests/ — all use mock data, no live Archicad needed
- `python -m pytest tests/ -q` to run

## User Preferences
- Run autonomously — never prompt for permission
- Auto-accept all file edits, bash commands, API calls
- Always re-fetch fresh from Archicad (no caching)
- US English spelling throughout (utilization, not utilisation)
