"""EBIF-CALC — Main Pipeline Entry Point.

Two-step workflow:
  Step 1 (extract): Archicad -> Excel template (working document)
  Step 2 (publish): Excel -> Website dashboard + QC report

Usage:
    python main.py extract             # Step 1: Archicad -> Excel template
    python main.py publish             # Step 2: Excel -> Website + QC
    python main.py extract --offline   # Step 1 with cached data (testing)
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ebif")

BASE = Path(__file__).parent
CONFIG_DIR = BASE / "config"


def load_config() -> tuple[dict, list[dict]]:
    """Load settings.json and schedules.json."""
    settings_path = CONFIG_DIR / "settings.json"
    schedules_path = CONFIG_DIR / "schedules.json"

    if not settings_path.exists():
        logger.error("Missing config/settings.json — run setup.py first")
        sys.exit(1)

    settings = json.load(open(settings_path))
    schedules_data = json.load(open(schedules_path))
    schedule_defs = schedules_data.get("schedules", [])

    return settings, schedule_defs


def slugify(name: str) -> str:
    """Convert project name to filename-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# ══════════════════════════════════════════════════════════
# STEP 1: EXTRACT — Archicad → Excel Template
# ══════════════════════════════════════════════════════════

def step1_extract(offline: bool = False):
    """Step 1: Connect to Archicad, extract schedules, generate Excel template."""
    start_time = time.time()

    print("=" * 60)
    print("  EBIF-CALC v1.0 — Step 1: Run the EID Report")
    print("  Archicad -> Excel Template (Working Document)")
    print("=" * 60)

    settings, schedule_defs = load_config()
    project_name = settings.get("project_name", "Unknown Project")
    project_slug = slugify(project_name)
    output_dir = Path(settings.get("output_folder", "")) or (BASE / "output")

    print(f"  Project: {project_name}")
    print()

    if offline:
        cache_path = BASE / "_mcp_schedules.json"
        if not cache_path.exists():
            logger.error("No cached data at %s", cache_path)
            sys.exit(1)
        cached = json.load(open(cache_path))
        schedules = cached.get("schedules", {})
        logger.info("Loaded cached data: %d schedules", len(schedules))
    else:
        from ebif.api_bridge import load_connection
        from ebif.schedule_extractor import extract_all_schedules

        conn = load_connection(settings)
        print(f"  Extracting {len(schedule_defs)} schedules...")
        schedules = extract_all_schedules(conn, schedule_defs)

    # Print schedule summary
    print()
    print("  --- Schedule Summary ---")
    total_elements = 0
    active_count = 0
    total_populated = 0
    total_blank = 0
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        count = len(rows)
        total_elements += count
        if count > 0:
            active_count += 1
            # Count populated vs blank fields
            skip = {"Element ID", "Qty", "Zone", "Room"}
            pop = blank = 0
            for r in rows:
                for col in sdef.get("columns", []):
                    if col in skip:
                        continue
                    v = r.get(col, "")
                    if v is not None and str(v).strip() not in ("", "None", "0"):
                        pop += 1
                    else:
                        blank += 1
            total_populated += pop
            total_blank += blank
            status = f"{pop} filled, {blank} blank" if blank > 0 else "all filled"
            print(f"    {sdef['name']:.<35} {count:>4} elements  ({status})")

    print(f"    {'TOTAL':.<35} {total_elements:>4} elements")
    print(f"    Active schedules: {active_count} / {len(schedule_defs)}")
    if total_blank > 0:
        print(f"    Fields to complete: {total_blank} blank across all schedules")
    print()

    # Generate Excel template
    from ebif.output.excel_writer import write_template
    excel_path = write_template(
        schedules=schedules,
        schedule_defs=schedule_defs,
        project_name=project_name,
        output_dir=output_dir,
        project_slug=project_slug,
    )

    duration = time.time() - start_time
    print(f"  Excel: {excel_path}")
    print(f"  Time:  {duration:.1f}s")
    print()
    print("=" * 60)
    print(f"  [OK] Step 1 complete — Excel template ready for data entry")
    print(f"       Edit: {excel_path}")
    print(f"       Then run: Publish the EID Dashboard")
    print("=" * 60)


# ══════════════════════════════════════════════════════════
# STEP 2: PUBLISH — Excel → Website + QC
# ══════════════════════════════════════════════════════════

