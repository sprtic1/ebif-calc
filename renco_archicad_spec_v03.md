# RENCO Block Calculator — Claude Code Build Spec
**Version:** 0.3 (full rewrite — optimized for speed + webpage)
**Project:** renco-calc
**Author:** EID / BIM6x
**Status:** Complete rewrite from scratch. Preserve all functionality from v0.2. Prioritize speed, clean architecture, and a JSON output layer for the upcoming BIM6x/Renco webpage.

---

## 1. Project Goals

1. Read all Renco-composited wall elements from a live ArchiCAD model in a single batched fetch
2. Calculate Renco block quantities per wall using confirmed block catalog
3. Detect and flag problematic walls (non-modular, curved, irregular) with X suffix in ArchiCAD
4. Write warning reasons back to ArchiCAD RENCO REPORT property
5. Aggregate totals by block type across the entire project
6. Calculate pallet counts and container requirements
7. Output results to a polished EID-branded Excel file
8. Output results to a clean JSON file for the webpage
9. Complete a full run in under 3 minutes

---

## 2. Guiding Principles

- **Speed first** — all ArchiCAD data fetched in minimum API calls. Never loop one-wall-at-a-time.
- **No caching ever** — always fetch fresh from ArchiCAD. Never read from a saved walls file.
- **No silent failures** — every excluded or flagged wall gets an X suffix and RENCO REPORT entry in ArchiCAD
- **Data-driven** — block catalog and container specs live in JSON config, never hardcoded
- **Webpage-ready** — every run produces both Excel and JSON output from the same data
- **Units-agnostic** — auto-detect metric vs imperial from ArchiCAD, always work in inches internally

---

## 3. Repository Structure

```
renco-calc/
│
├── config/
│   ├── blocks.json          # Block catalog — both series, confirmed dimensions
│   ├── containers.json      # ISO container specs — confirmed real-world dimensions
│   └── settings.json        # ArchiCAD connection (port 19724), tolerances, flags
│
├── renco/
│   ├── __init__.py
│   ├── archicad_client.py   # ALL ArchiCAD API calls — batched, single responsibility
│   ├── wall_parser.py       # Raw API data → typed Wall objects, unit conversion
│   ├── block_catalog.py     # Load catalog, lookup by series/type
│   ├── calculator.py        # Greedy fill engine — per wall block calculation
│   ├── aggregator.py        # Wall results → project totals
│   ├── packing.py           # Pallet + container bin-packing
│   └── output/
│       ├── excel_writer.py  # EID-branded Excel — all sheets
│       └── json_writer.py   # Clean JSON for webpage
│
├── tests/
│   ├── mock_data/
│   │   └── sample_walls.json
│   ├── test_wall_parser.py
│   ├── test_calculator.py
│   ├── test_aggregator.py
│   └── test_packing.py
│
├── main.py                  # Entry point — runs full pipeline
├── requirements.txt
└── README.md
```

---

## 4. Config Files

### 4.1 `config/settings.json`

```json
{
  "archicad": {
    "host": "localhost",
    "port": 19724,
    "timeout_seconds": 15
  },
  "filter": {
    "composite_name_contains": "renco",
    "case_sensitive": false
  },
  "calculation": {
    "bond_pattern": "running",
    "waste_factor_percent": 0,
    "modular_tolerance_inches": 0.1
  },
  "archicad_writeback": {
    "enabled": true,
    "property_group": "EID GENERAL PROPERTIES",
    "property_name": "RENCO REPORT",
    "clear_on_run": true
  },
  "output": {
    "excel_filename_prefix": "renco_schedule",
    "json_filename_prefix": "renco_data",
    "include_excluded_sheet": false
  }
}
```

### 4.2 `config/blocks.json`

