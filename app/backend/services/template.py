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


def copy_template(project_folder):
    """Copy the EBIF Master Template template into the project folder.

    The template source is defined in settings.json as a relative path
    under dropbox_root. The copy goes to:
        {project_folder}/EBIF/EXCEL/MASTER/EBIF Master Template.xlsm

    Creates subfolders if they don't exist.
    Returns the destination file path on success, or raises an error.
    """
    settings = load_settings()
    dropbox_root = settings['dropbox_root']
    template_source = settings['template_source']

    source = os.path.join(dropbox_root, template_source)
    if not os.path.exists(source):
        raise FileNotFoundError(f"Template not found: {source}")

    dest_dir = os.path.join(project_folder, 'EBIF', 'EXCEL', 'MASTER')
    os.makedirs(dest_dir, exist_ok=True)

    dest = os.path.join(dest_dir, 'EBIF Master Template.xlsm')

    if os.path.exists(dest):
        return dest  # preserve existing file — never overwrite

    shutil.copy2(source, dest)
    return dest