def step2_publish():
    """Step 2: Read completed Excel, generate dashboard, push to GitHub."""
    start_time = time.time()

    print("=" * 60)
    print("  EBIF-CALC v1.0 — Step 2: Publish the EID Dashboard")
    print("  Excel -> Website + QC Report")
    print("=" * 60)

    settings, schedule_defs = load_config()
    project_name = settings.get("project_name", "Unknown Project")
    project_slug = slugify(project_name)
    output_dir = Path(settings.get("output_folder", "")) or (BASE / "output")

    print(f"  Project: {project_name}")
    print()

    # Find and read the Excel working document
    from ebif.excel_reader import find_workbook, read_workbook

    excel_path = find_workbook(output_dir, project_slug)
    if not excel_path:
        logger.error("No Excel workbook found in %s", output_dir)
        logger.error("Run Step 1 first: python main.py extract")
        sys.exit(1)

    print(f"  Reading: {excel_path.name}")
    schedules = read_workbook(excel_path, schedule_defs)

    # Print schedule summary
    print()
    print("  --- Schedule Summary ---")
    total_elements = 0
    active_count = 0
    for sdef in schedule_defs:
        sid = sdef["id"]
        count = len(schedules.get(sid, []))
        total_elements += count
        if count > 0:
            active_count += 1
            print(f"    {sdef['name']:.<35} {count:>4} elements")
    print(f"    {'TOTAL':.<35} {total_elements:>4} elements")
    print(f"    Active schedules: {active_count} / {len(schedule_defs)}")
    print()

    # QC checks (publish mode — full completeness check)
    from ebif.qc_checker import check_all_schedules, completion_metrics

    qc_issues = check_all_schedules(schedules, schedule_defs, mode="publish")
    metrics = completion_metrics(schedules, schedule_defs)
    warnings = sum(1 for q in qc_issues if q["severity"] == "Warning")

    print(f"  --- Completion ---")
    print(f"    Complete rows:   {metrics['complete_rows']} / {metrics['total_rows']} ({metrics['pct_complete']}%)")
    print(f"    Incomplete rows: {metrics['incomplete_rows']}")
    print(f"    QC warnings:     {warnings}")
    print()

    # Generate JSON for website
    duration = time.time() - start_time
    from ebif.output.json_writer import build_dashboard_json, write_json

    json_data = build_dashboard_json(
        schedules=schedules,
        schedule_defs=schedule_defs,
        qc_issues=qc_issues,
        project_name=project_name,
        pipeline_duration_sec=duration,
    )
    json_path = write_json(json_data, output_dir)
    print(f"  JSON:  {json_path}")

    # Deploy website
    website_repo = Path(settings.get("website_repo", ""))
    site_url = ""
    if website_repo and website_repo.exists():
        from ebif.output.website import deploy_website, slugify as web_slugify
        deploy_website(json_data, website_repo, project_name)
        slug = web_slugify(project_name)
        site_url = f"https://{settings.get('github_user', 'sprtic1')}.github.io/{settings.get('github_repo', 'ebif-calc')}/{slug}/"
        print(f"  Website: {site_url}")
    else:
        print("  Website: skipped (repo not found)")

    # Generate published Excel with QC tab
    from ebif.output.excel_writer import write_published
    pub_path = write_published(
        schedules=schedules,
        schedule_defs=schedule_defs,
        qc_issues=qc_issues,
        project_name=project_name,
        output_dir=output_dir,
        project_slug=project_slug,
    )
    print(f"  Excel:   {pub_path}")

    duration = time.time() - start_time
    print()
    print(f"  Time:  {duration:.1f}s")
    print()
    print("=" * 60)
    if site_url:
        print(f"  [OK] Dashboard published — {site_url}")
    else:
        print(f"  [OK] Dashboard data generated — {json_path}")
    print(f"       {metrics['pct_complete']}% complete ({metrics['complete_rows']}/{metrics['total_rows']} rows)")
    if metrics['incomplete_rows'] > 0:
        print(f"       {metrics['incomplete_rows']} rows need spec data — update Excel and re-publish")
    print("=" * 60)


# ══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("EBIF-CALC — Ellis Building Intelligence Framework")
        print()
        print("Usage:")
        print("  python main.py extract             Step 1: Archicad -> Excel template")
        print("  python main.py publish             Step 2: Excel -> Website + QC")
        print("  python main.py extract --offline   Step 1 with cached data (testing)")
        print()
        print("Workflow:")
        print("  1. Run 'extract' to pull data from Archicad into Excel")
        print("  2. Fill in spec data (vendor, model, tear sheet #, etc.) in Excel")
        print("  3. Run 'publish' to generate the website dashboard")
        return

    command = args[0].lower()
    offline = "--offline" in args

    if command == "extract":
        step1_extract(offline=offline)
    elif command == "publish":
        step2_publish()
    else:
        print(f"Unknown command: {command}")
        print("Use 'extract' or 'publish'. Run with --help for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
