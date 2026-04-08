import json
import os
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from services.template import copy_template, slugify
from routes.archicad import archicad_bp

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='/')
CORS(app)
app.register_blueprint(archicad_bp)

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

@app.route('/api/browse-folder', methods=['GET'])
def browse_folder():
    """Open a native Windows folder picker dialog and return the selected path."""
    import threading

    result = {'path': ''}

    def _pick():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title='Select Project Folder')
        root.destroy()
        result['path'] = folder or ''

    # tkinter must run on its own thread when called from Flask
    t = threading.Thread(target=_pick)
    t.start()
    t.join(timeout=120)

    if not result['path']:
        return jsonify({'path': '', 'cancelled': True})
    return jsonify({'path': result['path'], 'cancelled': False})

@app.route('/api/projects', methods=['GET'])
def get_projects():
    projects = load_projects()
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    folder_location = data.get('folder_location', '').strip()
    project_name = data.get('project_name', '').strip()
    client_name = data.get('client_name', '').strip()
    address = data.get('address', '').strip()

    if not project_name or not folder_location:
        return jsonify({'error': 'Folder location and project name are required'}), 400

    project_id = str(uuid.uuid4())[:8]
    slug = slugify(project_name)

    project = {
        'id': project_id,
        'slug': slug,
        'project_name': project_name,
        'client_name': client_name,
        'address': address,
        'folder_location': folder_location,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'last_synced': None,
        'schedules': {
            'appliances': 0,
            'bath_accessories': 0,
            'cabinetry_hardware': 0,
            'cabinetry_inserts': 0,
            'cabinetry_style': 0,
            'countertops': 0,
            'decorative_lighting': 0,
            'door_hardware': 0,
            'flooring': 0,
            'furniture': 0,
            'lighting_electrical': 0,
            'plumbing': 0,
            'shower_glass_mirrors': 0,
            'specialty_equipment': 0,
            'surface_finishes': 0,
            'tile': 0,
        },
    }

    # Copy template file (non-fatal if template paths not configured)
    try:
        template_path = copy_template(folder_location)
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
    return jsonify({'message': 'EID Project Manager API running. Build frontend with: cd app/frontend && npm run build'}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
