"""Archicad sync routes — preview counts and full refresh via Tapir API."""

from datetime import datetime

from flask import Blueprint, jsonify

archicad_bp = Blueprint('archicad', __name__)


def _get_helpers():
    """Import app-level helpers lazily to avoid circular imports."""
    from app import load_projects, save_projects
    return load_projects, save_projects


@archicad_bp.route('/api/projects/<project_id>/preview', methods=['GET'])
def preview_archicad(project_id):
    """Connect to Archicad via Tapir and return element counts per category."""
    load_projects, _ = _get_helpers()
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

    # Map counts to the 16 dashboard categories (1:1 with schedules.json IDs)
    dashboard_counts = {k: 0 for k in project.get('schedules', {}).keys()}
    for sched in result.get('schedules', []):
        sid = sched['id']
        if sid in dashboard_counts:
            dashboard_counts[sid] = sched['count']

    return jsonify({
        'counts': dashboard_counts,
        'detail': result.get('schedules', []),
        'total': result.get('total', 0),
    })


@archicad_bp.route('/api/projects/<project_id>/refresh', methods=['POST'])
def refresh_archicad(project_id):
    """Full Archicad pull — extract data, write to Excel, update project."""
    load_projects, save_projects = _get_helpers()
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

    # Update project counts and timestamp (1:1 mapping)
    dashboard_counts = {k: 0 for k in project.get('schedules', {}).keys()}
    for sid, count in result.get('counts', {}).items():
        if sid in dashboard_counts:
            dashboard_counts[sid] = count

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
