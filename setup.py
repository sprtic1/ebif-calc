"""EBIF-CALC First-Run Setup — asks 5 questions and writes settings.json."""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"


def main():
    print("=" * 60)
    print("  EBIF-CALC Setup")
    print("  Ellis Building Intelligence Framework")
    print("=" * 60)
    print()
    print("  Answer 5 questions to configure your machine.")
    print()

    dropbox = input("  1. Full path to your Dropbox folder:\n     > ").strip()
    github_info = input("  2. GitHub username/repo (e.g. sprtic1/ebif-calc):\n     > ").strip()
    port = input("  3. Archicad Tapir port number (e.g. 19723):\n     > ").strip()
    project = input("  4. Archicad project name:\n     > ").strip()
    output = input("  5. Excel output folder (blank = project/output/):\n     > ").strip()

    parts = github_info.split("/")
    github_user = parts[0] if parts else "sprtic1"
    github_repo = parts[1] if len(parts) > 1 else "ebif-calc"

    settings = {
        "archicad_port": int(port) if port.isdigit() else 19723,
        "dropbox_root": dropbox,
        "website_repo": str(Path(dropbox) / "SOFTWARE" / "CLAUDE" / "CLAUDE CODE" / "EBIF-WEBSITE" / "ebif-calc"),
        "output_folder": output,
        "github_user": github_user,
        "github_repo": github_repo,
        "project_name": project,
        "branding": {
            "header_color": "868C54",
            "alt_row_color": "C2C8A2",
            "accent_color": "737569",
            "heading_font": "Lato",
            "body_font": "Arial Narrow",
            "title_font": "Gowun Batang",
        },
    }

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    settings_path = CONFIG_DIR / "settings.json"
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    print()
    print(f"  Saved: {settings_path}")
    print()
    print("  Setup complete! Run: python main.py")
    print("  Or in Claude Code: Run the EID Report")
    print()


if __name__ == "__main__":
    main()
