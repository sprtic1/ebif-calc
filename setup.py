"""RENCO Block Calculator — First-use setup.

Run this once on a new machine to configure all paths and settings.
After first run, this script is never needed again — all config
is stored in config/settings.json.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "settings.json"


def main():
    print("=" * 60)
    print("  RENCO Block Calculator — First-Use Setup")
    print("=" * 60)
    print()
    print("  This will configure your local environment.")
    print("  Press Enter to accept the default value shown in [brackets].")
    print()

    # Load existing settings as defaults
    defaults = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            defaults = json.load(f)

    # Question 1: Dropbox folder
    current_renders = defaults.get("paths", {}).get("project_renders", "")
    dropbox = input(f"  1. Full path to your project renders folder\n     [{current_renders}]: ").strip()
    if not dropbox:
        dropbox = current_renders

    # Question 2: GitHub repo
    current_repo = defaults.get("paths", {}).get("website_repo", "")
    repo = input(f"\n  2. Full path to the GitHub Pages website repo folder\n     [{current_repo}]: ").strip()
    if not repo:
        repo = current_repo

    # Question 3: ArchiCAD port
    current_port = defaults.get("archicad", {}).get("port", 19723)
    port_str = input(f"\n  3. ArchiCAD port number\n     [{current_port}]: ").strip()
    port = int(port_str) if port_str else current_port

    # Question 4: Project name
    current_name = defaults.get("project", {}).get("name", "Untitled Project")
    name = input(f"\n  4. Project name\n     [{current_name}]: ").strip()
    if not name:
        name = current_name

    # Question 5: Excel output folder
    current_excel = defaults.get("paths", {}).get("excel_output", "")
    excel_hint = current_excel or "(same as project folder)"
    excel = input(f"\n  5. Where to save Excel output files\n     [{excel_hint}]: ").strip()
    if not excel:
        excel = current_excel

    # Build settings
    settings = {
        "archicad": {
            "host": "localhost",
            "port": port,
            "timeout_seconds": 15,
        },
        "filter": defaults.get("filter", {
            "composite_name_contains": "renco",
            "case_sensitive": False,
        }),
        "calculation": defaults.get("calculation", {
            "bond_pattern": "running",
            "waste_factor_percent": 0,
            "modular_tolerance_inches": 0.1,
        }),
        "archicad_writeback": {
            "enabled": True,
            "property_group": defaults.get("archicad_writeback", {}).get("property_group", "EID GENERAL PROPERTIES"),
            "property_name": defaults.get("archicad_writeback", {}).get("property_name", "RENCO REPORT"),
            "element_id_guid": defaults.get("archicad_writeback", {}).get("element_id_guid", "7e221f33-829b-4fbc-a670-e74dabce6289"),
            "clear_on_run": True,
        },
        "paths": {
            "website_repo": repo,
            "project_renders": dropbox,
            "excel_output": excel,
        },
        "project": {
            "name": name,
        },
        "output": defaults.get("output", {
            "excel_filename_prefix": "renco_schedule",
            "json_filename_prefix": "renco_data",
            "include_excluded_sheet": False,
        }),
    }

    # Write
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"\n  Settings saved to {CONFIG_PATH}")
    print(f"\n  ArchiCAD port:    {port}")
    print(f"  Project name:     {name}")
    print(f"  Renders folder:   {dropbox}")
    print(f"  Website repo:     {repo}")
    print(f"  Excel output:     {excel or '(project folder)'}")
    print(f"\n  Setup complete. Run 'python main.py' to start the pipeline.")
    print("=" * 60)


if __name__ == "__main__":
    main()
