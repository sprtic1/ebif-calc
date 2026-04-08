"""RENCO Block Calculator v0.4 — MCP-based pipeline entry point.

All ArchiCAD I/O is handled by Claude Code via MCP tools.
This script reads pre-fetched wall data from _mcp_walls.json,
runs all computation, and writes writeback entries to _mcp_writeback.json.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("renco")

BASE = Path(__file__).parent
CFG = BASE / "config"
MCP_INPUT = BASE / "_mcp_walls.json"
MCP_OUTPUT = BASE / "_mcp_writeback.json"


def run():
    t0 = time.time()
    print("=" * 60)
    print("  RENCO Block Calculator v0.4 (MCP)")
    print("=" * 60)

    # 1. Load config
    with open(CFG / "settings.json") as f:
        settings = json.load(f)

    from renco.block_catalog import BlockCatalog
    catalog = BlockCatalog(str(CFG / "blocks.json"))

    wb_cfg = settings["archicad_writeback"]
    paths = settings.get("paths", {})
    project_name = settings.get("project", {}).get("name", "Untitled Project")

    # 2. Read MCP-fetched wall data
    if not MCP_INPUT.exists():
        print(f"\n  [ERROR] No MCP wall data found at {MCP_INPUT}")
        print("  Run the /renco-report skill to fetch data via MCP first.")
        return
    with open(MCP_INPUT) as f:
        mcp_data = json.load(f)

    raw_walls = mcp_data["walls"]
    report_guid = mcp_data.get("report_guid", "")
    print(f"  Loaded {len(raw_walls)} walls from MCP data")

    if not raw_walls:
        print("  [WARNING] No walls found.")
        return

    if not report_guid:
        print("  [WARNING] RENCO REPORT property not found — writeback will skip reports")

    # 3. Parse, filter, validate, assign IDs
    from renco.wall_parser import parse_walls, assign_ids, run_checks, renco_report_value
    renco_walls, excluded_walls = parse_walls(raw_walls, settings["filter"]["composite_name_contains"])

    excluded_renco = [w for w in excluded_walls if w.composite_name and "renco" in w.composite_name.lower()]

    all_renco_for_ids = renco_walls + excluded_renco
    assign_ids(all_renco_for_ids)
    run_checks(renco_walls, catalog)

    for w in excluded_renco:
        if not w.wall_id.endswith("X"):
            w.wall_id += "X"

    print(f"\n  --- Filter ---")
    print(f"    Renco walls:  {len(renco_walls)}")
    print(f"    Excluded:     {len(excluded_walls)}")
    if excluded_renco:
        print(f"    Excluded Renco (curved/irregular): {len(excluded_renco)}")
        for w in excluded_renco:
            print(f"      {w.wall_id:12s}  {w.exclude_reason}")

    flagged = [w for w in renco_walls if w.flags]
    clean = [w for w in renco_walls if not w.flags]
    print(f"    Flagged (X):  {len(flagged)}")
    print(f"    Clean:        {len(clean)}")
    if flagged:
        print(f"\n  --- X Suffix Details ---")
        for w in flagged:
            print(f"    {w.wall_id:12s}  {'; '.join(w.flags)}")

    # 4. Calculate blocks per wall
    from renco.calculator import calculate_wall
    results = [calculate_wall(w, catalog) for w in renco_walls]

    # 5. Aggregate
    from renco.aggregator import aggregate
    totals = aggregate(results, catalog, project_name, excluded_count=len(excluded_renco))

    print(f"\n  --- Block Totals ---")
    for bid in sorted(totals.blocks_by_type.keys()):
        cnt = totals.blocks_by_type[bid]
        b = catalog.get(bid)
        print(f"    {bid:8s} x {cnt:5d}  ({b['weight_lbs']} lbs/ea = {cnt * b['weight_lbs']:,.1f} lbs)")
    print(f"    {'TOTAL':8s}   {totals.total_blocks:5d}  ({totals.total_weight_lbs:,.1f} lbs)")

    # 6. Packing
    from renco.packing import calculate_packing
    pallet_height = settings.get("pallet", {}).get("loaded_height_in", 48)
    packing = calculate_packing(totals, catalog, str(CFG / "containers.json"),
                                loaded_pallet_height=pallet_height, settings=settings)

    print(f"\n  --- Shipping ---")
    print(f"    Recommended: {packing.recommended.label}")
    print(f"    {packing.total_pallets} pallets  |  {packing.utilization_percent}% utilization")

    # Consumables
    cons = packing.consumables
    print(f"\n  --- Consumables ---")
    est = " (estimated)" if not cons.adhesive_confirmed else ""
    print(f"    Adhesive: {cons.adhesive_cartridges} cartridges ({cons.total_joint_linear_ft:.0f} LF joints / {cons.adhesive_per_cartridge_ft:.0f} LF/cart){est}")
    print(f"    Mallets:  {cons.mallets} (1 per 20 glue guns)")

    # Pallet specs per block type
    print(f"\n  --- Pallet Optimization ---")
    for bid, spec in sorted(packing.pallet_specs.items()):
        print(f"    {bid:8s}  {spec.blocks_per_pallet} blocks/pallet ({spec.blocks_per_layer}/layer x {spec.layers_per_pallet} layers, {spec.pallet_height_in:.0f}in tall)")

    # 7. Write Excel
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    prefix = settings["output"]["excel_filename_prefix"]
    excel_dir = Path(paths.get("excel_output", "")) if paths.get("excel_output") else BASE
    excel_path = str(excel_dir / f"{prefix}_{ts}.xlsx")

    from renco.output.excel_writer import write_excel
    write_excel(totals, results, packing, catalog, excel_path)

    # 8. Write JSON
    json_prefix = settings["output"]["json_filename_prefix"]
    json_path = str(BASE / f"{json_prefix}_{ts}.json")

    from renco.output.json_writer import write_json
    # Use MCP start time if available (covers fetch + compute + deploy)
    mcp_start_file = BASE / "_mcp_start_time"
    if mcp_start_file.exists():
        try:
            mcp_start = float(mcp_start_file.read_text().strip())
        except ValueError:
            mcp_start = t0
    else:
        mcp_start = t0
    elapsed_total = time.time() - mcp_start
    write_json(totals, results, packing, catalog, excluded_walls, json_path,
               pipeline_duration_sec=elapsed_total)

    # 9. Write MCP writeback entries
    from renco.mcp_bridge import build_writeback_entries, P_ELEMENT_ID
    eid_guid = wb_cfg.get("element_id_guid", P_ELEMENT_ID)
    entries = build_writeback_entries(
        renco_walls, excluded_renco, eid_guid, report_guid, renco_report_value
    )
    with open(MCP_OUTPUT, "w") as f:
        json.dump({"entries": entries, "count": len(entries)}, f, indent=2)
    print(f"\n  MCP writeback: {len(entries)} entries written to {MCP_OUTPUT.name}")

    # 10. Auto-deploy to website
    _deploy_to_website(json_path, project_name, paths)

    slug = _project_slug(project_name)
    elapsed = time.time() - t0
    print(f"\n  Excel: {excel_path}")
    print(f"  JSON:  {json_path}")
    print(f"  Time:  {elapsed:.1f}s")
    print("\n" + "=" * 60)
    print(f"\n[OK] Renco Report complete -- Click here to see the Report: __https://sprtic1.github.io/renco-calc/{slug}/__\n")
    print("=" * 60)


def _project_slug(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def _deploy_to_website(json_path: str, project_name: str, paths: dict):
    import shutil, subprocess
    website_repo = Path(paths.get("website_repo", ""))
    if not website_repo or not website_repo.exists():
        logger.warning("Website repo not found at %s -- skipping deploy", website_repo)
        return
    slug = _project_slug(project_name)
    proj_dir = website_repo / slug
    data_dir = proj_dir / "data"
    assets_dir = proj_dir / "assets"
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(exist_ok=True)
    dest = data_dir / "renco_data.json"
    shutil.copy2(json_path, dest)
    print(f"\n  Website: copied JSON to {slug}/data/renco_data.json")
    render_dir = Path(paths.get("project_renders", ""))
    if render_dir.exists():
        render_files = sorted(render_dir.glob("RENDER*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not render_files:
            render_files = sorted(render_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
        if render_files:
            shutil.copy2(render_files[0], assets_dir / "model.png")
            print(f"  Website: copied project image ({render_files[0].name})")
    root_assets = website_repo / "assets"
    for logo in ["Renco Logo.png", "BIM6x Logo.png"]:
        src = root_assets / logo
        if src.exists():
            shutil.copy2(src, assets_dir / logo.replace(" ", "_"))
    registry_path = website_repo / "projects.json"
    try:
        with open(registry_path) as f: projects = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): projects = []
    with open(json_path) as f: jdata = json.load(f)
    entry = {
        "name": project_name, "slug": slug,
        "run_date": jdata["project"]["run_date"],
        "total_walls": jdata["project"]["total_walls"],
        "total_blocks": jdata["summary"]["total_blocks"],
        "total_weight_lbs": jdata["summary"]["total_weight_lbs"],
        "containers": jdata["summary"]["containers_required"],
        "container_recommendation": jdata["summary"].get("container_recommendation", ""),
    }
    found = False
    for i, p in enumerate(projects):
        if p.get("slug") == slug: projects[i] = entry; found = True; break
    if not found: projects.append(entry)
    with open(registry_path, "w") as f: json.dump(projects, f, indent=2)
    print(f"  Website: updated projects.json ({len(projects)} projects)")
    try:
        subprocess.run(["git", "add", "."], cwd=website_repo, check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=website_repo, capture_output=True)
        if result.returncode != 0:
            msg = f"Update {project_name}"
            subprocess.run(["git", "commit", "-m", msg], cwd=website_repo, check=True, capture_output=True)
            subprocess.run(["git", "push"], cwd=website_repo, check=True, capture_output=True)
            print("  Website: committed and pushed to GitHub Pages")
        else:
            print("  Website: no changes to push")
    except subprocess.CalledProcessError as e:
        logger.warning("Website git push failed: %s", e.stderr.decode() if e.stderr else e)


if __name__ == "__main__":
    run()
