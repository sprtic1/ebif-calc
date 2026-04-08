import json
import os
import shutil


def _load_settings():
    settings_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
    )
    with open(settings_path, 'r') as f:
        return json.load(f)


def copy_template(project_number, project_name):
    """Copy the EID master schedule template to the project's Dropbox folder.

    Reads templates_folder and projects_folder from app/settings.json.
    Names the copy EID-{ProjectNumber}-{ProjectName}.xlsm.

    Returns the destination file path on success, or raises an error.
    """
    settings = _load_settings()
    templates_folder = settings['paths']['templates_folder']
    projects_folder = settings['paths']['projects_folder']
    template_filename = settings['project']['default_template']

    source = os.path.join(templates_folder, template_filename)
    if not os.path.exists(source):
        raise FileNotFoundError(f"Template not found: {source}")

    safe_name = project_name.replace(' ', '-').replace('/', '-').replace('\\', '-')
    dest_filename = f"EID-{project_number}-{safe_name}.xlsm"

    project_dir = os.path.join(projects_folder, f"{project_number}-{safe_name}")
    os.makedirs(project_dir, exist_ok=True)

    dest = os.path.join(project_dir, dest_filename)
    shutil.copy2(source, dest)
    return dest