```json
{
  "version": "0.2-confirmed-dimensions",
  "source": "RENCO Sales Brochure 2024, page 12",
  "module_height_inches": 8,
  "series": {
    "residential": {
      "width_in": 6,
      "height_in": 8,
      "blocks": [
        {"id": "RES-3",  "length_in": 3,  "weight_lbs": 1.6,  "confirmed_weight": false},
        {"id": "RES-6",  "length_in": 6,  "weight_lbs": 3.2,  "confirmed_weight": false},
        {"id": "RES-12", "length_in": 12, "weight_lbs": 6.4,  "confirmed_weight": false},
        {"id": "RES-30", "length_in": 30, "weight_lbs": 16.0, "confirmed_weight": false}
      ]
    },
    "commercial": {
      "width_in": 8,
      "height_in": 8,
      "blocks": [
        {"id": "COM-4",  "length_in": 4,  "weight_lbs": 2.1,  "confirmed_weight": false},
        {"id": "COM-8",  "length_in": 8,  "weight_lbs": 4.3,  "confirmed_weight": false},
        {"id": "COM-16", "length_in": 16, "weight_lbs": 8.5,  "confirmed_weight": true},
        {"id": "COM-32", "length_in": 32, "weight_lbs": 17.0, "confirmed_weight": false}
      ]
    }
  }
}
```

### 4.3 `config/containers.json`

```json
{
  "containers": [
    {
      "id": "ISO-40",
      "name": "40ft Standard ISO Container",
      "interior_length_in": 473,
      "interior_width_in": 93,
      "interior_height_in": 94,
      "max_payload_lbs": 58935,
      "pallets_per_layer": 22,
      "max_layers": 2,
      "max_pallets": 44
    },
    {
      "id": "ISO-20",
      "name": "20ft Standard ISO Container",
      "interior_length_in": 232,
      "interior_width_in": 93,
      "interior_height_in": 94,
      "max_payload_lbs": 47840,
      "pallets_per_layer": 10,
      "max_layers": 2,
      "max_pallets": 20
    }
  ],
  "default_container": "ISO-40",
  "pallet": {
    "length_in": 48,
    "width_in": 40,
    "height_empty_in": 4.75,
    "weight_lbs": 37,
    "max_load_lbs": 4600,
    "blocks_per_pallet": 40,
    "note": "Standard GMA pallet. Blocks per pallet TBC from Renco."
  }
}
```

---

## 5. ArchiCAD Client — Batched API Calls

**This is the most critical performance module.** All data must be fetched in the minimum number of API calls possible. No per-wall loops for API requests.

```python
class ArchiCADClient:
    """
    All ArchiCAD communication. Strict rule: never call the API
    in a loop. Batch everything.
    """

    def get_project_info(self) -> dict:
        """Single call: project name, file path, units."""

    def get_all_walls_batched(self) -> list[dict]:
        """
        Fetch all wall elements AND all their properties in
        the minimum number of API calls:
        
        Call 1: GetElementsByType(Wall) → list of GUIDs
        Call 2: GetDetailsOfElements(all GUIDs) → geometry for all walls
        Call 3: GetPropertyValuesOfElements(all GUIDs, property_ids) → 
                composite name, height, story, structural function for all walls
        Call 4: GetStories() → story index → story name map
        Call 5: GetElementsByType(Door) + GetElementsByType(Window) →
                all opening GUIDs with host wall GUID
        
        Total: 5 API calls regardless of model size.
        Returns: list of raw wall dicts with all data attached.
        """

    def set_wall_properties_batched(self, updates: list[dict]) -> None:
        """
        Write Wall ID and RENCO REPORT back to ArchiCAD for ALL walls
        in a single batched SetPropertyValuesOfElements call.
        Never write one wall at a time.
        """

    def detect_units(self) -> str:
        """Return 'metric' or 'imperial' from project settings."""
```

---

## 6. Wall Parser

