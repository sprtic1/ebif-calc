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


def copy_template(project_name, project_number):
    """Copy the TEMPLATE .xlsm file to the project folder.

    Names it EID-{ProjectNumber}-{ProjectName}.xlsm
    Returns the destination path.
    """
    settings = load_settings()
    templates_folder = settings['templates_folder']
    projects_folder = settings['projects_folder']
    template_filename = settings.get('template_filename', 'TEMPLATE.xlsm')

    src = os.path.join(templates_folder, template_filename)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Template not found: {src}")

    safe_name = re.sub(r'[^\w\s-]', '', project_name).strip()
    dest_filename = f"EID-{project_number}-{safe_name}.xlsm"

    slug = slugify(project_name)
    project_dir = os.path.join(projects_folder, slug)
    os.makedirs(project_dir, exist_ok=True)

    dest = os.path.join(project_dir, dest_filename)
    shutil.copy2(src, dest)

    return dest
