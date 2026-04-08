import json
import os
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from services.template import copy_template, slugify

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='/')
CORS(app)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PROJECTS_FILE = os.path.abspath(os.path.join(DATA_DIR, 'projects.json'))


def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, 'r') as f:
        return json.load(f)


def save_projects(projects):
    os.makedirs(os.path.dirname(PROJECTS_FILE), exist_ok=True)
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2)


# ---------- API Routes ----------

@app.route('/api/projects', methods=['GET'])
def get_projects():
    projects = load_projects()
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    client = data.get('client', '').strip()
    number = data.get('number', '').strip()
    dropbox_path = data.get('dropbox_path', '').strip()

    if not name or not number:
        return jsonify({'error': 'Project name and number are required'}), 400

    project_id = str(uuid.uuid4())[:8]
    slug = slugify(name)

    project = {
        'id': project_id,
        'slug': slug,
        'name': name,
        'client': client,
        'number': number,
        'dropbox_path': dropbox_path,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'last_synced': None,
        'schedules': {
            'appliances': 0,
            'bath_accessories': 0,
            'cabinetry_hardware': 0,
            'cabinetry_inserts': 0,
            'cabinetry_style_species': 0,
            'countertops': 0,
            'covering_calculations': 0,
            'decorative_lighting': 0,
            'door_hardware': 0,
            'doors': 0,
            'flooring': 0,
            'furniture': 0,
            'lighting_electrical': 0,
            'plumbing': 0,
            'shower_glass_mirrors': 0,
            'specialty_equipment': 0,
            'surface_finishes': 0,
            'tile': 0,
            'windows': 0,
        },
    }

    # Copy template file (non-fatal if template paths not configured)
    try:
        template_path = copy_template(name, number)
        project['template_path'] = template_path
    except Exception as e:
        project['template_path'] = None
        project['template_error'] = str(e)

    projects = load_projects()
    projects.append(project)
    save_projects(projects)

    return jsonify(project), 201


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project)


# ---------- Frontend (production) ----------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'))
    if path and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    index = os.path.join(dist_dir, 'index.html')
    if os.path.exists(index):
        return send_from_directory(dist_dir, 'index.html')
    return jsonify({'message': 'EID Project Hub API running. Build frontend with: cd app/frontend && npm run build'}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