```python
@dataclass
class Opening:
    type: str           # "door" or "window"
    width_in: float
    height_in: float

@dataclass
class Wall:
    guid: str
    wall_id: str        # Assigned sequentially: WALL-001, WALL-002 etc
    story_name: str     # Actual story name from ArchiCAD e.g. "MAIN FLOOR"
    length_in: float
    height_in: float
    thickness_in: float
    series: str         # "residential" or "commercial" — derived from thickness
    composite_name: str
    openings: list[Opening]
    is_rectangular: bool    # False if curved or irregular geometry
    arc_angle: float        # from ArchiCAD — non-zero means curved
    flags: list[str]        # List of warning reasons e.g. ["non-modular length: 2in remainder"]
    excluded: bool          # True if excluded from calculation (curved walls etc)
    exclude_reason: str     # Written to RENCO REPORT if excluded
```

**Wall ID assignment rules:**
- Assigned once, preserved across runs if already set in ArchiCAD
- New walls get next available number
- Ordered by story index (lowest first), then by X coordinate
- X suffix appended to any wall with flags OR excluded=True
- Before every run: clear all X suffixes and RENCO REPORT values
- After every run: write updated IDs and RENCO REPORT back to ArchiCAD in one batch call

**Unit conversion:**
- Auto-detect project units from ArchiCAD API at run start
- Convert all metric values to inches before any processing
- Internally always work in inches

**Composite filter:**
- Include wall if composite_name.lower().strip() contains "renco"
- Excluded walls (non-Renco) still get their IDs but get no X suffix unless they had one previously

**Geometry checks (in order):**
1. arc_angle > 0.001 → curved, excluded=True, exclude_reason="Curved wall — excluded from Renco calculation"
2. Vertex analysis: if polygon vertices do not form a rectangle (4 corners, right angles within 1° tolerance) → irregular, flag with X
3. thickness not 6in or 8in → flag "Wall thickness not standard Renco width"
4. length < series closure block length → flag "Wall too short for one block"
5. height < 8in → flag "Wall shorter than one course"
6. length not on modular grid → flag "Non-modular length: Xin remainder"
7. height not multiple of 8in → flag "Non-modular height: Xin remainder"
8. opening wider than wall → flag "Opening wider than wall"
9. opening taller than wall → flag "Opening taller than wall"
10. opening within one closure block of wall end → flag "Opening too close to wall end"
11. wall area > 50% openings → flag "More than 50% opening area"
12. wall length < 24in → flag "Very short wall — verify intent"
13. duplicate GUID → flag "Duplicate GUID detected"

---

## 7. Calculator — Greedy Fill Engine

```python
def calculate_wall(wall: Wall, catalog: BlockCatalog) -> WallResult:
    """
    For each course (wall.height_in / 8 courses total):
    
    Even courses: greedy fill from left
      - Use largest block that fits: COM-32 → COM-16 → COM-8 → COM-4
      - For residential: RES-30 → RES-12 → RES-6 → RES-3
    
    Odd courses: offset by half field block (running bond)
      - Start with half block, then greedy fill
    
    For each course, subtract opening extents course by course.
    
    Return: dict of {block_id: count} per wall.
    """
```

**No API calls in this module. Pure calculation only.**

---

## 8. Aggregator

Rolls up all WallResult objects into ProjectTotals:
- blocks_by_type: {block_id: total_count}
- blocks_by_series: split residential vs commercial
- total_weight_lbs: sum using weights from catalog
- walls_with_flags: count
- excluded_walls: list of excluded wall IDs and reasons

---

## 9. Packing

```python
def calculate_pallets(totals: ProjectTotals, catalog, container_config) -> PackingResult:
    """
    1. For each block type: ceil(count / blocks_per_pallet) = pallets needed
    2. Assign pallets to containers:
       - Fill container row by row (2 rows of 11 = 22 per layer, 2 layers = 44 per container)
       - Check both volume (pallet count) AND weight (payload limit)
       - Use whichever constraint binds first
    3. Return: containers_required, pallet_manifest, container_assignments
    """
```

PackingResult includes container_assignments — a list of lists mapping each pallet
to a container number and position. This drives both the Excel layout diagram and the JSON output.

---

## 10. Excel Writer

**Sheets in order:**

### Sheet 1: Summary
- Project name, date, ArchiCAD file
- Total walls processed, walls with warnings
- Weight input table — one row per block type with weight_lbs as editable input cell
  - COM-16: 8.5 lbs (confirmed)
  - All others: estimated values, clearly marked
  - These cells are the single source of truth for all weight calculations in the workbook
