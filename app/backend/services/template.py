import json
import os
import shutil


def _load_settings():
    settings_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
    )
    with open(settings_path, 'r') as f:
        return json.load(f)


def copy_template(project_folder):
    """Copy the EID master schedule template into the project folder.

    The template source is defined in settings.json as a relative path
    under dropbox_root. The copy goes to:
        {project_folder}/EBIF/EXCEL/MASTER/EID Master Schedule.xlsm

    Returns the destination file path on success, or raises an error.
    """
    settings = _load_settings()
    dropbox_root = settings['dropbox_root']
    template_source = settings['template_source']
    excel_subpath = settings['excel_subpath']

    source = os.path.join(dropbox_root, template_source)
    if not os.path.exists(source):
        raise FileNotFoundError(f"Template not found: {source}")

    dest = os.path.join(project_folder, excel_subpath)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    shutil.copy2(source, dest)
    return dest
