"""Website Deployer — copies JSON to GitHub Pages repo and pushes.

Handles:
- Copying ebif_data.json to the project's data/ folder
- Updating projects.json registry
- Git commit + push
"""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """Convert project name to URL-friendly slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def deploy_website(
    json_data: dict,
    website_repo: Path,
    project_name: str,
) -> bool:
    """Deploy dashboard data to GitHub Pages.

    Returns True on success.
    """
    if not website_repo.exists():
        logger.warning("Website repo not found: %s", website_repo)
        logger.info("Skipping website deployment. Create the repo to enable.")
        return False

    slug = slugify(project_name)
    project_dir = website_repo / slug
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON data
    json_path = data_dir / "ebif_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Website: copied JSON to %s", json_path.relative_to(website_repo))

    # Update projects.json registry
    projects_file = website_repo / "projects.json"
    projects = []
    if projects_file.exists():
        try:
            projects = json.load(open(projects_file))
        except (json.JSONDecodeError, FileNotFoundError):
            projects = []

    # Upsert this project
    entry = {
        "slug": slug,
        "name": project_name,
        "last_updated": json_data.get("generated_at", ""),
        "total_elements": json_data.get("summary", {}).get("total_elements", 0),
        "active_schedules": json_data.get("summary", {}).get("active_schedules", 0),
    }
    existing = [p for p in projects if p.get("slug") != slug]
    existing.append(entry)
    with open(projects_file, "w") as f:
        json.dump(existing, f, indent=2)
    logger.info("Website: updated projects.json (%d projects)", len(existing))

    # Git commit + push
    try:
        subprocess.run(["git", "add", "-A"], cwd=str(website_repo), check=True,
                        capture_output=True, timeout=30)
        msg = f"Update {project_name} — {json_data.get('summary', {}).get('total_elements', 0)} elements"
        subprocess.run(["git", "commit", "-m", msg], cwd=str(website_repo),
                        check=True, capture_output=True, timeout=30)
        subprocess.run(["git", "push"], cwd=str(website_repo),
                        check=True, capture_output=True, timeout=60)
        logger.info("Website: committed and pushed to GitHub Pages")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        if "nothing to commit" in stderr:
            logger.info("Website: no changes to commit")
            return True
        logger.error("Website git error: %s", stderr)
        return False
    except Exception as e:
        logger.error("Website deploy error: %s", e)
        return False