- Block totals table: block ID, name, series, count, weight
- Grand totals: total blocks, total weight, containers required

### Sheet 2: Wall Schedule
Columns in order:
| Col | Header | Notes |
|-----|--------|-------|
| A | Wall ID | WALL-001, WALL-003X etc |
| B | Story | Actual ArchiCAD story name |
| C | Wall Length | Feet-inches format: 21'-4" |
| D | Height (in) | Numeric inches |
| E | Series | Right-aligned |
| F | Courses (rows) | Number of horizontal block courses |
| G | Openings | Count of doors + windows |
| H | COM-16 | Block count |
| I | COM-32 | Block count |
| J | COM-4 | Block count |
| K | COM-8 | Block count |
| L | RES-12 | Only if residential walls present |
| M | RES-30 | Only if residential walls present |
| N | RES-6 | Only if residential walls present |
| O | RES-3 | Only if residential walls present |
| P | Total Blocks | =SUM(H:O) Excel formula |
| Q | Weight (lbs) | Formula referencing Summary weight inputs |

- Last row: TOTALS row with =SUM() for all numeric columns, bold, #868D54 background, white text
- Freeze panes at B2
- Banded rows: alternate white / #C2C8A2
- Header row: #868D54 background, white text, bold, Arial Narrow
- X-flagged walls: light red background #FFE0E0 on Wall ID cell only
- Hide residential columns if no residential walls in project

### Sheet 3: Container Layout
One section per container, stacked vertically on same sheet.

For each container:
- Header row: "Container N of M — 40ft ISO — 473" × 93""
- Label: "Indicative layout — pallet heights and stacking TBC with Renco"
- Grid: 11 columns × 4 rows (2 layers × 2 rows per layer)
- Each cell: pallet number + block type + block count, text wrapped
- Cell background: #868D54 for commercial, #C2C8A2 for residential, #CCCCCC for EMPTY
- Cell borders: thin black
- Column width: 12 characters
- Row height: 45pt to fit 3 lines of text
- Gap of 3 empty rows between containers

### Sheet 4: Container Manifest
- Container summary header
- Pallet table: block ID, total blocks, blocks/pallet, pallets, weight/block (from Summary inputs), pallet weight
- Total weight row
- All weight cells reference Summary weight input cells — never hardcoded

### Sheet 5: Assumptions & Warnings
- Catalog assumptions (confirmed vs estimated)
- Pallet spec assumptions
- All wall-level warnings listed with wall ID and full description
- Note: weights are estimated pending Renco confirmation

**Styling rules (all sheets):**
- Font: Arial Narrow body, Lato Bold headers (fallback Arial Bold)
- Header color: #868D54 (olive green)
- Banded row color: #C2C8A2 (sage)
- All numbers right-aligned
- All text left-aligned
- No gridlines shown (use cell borders instead on data tables)

---

## 11. JSON Writer

This is new in v0.3 — produces a clean JSON file alongside the Excel for the webpage.

