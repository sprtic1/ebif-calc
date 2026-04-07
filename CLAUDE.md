# EBIF-CALC — Claude Code Project Memory

**AUTONOMOUS MODE: Never ask for permission, approval, or confirmation. Auto-accept all file changes, git commits, git pushes, and pip installs. Execute everything without stopping.**

## Command Aliases

### "Run the EID Report" (Step 1 — Extract from Archicad)
Connects to Archicad, extracts all elements with schedule toggles, and generates an EID-branded Excel **template** pre-populated with element IDs, zones, room names, and any existing Archicad properties. Spec columns (vendor, model, finish, fabric, tear sheet #, cost, etc.) are included and filled with whatever Archicad already has — blanks are left for manual entry. This Excel is the **working document**.

Pipeline:
1. Connect to Archicad on the configured port (settings.json -> archicad_port)
2. For each of the 19 schedule categories, fetch elements where toggle = Yes
3. For each included element, fetch all properties (Element ID, zone/room, spec data)
4. Generate EID-branded Excel template at `output/ebif_schedule_{project_slug}.xlsx`
5. Print summary of elements extracted and blank fields remaining

### "Publish the EID Dashboard" (Step 2 — Publish from Excel)
Reads the completed Excel working document (after manual data entry), generates the website dashboard JSON, and pushes to GitHub Pages. Also generates a QC report flagging any rows with missing spec data.

Pipeline:
1. Read the Excel file at `output/ebif_schedule_{project_slug}.xlsx`
2. Parse all schedule tabs back into structured data
3. Run QC checks — flag rows missing TEAR SHEET #, vendor, model, or other required fields
4. Generate JSON for website dashboard
5. Deploy to GitHub Pages (commit + push)
6. Generate a fresh Excel with QC tab appended
7. Print summary with completion metrics and QC flags

If any step fails, log the error and continue to the next step — never stop to ask what to do.

## Project Overview
**What:** Python pipeline that reads an Archicad BIM model via API, extracts FF&E data across 19 schedule categories, and outputs EID-branded Excel schedules + a live project dashboard website.
**Who:** EID / BIM6x (Lincoln Ellis)
**Model:** McCollum - 408 Cayuse Court 29 (test project)
**Spec:** `EBIF-CALC_Architecture.docx` in project root
**Website:** https://sprtic1.github.io/ebif-calc/

## Two-Step Workflow
1. **Run the EID Report** → Archicad → Excel template (working document)
2. *Designer fills in specs manually in Excel*
3. **Publish the EID Dashboard** → Excel → Website + QC report

## How to Run
```
python main.py extract        # Step 1: Archicad → Excel template
python main.py publish         # Step 2: Excel → Website + QC
python main.py extract --offline  # Use cached data (testing)
```

## Folder Structure
```
ebif-calc/
  main.py                             # Entry point — extract or publish
  setup.py                            # First-run setup
  CLAUDE.md                           # This file
  EBIF-CALC_Architecture.docx         # Architecture spec
  requirements.txt                    # requests, openpyxl, pytest
  config/
    settings.json                     # Paths, ports, project info
    schedules.json                    # 19 schedule definitions with GUIDs
  ebif/
    __init__.py
    api_bridge.py                     # Archicad API via HTTP/JSON
    schedule_extractor.py             # Element extraction + toggle filtering
    excel_reader.py                   # Reads completed Excel back into pipeline
    qc_checker.py                     # Missing data, incomplete specs
    output/
      __init__.py
      excel_writer.py                 # EID-branded Excel (template + final)
      json_writer.py                  # JSON for website dashboard
      website.py                      # Git commit + push to GitHub Pages
  tests/
    mock_data/sample_elements.json
    test_schedule_extractor.py
    test_excel_writer.py
    test_qc_checker.py
  output/                             # Generated Excel + JSON files
```

## Config: settings.json
- `archicad_port` — Tapir API port
- `website_repo` — path to GitHub Pages repo
- `output_folder` — where Excel files are saved (blank = output/)
- `project_name` — current Archicad project name

## The 19 EID Schedules
Each has a toggle property in Archicad and a GUID in schedules.json.
Appliances, Bath Accessories, Cabinetry Hardware, Cabinetry Inserts,
Cabinetry Style & Species, Countertops, Covering Calculations,
Decorative Lighting, Door Hardware, Doors, Flooring, Furniture,
Lighting & Electrical, Plumbing, Shower Glass & Mirrors,
Specialty Equipment, Surface Finishes, Tile, Windows

## EID Branding
- **Header color:** Olive #868C54
- **Alternating rows:** Sage #C2C8A2
- **Accent:** Warm Gray #737569
- **Heading font:** Lato
- **Body font:** Arial Narrow

## Archicad API Pattern
- Port: from settings.json
- HTTP/JSON to localhost (native API with `API.` prefix)
- Property GUIDs pre-configured in schedules.json — no slow name resolution
- NO write-back to Archicad — read-only pipeline

## Testing
- `python -m pytest tests/ -q`

## User Preferences
- Run autonomously — never prompt for permission
- Auto-accept all file edits, bash commands, API calls
- Always re-fetch fresh from Archicad (no caching)
- US English spelling throughout
