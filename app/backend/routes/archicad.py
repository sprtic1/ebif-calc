"""Archicad sync routes — instance discovery, preview counts, and full refresh."""

import json as _json
from datetime import datetime

from flask import Blueprint, jsonify, request, Response

archicad_bp = Blueprint('archicad', __name__)


def _get_helpers():
    """Import app-level helpers lazily to avoid circular imports."""
    from app import load_projects, save_projects
    return load_projects, save_projects


@archicad_bp.route('/api/archicad/instances', methods=['GET'])
def list_instances():
    """Scan ports 19724-19734 for running Archicad instances."""
    try:
        from services.tapir import scan_instances
        instances = scan_instances()
    except Exception as e:
        return jsonify({'error': f'Scan failed: {e}'}), 500

    if not instances:
        return jsonify({
            'instances': [],
            'error': "Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!",
        })

    return jsonify({'instances': instances})


@archicad_bp.route('/api/projects/<project_id>/preview', methods=['GET'])
def preview_archicad(project_id):
    """Connect to Archicad via Tapir and return element counts per category."""
    load_projects, _ = _get_helpers()
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    port = request.args.get('port', type=int)

    try:
        from services.tapir import preview_counts
        result = preview_counts(port=port)
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
    """Full Archicad pull — extract data, write to Excel, update project.

    Streams progress as newline-delimited JSON. Each line is either:
      {"progress": {"step": 3, "total": 16, "category": "Countertops"}}
    or the final result:
      {"result": {...}}
    """
    load_projects, save_projects = _get_helpers()
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    folder = project.get('folder_location', '')
    if not folder:
        return jsonify({'error': 'Project has no folder location set'}), 400

    data = request.get_json(silent=True) or {}
    port = data.get('port') or request.args.get('port', type=int)

    def generate():
        import threading
        import time

        progress_events = []

        def _extract_progress(step, total, category_name, items_so_far, items_total):
            progress_events.append({
                'progress': {
                    'phase': 'extracting', 'step': step, 'total': total,
                    'category': category_name,
                    'items_so_far': items_so_far,
                    'items_total': items_total,
                }
            })

        # Extract from Archicad in a thread so we can stream progress
        extract_result = [None]
        extract_error = [None]

        def _do_extract():
            try:
                from services.tapir import full_extract
                extract_result[0] = full_extract(port=port, on_progress=_extract_progress)
            except ConnectionError as e:
                extract_error[0] = str(e)
            except Exception as e:
                extract_error[0] = f'Archicad extraction failed: {e}'

        t = threading.Thread(target=_do_extract)
        t.start()

        last_sent = 0
        while t.is_alive():
            while last_sent < len(progress_events):
                yield _json.dumps(progress_events[last_sent]) + '\n'
                last_sent += 1
            time.sleep(0.1)
        while last_sent < len(progress_events):
            yield _json.dumps(progress_events[last_sent]) + '\n'
            last_sent += 1

        if extract_error[0]:
            yield _json.dumps({'error': extract_error[0]}) + '\n'
            return

        result = extract_result[0]

        # Write to Excel in a thread, streaming progress
        write_error = [None]

        def _write_progress(step, total, category_name, items_so_far, items_total):
            progress_events.append({
                'progress': {
                    'phase': 'writing', 'step': step, 'total': total,
                    'category': category_name,
                    'items_so_far': items_so_far,
                    'items_total': items_total,
                }
            })

        def _do_write():
            try:
                from services.excel_writer import write_to_master
                write_to_master(
                    folder, result['schedules'], result['schedule_defs'],
                    on_progress=_write_progress,
                )
            except FileNotFoundError as e:
                write_error[0] = str(e)
            except Exception as e:
                write_error[0] = f'Excel write failed: {e}'

        t = threading.Thread(target=_do_write)
        t.start()

        while t.is_alive():
            while last_sent < len(progress_events):
                yield _json.dumps(progress_events[last_sent]) + '\n'
                last_sent += 1
            time.sleep(0.1)
        while last_sent < len(progress_events):
            yield _json.dumps(progress_events[last_sent]) + '\n'
            last_sent += 1

        # Update project counts and timestamp
        dashboard_counts = {k: 0 for k in project.get('schedules', {}).keys()}
        for sid, count in result.get('counts', {}).items():
            if sid in dashboard_counts:
                dashboard_counts[sid] = count

        project['schedules'] = dashboard_counts
        project['last_synced'] = datetime.utcnow().isoformat() + 'Z'
        save_projects(projects)

        response = {
            'result': {
                'project': project,
                'total': result.get('total', 0),
            }
        }
        if write_error[0]:
            response['result']['excel_error'] = write_error[0]

        yield _json.dumps(response) + '\n'

    return Response(generate(), mimetype='application/x-ndjson')
