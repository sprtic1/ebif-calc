"""Tear sheet routes — publish from Archicad, scan highlights, write to Excel."""

import json as _json
import os

from flask import Blueprint, jsonify, request, Response

tearsheets_bp = Blueprint('tearsheets', __name__)


def _get_helpers():
    """Import app-level helpers lazily to avoid circular imports."""
    from app import load_projects, save_projects
    return load_projects, save_projects


@tearsheets_bp.route('/api/projects/<project_id>/scan-tearsheets', methods=['POST'])
def scan_tearsheets_route(project_id):
    """Combined: publish tear sheets from Archicad, then scan and write to Excel.

    Streams NDJSON progress:
      {"progress": {"phase": "publishing"}}
      {"progress": {"phase": "scanning", "step": 3, "total": 15, "pdf": "P1_01.pdf"}}
      {"result": {...summary...}}
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
    port = data.get('port') or project.get('last_tapir_port')

    def generate():
        import threading
        import time

        progress_events = []

        # Phase 1: Publish tear sheets from Archicad
        progress_events.append({
            'progress': {'phase': 'publishing', 'step': 0, 'total': 0, 'pdf': 'Publishing from Archicad...'}
        })

        publish_error = [None]

        def _do_publish():
            try:
                from services.tearsheet_scanner import publish_tearsheets
                if not port:
                    publish_error[0] = "No Tapir port available. Run 'Refresh from Archicad' first."
                    return
                publish_tearsheets(port, folder)
            except Exception as e:
                publish_error[0] = f"Publish failed: {e}"

        t = threading.Thread(target=_do_publish)
        t.start()

        last_sent = 0
        while t.is_alive():
            while last_sent < len(progress_events):
                yield _json.dumps(progress_events[last_sent]) + '\n'
                last_sent += 1
            time.sleep(0.2)
        while last_sent < len(progress_events):
            yield _json.dumps(progress_events[last_sent]) + '\n'
            last_sent += 1

        if publish_error[0]:
            yield _json.dumps({'error': publish_error[0]}) + '\n'
            return

        # Brief pause to let filesystem sync
        time.sleep(1)

        # Phase 2: Scan PDFs and write to Excel
        from services.template import get_excel_path
        excel_path = get_excel_path(project)

        scan_result = [None]
        scan_error = [None]

        def _scan_progress(step, total, pdf_name):
            progress_events.append({
                'progress': {'phase': 'scanning', 'step': step, 'total': total, 'pdf': pdf_name}
            })

        def _do_scan():
            try:
                from services.tearsheet_scanner import scan_tearsheets
                scan_result[0] = scan_tearsheets(folder, excel_path, on_progress=_scan_progress)
            except Exception as e:
                scan_error[0] = f"Scan failed: {e}"

        t = threading.Thread(target=_do_scan)
        t.start()

        while t.is_alive():
            while last_sent < len(progress_events):
                yield _json.dumps(progress_events[last_sent]) + '\n'
                last_sent += 1
            time.sleep(0.1)
        while last_sent < len(progress_events):
            yield _json.dumps(progress_events[last_sent]) + '\n'
            last_sent += 1

        if scan_error[0]:
            yield _json.dumps({'error': scan_error[0]}) + '\n'
            return

        result = scan_result[0]
        yield _json.dumps({'result': result}) + '\n'

    return Response(generate(), mimetype='application/x-ndjson')


@tearsheets_bp.route('/api/projects/<project_id>/tearsheet-status', methods=['GET'])
def tearsheet_status(project_id):
    """Return list of PDFs in the FROM ARCHICAD folder."""
    load_projects, _ = _get_helpers()
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    folder = project.get('folder_location', '')
    from_archicad = os.path.join(folder, 'EBIF', 'EXCEL', 'MASTER', 'FROM ARCHICAD')

    if not os.path.exists(from_archicad):
        return jsonify({'pdfs': [], 'folder_exists': False})

    pdfs = sorted([f for f in os.listdir(from_archicad) if f.lower().endswith('.pdf')])
    return jsonify({'pdfs': pdfs, 'folder_exists': True, 'count': len(pdfs)})