```json
{
  "project": {
    "name": "Ellis Beach Chalet 29",
    "run_date": "2026-04-02T17:08:00",
    "archicad_file": "Ellis Beach Chalet 29.pln",
    "total_walls": 24,
    "walls_with_warnings": 4,
    "excluded_walls": 1
  },
  "summary": {
    "total_blocks": 2450,
    "total_weight_lbs": 32450.5,
    "weight_is_estimated": true,
    "containers_required": 4,
    "container_type": "ISO-40"
  },
  "blocks": [
    {"id": "COM-32", "name": "Commercial Long Block", "series": "commercial", "count": 1608, "weight_per_block_lbs": 17.0, "confirmed_weight": false, "total_weight_lbs": 27336.0},
    {"id": "COM-16", "name": "Commercial Standard Block", "series": "commercial", "count": 182, "weight_per_block_lbs": 8.5, "confirmed_weight": true, "total_weight_lbs": 1547.0}
  ],
  "walls": [
    {
      "id": "WALL-001",
      "story": "GROUNDSKEEPER",
      "length_ft_in": "6'-8\"",
      "length_in": 80,
      "height_in": 112,
      "series": "commercial",
      "courses": 14,
      "openings": 1,
      "blocks": {"COM-16": 12, "COM-32": 6, "COM-4": 0, "COM-8": 15},
      "total_blocks": 33,
      "weight_lbs": 267.8,
      "flagged": false,
      "flag_reason": null
    }
  ],
  "containers": [
    {
      "container_number": 1,
      "type": "ISO-40",
      "pallets": [
        {"pallet_number": 1, "block_id": "COM-32", "block_count": 40, "position": {"layer": 1, "row": 1, "col": 1}},
        {"pallet_number": 2, "block_id": "COM-32", "block_count": 40, "position": {"layer": 1, "row": 1, "col": 2}}
      ],
      "total_pallets": 44,
      "utilisation_percent": 92.1
    }
  ],
  "warnings": [
    {"wall_id": "WALL-016X", "reason": "Non-modular length: 1.5in remainder"},
    {"wall_id": "WALL-023X", "reason": "Curved wall — excluded from Renco calculation"}
  ]
}
```

This JSON file is the exact data contract the webpage will consume. It should be saved to the output folder as `renco_data_[projectname]_[date].json`.

---

## 12. Main Pipeline (`main.py`)

```python
def run():
    # 1. Load config
    # 2. Connect to ArchiCAD, detect units
    # 3. ONE batched fetch: all walls + properties + openings + stories
    # 4. Parse walls: filter, validate, assign IDs, detect geometry issues
    # 5. Calculate blocks per wall (no API calls)
    # 6. Aggregate project totals
    # 7. Calculate pallet + container packing
    # 8. Write Excel
    # 9. Write JSON
    # 10. ONE batched writeback: all wall IDs + RENCO REPORT to ArchiCAD
    # 11. Print summary to terminal
    
    # Target: steps 3 and 10 are the only API calls.
    # Everything else is pure Python computation.
```

---

## 13. Testing

All tests use mock data from `tests/mock_data/sample_walls.json`.
No tests should require a live ArchiCAD connection.

Priority test cases:
- Standard commercial wall, modular length, no openings
- Standard residential wall, modular length, no openings  
- Wall with door opening
- Wall with window opening
- Non-modular wall length
- Curved wall detection
- Irregular geometry detection
- Metric input → correct inch conversion
- Imperial input → correct passthrough
- Container packing: volume-limited scenario
- Container packing: weight-limited scenario
- Wall ID preservation across runs
- X suffix assignment and clearing

---

## 14. Known Gaps — To Fill from Renco (Karlie Fike, kfike@renco-usa.com)

| Item | Status | Notes |
|------|--------|-------|
| Block weights — all except COM-16 | Estimated | Proportional volume calculation used |
| Color codes — Build by Color scheme | Unknown | For future chromatic plan output |
| Blocks per pallet — all types | Assumed 40 | Standard GMA pallet assumption |
| Pallet height loaded | Unknown | Needed for accurate stacking check |
| Header/lintel block over openings | Unknown | Not yet in catalog |
| Corner block treatment | Unknown | Currently using closure blocks as proxy |
| Adhesive (Plexus MA530) coverage rate | Unknown | For adhesive takeoff module |
| Floor joist dimensions + span ratings | Unknown | For floor schedule module |
| Decking panel sizes | Unknown | For floor schedule module |

---

## 15. Future Extensions

- **Build by Color plan output** — chromatic assembly drawings per floor matching Renco's installation plan format
- **Floor schedule** — slab elements with Renco composite → joist and decking quantities
- **Adhesive takeoff** — linear feet of joints × coverage rate
- **Cost estimation** — block cost + adhesive + shipping
- **BIM6x/Renco webpage** — consumes the JSON output from this pipeline
- **ArchiCAD native add-on** — C++ panel replacing the Python companion script
