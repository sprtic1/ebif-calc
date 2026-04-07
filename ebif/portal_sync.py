"""Portal Sync — auto-registers client portals on the EID App Platform.

After every EBIF Report run, this module SSHes into the server and
updates the client portal's projects.json with the current project data.
This creates/updates both the client portal page and the launcher card.
"""

import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SERVER = "root@209.38.130.201"
PORTAL_JSON = "/opt/eid-apps/client-portal/data/projects.json"


def _derive_client_slug(project_name: str) -> str:
    """Derive client portal slug from Archicad project name.

    'McCollum - 408 Cayuse Court 29' -> 'mccollum'
    'Goulet - 13 Chateau Circle 29' -> 'goulet'
    """
    parts = project_name.split("-")
    slug = parts[0].strip().lower()
    slug = slug.rstrip("0123456789 ")
    return slug.replace(" ", "-") if " " in slug else slug


def _derive_display_name(project_name: str) -> tuple[str, str, str]:
    """Derive display name, address, and full title from project name.

    Returns (name, address, full_title).
    """
    parts = [p.strip() for p in project_name.split("-")]
    if len(parts) >= 2:
        client = parts[0].strip()
        addr_parts = parts[1:-1] if len(parts) > 2 and parts[-1].strip().isdigit() else parts[1:]
        address = " - ".join(addr_parts).strip()
        address = re.sub(r"\s+\d+$", "", address).strip()
        name = f"{client} Residence"
        full_title = f"{name} - {address}"
        return name, address, full_title
    return project_name, "", project_name


def sync_portal(
    project_name: str,
    dropbox_folder: str,
    active_schedules: int,
    schedule_names: list[str],
) -> bool:
    """Update the client portal on the server with this project's data.

    Creates or updates the project entry in the server's projects.json.
    The launcher reads from the same file, so both update automatically.

    Returns True on success.
    """
    slug = _derive_client_slug(project_name)
    name, address, full_title = _derive_display_name(project_name)

    if not dropbox_folder:
        logger.warning("No Dropbox folder for '%s' -- skipping portal sync", project_name)
        return False

    logger.info("Syncing portal for '%s' (slug: %s, %d schedules)", name, slug, active_schedules)

    # Build the project entry as JSON
    entry = {
        "name": name,
        "address": address,
        "full_title": full_title,
        "dropbox_folder": dropbox_folder,
        "exclude_categories": ["Covering Calculations", "Summary"],
        "active_schedules": active_schedules,
    }
    entry_json = json.dumps(entry)

    # Write a temp Python script, upload it, run it, delete it
    script = f'''import json
path = "{PORTAL_JSON}"
try:
    data = json.load(open(path))
except:
    data = {{"projects": {{}}}}
projects = data.setdefault("projects", {{}})
slug = "{slug}"
existing = projects.get(slug, {{}})
entry = json.loads('{entry_json}')
entry["timeline"] = existing.get("timeline", [
    {{"phase": "Design Development", "date": "", "status": "in_progress"}},
    {{"phase": "Selections Due", "date": "", "status": "upcoming"}},
    {{"phase": "Ordering", "date": "", "status": "upcoming"}},
    {{"phase": "Delivery & Receiving", "date": "", "status": "upcoming"}},
    {{"phase": "Installation", "date": "", "status": "upcoming"}}
])
entry["budget"] = existing.get("budget", {{}})
projects[slug] = entry
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print("OK " + slug + " " + str(entry["active_schedules"]) + " schedules")
'''

    try:
        # Write script to temp file, scp it, run it, clean up
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(script)
            tmp_path = tmp.name

        subprocess.run(["scp", tmp_path, f"{SERVER}:/tmp/_portal_sync.py"],
                       capture_output=True, timeout=10)
        result = subprocess.run(
            ["ssh", SERVER, "python3 /tmp/_portal_sync.py && rm -f /tmp/_portal_sync.py"],
            capture_output=True, text=True, timeout=15,
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode == 0 and "OK" in result.stdout:
            logger.info("Portal synced: %s", result.stdout.strip())
            return True
        else:
            logger.error("Portal sync failed: %s %s", result.stdout.strip(), result.stderr.strip())
            return False
    except subprocess.TimeoutExpired:
        logger.error("Portal sync timed out")
        return False
    except FileNotFoundError:
        logger.warning("SSH not available -- skipping portal sync")
        return False
