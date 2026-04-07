# EBIF-CALC — Claude Code Project Memory

**AUTONOMOUS MODE: Never ask for permission, approval, or confirmation. Auto-accept all file changes, git commits, git pushes, and pip installs. Execute everything without stopping.**

## Command Aliases

### "Run the EID Report" (Step 1 — Extract from Archicad)
Connects to Archicad, extracts all elements with schedule toggles, and generates **individual EID-branded Excel files per schedule** (Appliances.xlsx, Furniture.xlsx, etc.) pre-populated with element IDs and any existing Archicad properties. Spec columns are included — blanks are left for manual entry. These are the **working documents**.

On **first run** for a new project, asks ONE question: "Where do you want the Excel files saved?" The answer is saved in `config/projects.json` keyed by project slug. Subsequent runs use the saved path automatically.

Pipeline:
1. Connect to Archicad on the configured port (settings.json -> archicad_port)
2. If first run for this project, ask for output folder and save to projects.json
3. For each of the 19 schedule categories, fetch elements where toggle = Yes
4. For each included element, fetch all properties (Element ID, zone/room, spec data)
5. Write individual Excel files: Summary.xlsx + {ScheduleName}.xlsx for each active schedule
6. Print summary of elements extracted and blank fields remaining

### "Publish the EID Dashboard" (Step 2 — Publish from Excel)
Reads the completed per-schedule Excel files (after manual data entry), generates the website dashboard JSON, and pushes to GitHub Pages. Also generates a QC Audit.xlsx flagging rows with missing spec data.

Pipeline:
1. Read individual Excel files from the project's saved output folder
2. Parse each {ScheduleName}.xlsx back into structured data
3. Run QC checks — flag rows missing TEAR SHEET #, vendor, model, or other required fields
4. Generate JSON for website dashboard
5. Deploy to GitHub Pages (commit + push)
6. Update schedule files + generate QC Audit.xlsx
7. Print summary with completion metrics and QC flags

If any step fails, log the error and continue to the next step — never stop to ask what to do.

## Project Overview
**What:** Python pipeline that reads an Archicad BIM model via API, extracts FF&E data across 19 schedule categories, and outputs EID-branded Excel schedules + a live project dashboard website.
**Who:** EID / BIM6x (Lincoln Ellis)
**Model:** McCollum - 408 Cayuse Court 29 (test project)
**Spec:** `EBIF-CALC_Architecture.docx` in project root
**Website:** https://sprtic1.github.io/ebif-calc/

## Two-Step Workflow
1. **Run the EID Report** -> Archicad -> Individual Excel files per schedule
2. *Designer fills in specs manually in each Excel file*
3. **Publish the EID Dashboard** -> Excel files -> Website + QC report

## How to Run
```
python main.py extract        # Step 1: Archicad -> per-schedule Excel files
python main.py publish         # Step 2: Excel files -> Website + QC
python main.py extract --offline  # Use cached data (testing)
```

## Project Output Paths
Output paths are stored per-project in `config/projects.json`. On first run for a new project, the pipeline asks where to save files. Example:
```json
{
  "projects": {
    "mccollum-408-cayuse-court-29": {
      "name": "McCollum - 408 Cayuse Court 29",
      "output_path": "C:\\Users\\linco\\EID Dropbox\\PROJECTS\\McCollum\\Schedules"
    }
  }
}
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
