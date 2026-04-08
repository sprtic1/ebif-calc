import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from services.projects import get_all_projects, get_project_by_id, create_project
from services.template import copy_template

app = Flask(__name__, static_folder=None)
CORS(app)

# --- API Routes ---

@app.route('/api/projects', methods=['GET'])
def list_projects():
    projects = get_all_projects()
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def new_project():
    data = request.get_json()

    required = ['project_name', 'client_name', 'folder_location']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f"Missing fields: {', '.join(missing)}"}), 400

    project = create_project(data)

    # Attempt to copy the EID master schedule template
    template_path = None
    template_error = None
    try:
        template_path = copy_template(data['folder_location'])
    except Exception as e:
        template_error = str(e)

    return jsonify({
        'project': project,
        'template_path': template_path,
        'template_error': template_error,
    }), 201


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    project = get_project_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project)


# --- Serve React static build in production ---

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    dist = os.path.normpath(FRONTEND_DIST)
    if path and os.path.exists(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    index = os.path.join(dist, 'index.html')
    if os.path.exists(index):
        return send_from_directory(dist, 'index.html')
    return jsonify({'message': 'EID Project Manager API is running. Build the frontend to serve the UI.'}), 200


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=True)
