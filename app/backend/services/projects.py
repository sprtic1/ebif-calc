import json
import os
import uuid
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'projects.json')


def _load_projects():
    path = os.path.normpath(DATA_FILE)
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return json.load(f)


def _save_projects(projects):
    path = os.path.normpath(DATA_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(projects, f, indent=2)


def get_all_projects():
    return _load_projects()


def get_project_by_id(project_id):
    projects = _load_projects()
    for p in projects:
        if p['id'] == project_id:
            return p
    return None


def create_project(data):
    projects = _load_projects()

    project = {
        'id': str(uuid.uuid4()),
        'project_name': data['project_name'],
        'client_name': data['client_name'],
        'address': data.get('address', ''),
        'folder_location': data['folder_location'],
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'last_synced': None,
        'categories': {
            'walls': 0,
            'floors': 0,
            'roofs': 0,
            'columns': 0,
            'beams': 0,
            'slabs': 0,
            'stairs': 0,
            'doors': 0,
            'windows': 0,
            'curtain_walls': 0,
            'railings': 0,
            'zones': 0,
            'meshes': 0,
            'shells': 0,
            'morphs': 0,
            'objects': 0,
        }
    }

    projects.append(project)
    _save_projects(projects)
    return project
