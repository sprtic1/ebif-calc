"""EBIF-CALC -- Main Pipeline Entry Point.

Two-step workflow:
  Step 1 (extract): Archicad -> individual Excel files per schedule
  Step 2 (publish): Excel files -> Website dashboard + QC report

Usage:
    python main.py extract             Step 1: Archicad -> Excel files
    python main.py publish             Step 2: Excel -> Website + QC
    python main.py extract --offline   Step 1 with cached data (testing)
"""

import json
import logging
import re
import sys
import time
from pathlib import Path

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
    settings = json.load(open(CONFIG_DIR / "settings.json"))
    schedules_data = json.load(open(CONFIG_DIR / "schedules.json"))
    return settings, schedules_data.get("schedules", [])


def slugify(name: str) -> str:
    """Convert project name to filename-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# ------------------------------------------------------------------
# Project path management (config/projects.json)
# ------------------------------------------------------------------

def _load_projects() -> dict:
    """Load the projects registry."""
    path = CONFIG_DIR / "projects.json"
    if path.exists():
        return json.load(open(path))
    return {"projects": {}}


def _save_projects(data: dict):
    """Save the projects registry."""
    with open(CONFIG_DIR / "projects.json", "w") as f:
        json.dump(data, f, indent=2)


def get_output_dir(project_slug: str, project_name: str) -> Path:
    """Get the output directory for a project.

    On first run for a new project, prompts for the path and saves it.
    On subsequent runs, uses the saved path automatically.
    """
    registry = _load_projects()
    projects = registry.get("projects", {})

    if project_slug in projects:
        saved_path = projects[project_slug].get("output_path", "")
        if saved_path:
            p = Path(saved_path)
            logger.info("Using saved output path for '%s': %s", project_name, p)
            return p

    # First run for this project -- ask the user
    print()
    print(f"  First run for project: {project_name}")
    answer = input("  Where do you want the Excel files saved for this project?\n  > ").strip()

    if not answer:
        answer = str(BASE / "output")
        print(f"  (Using default: {answer})")

    out_path = Path(answer)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save to projects.json
    projects[project_slug] = {
        "name": project_name,
        "output_path": str(out_path),
    }
    registry["projects"] = projects
    _save_projects(registry)
    logger.info("Saved output path for '%s': %s", project_slug, out_path)

    return out_path


# ==================================================================
# STEP 1: EXTRACT -- Archicad -> Individual Excel Files
# ==================================================================

def step1_extract(offline: bool = False):
    """Step 1: Connect to Archicad, extract schedules, write per-schedule Excel files."""
    start_time = time.time()

    print("=" * 60)
    print("  EBIF-CALC v1.0 -- Step 1: Run the EID Report")
    print("  Archicad -> Excel Files (Working Documents)")
    print("=" * 60)

    settings, schedule_defs = load_config()
    project_name = settings.get("project_name", "Unknown Project")
    project_slug = slugify(project_name)

    print(f"  Project: {project_name}")

    # Get output directory (prompts on first run)
    output_dir = get_output_dir(project_slug, project_name)
    print(f"  Output:  {output_dir}")
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

    # Print summary
    print()
    print("  --- Schedule Summary ---")
    total_elements = 0
    active_count = 0
    total_blank = 0
    for sdef in schedule_defs:
        sid = sdef["id"]
        rows = schedules.get(sid, [])
        count = len(rows)
        total_elements += count
        if count > 0:
            active_count += 1
            skip = {"Element ID", "Qty", "Zone", "Room"}
            blank = sum(1 for r in rows for col in sdef.get("columns", [])
                        if col not in skip and
                        (r.get(col) is None or str(r.get(col, "")).strip() in ("", "None", "0")))
            total_blank += blank
            status = f"{blank} blank fields" if blank > 0 else "all filled"
            print(f"    {sdef['name']:.<35} {count:>4} elements  ({status})")

    print(f"    {'TOTAL':.<35} {total_elements:>4} elements")
    print(f"    Active schedules: {active_count} / {len(schedule_defs)}")
    if total_blank > 0:
        print(f"    Fields to complete: {total_blank}")
    print()

    # Write individual Excel files
    from ebif.output.excel_writer import write_template
    paths = write_template(
        schedules=schedules,
        schedule_defs=schedule_defs,
        project_name=project_name,
        output_dir=output_dir,
    )

    print(f"  --- Files Written ---")
    for p in paths:
        print(f"    {p.name}")

    duration = time.time() - start_time
    print()
    print(f"  Time:  {duration:.1f}s")
    print()
    print("=" * 60)
    print(f"  [OK] Step 1 complete -- {len(paths)} Excel files written")
    print(f"       Folder: {output_dir}")
    print(f"       Fill in spec data, then run: Publish the EID Dashboard")
    print("=" * 60)


# ==================================================================
# STEP 2: PUBLISH -- Excel Files -> Website + QC
# ==================================================================

def step2_publish():
    """Step 2: Read completed Excel files, generate dashboard, push to GitHub."""
    start_time = time.time()

    print("=" * 60)
    print("  EBIF-CALC v1.0 -- Step 2: Publish the EID Dashboard")
    print("  Excel -> Website + QC Report")
    print("=" * 60)

    settings, schedule_defs = load_config()
    project_name = settings.get("project_name", "Unknown Project")
    project_slug = slugify(project_name)

    # Get output directory (must already exist from Step 1)
    registry = _load_projects()
    projects = registry.get("projects", {})
    if project_slug not in projects:
        logger.error("No saved output path for '%s'. Run Step 1 first.", project_name)
        sys.exit(1)

    output_dir = Path(projects[project_slug]["output_path"])
    print(f"  Project: {project_name}")
    print(f"  Reading: {output_dir}")
    print()

    # Read individual schedule files
    from ebif.excel_reader import read_all_schedules, has_schedule_files

    if not has_schedule_files(output_dir, schedule_defs):
        logger.error("No schedule Excel files found in %s", output_dir)
        logger.error("Run Step 1 first: python main.py extract")
        sys.exit(1)

    schedules = read_all_schedules(output_dir, schedule_defs)

    # Print summary
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

    # QC (publish mode)
    from ebif.qc_checker import check_all_schedules, completion_metrics

    qc_issues = check_all_schedules(schedules, schedule_defs, mode="publish")
    metrics = completion_metrics(schedules, schedule_defs)
    warnings = sum(1 for q in qc_issues if q["severity"] == "Warning")

    print(f"  --- Completion ---")
    print(f"    Complete rows:   {metrics['complete_rows']} / {metrics['total_rows']} ({metrics['pct_complete']}%)")
    print(f"    Incomplete rows: {metrics['incomplete_rows']}")
    print(f"    QC warnings:     {warnings}")
    print()

    # Generate JSON
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
    print(f"  JSON:    {json_path}")

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

    # Write published Excel files (updates schedule files + adds QC)
    from ebif.output.excel_writer import write_published
    pub_paths = write_published(
        schedules=schedules,
        schedule_defs=schedule_defs,
        qc_issues=qc_issues,
        project_name=project_name,
        output_dir=output_dir,
    )

    duration = time.time() - start_time
    print()
    print(f"  Time:  {duration:.1f}s")
    print()
    print("=" * 60)
    if site_url:
        print(f"  [OK] Dashboard published -- {site_url}")
    else:
        print(f"  [OK] Dashboard data generated -- {json_path}")
    print(f"       {metrics['pct_complete']}% complete ({metrics['complete_rows']}/{metrics['total_rows']} rows)")
    if metrics['incomplete_rows'] > 0:
        print(f"       {metrics['incomplete_rows']} rows need spec data -- update Excel and re-publish")
    print("=" * 60)


# ==================================================================
# CLI
# ==================================================================

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("EBIF-CALC -- Ellis Building Intelligence Framework")
        print()
        print("Usage:")
        print("  python main.py extract             Step 1: Archicad -> Excel files")
        print("  python main.py publish             Step 2: Excel -> Website + QC")
        print("  python main.py extract --offline   Step 1 with cached data (testing)")
        print()
        print("Workflow:")
        print("  1. Run 'extract' to pull data from Archicad into per-schedule Excel files")
        print("  2. Fill in spec data (vendor, model, tear sheet #, etc.) in each Excel file")
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
