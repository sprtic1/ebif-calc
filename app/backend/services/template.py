import json
import os
import shutil
import re


def load_settings():
    settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
    with open(os.path.abspath(settings_path), 'r') as f:
        return json.load(f)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text


def excel_filename(project_name):
    """Return the project-specific Excel filename.

    Format: "{ProjectName} EBIF SCHEDULES.xlsm"
    Example: "MCCOLLUM - 408 CAYUSE COURT EBIF SCHEDULES.xlsm"
    """
    return f"{project_name} EBIF SCHEDULES.xlsm"


def get_excel_path(project):
    """Return the full path to a project's Excel file.

    Uses the stored excel_filename if available, otherwise derives it
    from the project name.
    """
    folder = project.get('folder_location', '')
    fname = project.get('excel_filename', '')
    if not fname:
        fname = excel_filename(project.get('project_name', 'EBIF SCHEDULES'))
    return os.path.join(folder, 'EBIF', 'EXCEL', 'MASTER', fname)


def copy_template(project_folder, project_name):
    """Copy the EBIF template into the project folder.

    The template source is defined in settings.json as a relative path
    under dropbox_root. The copy is renamed to:
        {project_folder}/EBIF/EXCEL/MASTER/{ProjectName} EBIF SCHEDULES.xlsm

    Creates subfolders if they don't exist.
    Returns (destination_path, filename) on success, or raises an error.
    """
    settings = load_settings()
    dropbox_root = settings['dropbox_root']
    template_source = settings['template_source']

    source = os.path.join(dropbox_root, template_source)
    if not os.path.exists(source):
        raise FileNotFoundError(f"Template not found: {source}")

    dest_dir = os.path.join(project_folder, 'EBIF', 'EXCEL', 'MASTER')
    os.makedirs(dest_dir, exist_ok=True)

    fname = excel_filename(project_name)
    dest = os.path.join(dest_dir, fname)

    if os.path.exists(dest):
        return dest, fname  # preserve existing file — never overwrite

    shutil.copy2(source, dest)
    return dest, fname
