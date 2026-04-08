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
            'cabinets': 0,
            'countertops': 0,
            'doors': 0,
            'electrical': 0,
            'flooring': 0,
            'furniture': 0,
            'hardware': 0,
            'lighting': 0,
            'mirrors': 0,
            'plumbing': 0,
            'specialty': 0,
            'tile': 0,
            'windows': 0,
            'accessories': 0,
            'zones': 0,
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


# ---------- Archicad Sync Routes ----------

# Mapping from schedules.json IDs to the 16 dashboard category keys
SCHEDULE_ID_MAP = {
    'appliances': 'appliances',
    'cabinetry_hardware': 'cabinets',
    'cabinetry_inserts': 'cabinets',
    'cabinetry_style': 'cabinets',
    'countertops': 'countertops',
    'doors': 'doors',
    'lighting_electrical': 'electrical',
    'flooring': 'flooring',
    'furniture': 'furniture',
    'door_hardware': 'hardware',
    'decorative_lighting': 'lighting',
    'shower_glass_mirrors': 'mirrors',
    'plumbing': 'plumbing',
    'specialty_equipment': 'specialty',
    'tile': 'tile',
    'windows': 'windows',
    'bath_accessories': 'accessories',
    'surface_finishes': 'zones',
    'covering_calc': 'zones',
}


@app.route('/api/projects/<project_id>/preview', methods=['GET'])
def preview_archicad(project_id):
    """Connect to Archicad via Tapir and return element counts per category."""
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        from services.tapir import preview_counts
        result = preview_counts()
    except ConnectionError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Archicad sync failed: {e}'}), 500

    # Aggregate counts into the 16 dashboard categories
    dashboard_counts = {k: 0 for k in project.get('schedules', {}).keys()}
    for sched in result.get('schedules', []):
        sid = sched['id']
        dashboard_key = SCHEDULE_ID_MAP.get(sid)
        if dashboard_key and dashboard_key in dashboard_counts:
            dashboard_counts[dashboard_key] += sched['count']

    return jsonify({
        'counts': dashboard_counts,
        'detail': result.get('schedules', []),
        'total': result.get('total', 0),
    })


@app.route('/api/projects/<project_id>/refresh', methods=['POST'])
def refresh_archicad(project_id):
    """Full Archicad pull — extract data, write to Excel, update project."""
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    folder = project.get('folder_location', '')
    if not folder:
        return jsonify({'error': 'Project has no folder location set'}), 400

    try:
        from services.tapir import full_extract
        result = full_extract()
    except ConnectionError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Archicad extraction failed: {e}'}), 500

    # Write to Excel
    excel_error = None
    try:
        from services.excel_writer import write_to_master
        write_to_master(folder, result['schedules'], result['schedule_defs'])
    except FileNotFoundError as e:
        excel_error = str(e)
    except Exception as e:
        excel_error = f'Excel write failed: {e}'

    # Update project counts and timestamp
    dashboard_counts = {k: 0 for k in project.get('schedules', {}).keys()}
    for sid, count in result.get('counts', {}).items():
        dashboard_key = SCHEDULE_ID_MAP.get(sid)
        if dashboard_key and dashboard_key in dashboard_counts:
            dashboard_counts[dashboard_key] += count

    project['schedules'] = dashboard_counts
    project['last_synced'] = datetime.utcnow().isoformat() + 'Z'
    save_projects(projects)

    response = {
        'project': project,
        'total': result.get('total', 0),
    }
    if excel_error:
        response['excel_error'] = excel_error

    return jsonify(response)


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
