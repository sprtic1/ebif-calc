"""Cloud sync routes — receive and serve dashboard data on DigitalOcean."""

import json
import os

from flask import Blueprint, jsonify, request

cloud_bp = Blueprint('cloud', __name__)

SYNC_DATA_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'dashboard_sync.json')
)


def _get_sync_token():
    """Read sync_token from settings.json or environment variable."""
    # Environment variable takes precedence (for DigitalOcean deployment)
    token = os.environ.get('EID_SYNC_TOKEN', '')
    if token:
        return token
    try:
        settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
        with open(os.path.normpath(settings_path), 'r') as f:
            return json.load(f).get('sync_token', '')
    except Exception:
        return ''


def _check_auth():
    """Validate the Authorization header. Returns error response or None."""
    token = _get_sync_token()
    if not token:
        return jsonify({'error': 'Sync not configured'}), 500

    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer ') or auth[7:] != token:
        return jsonify({'error': 'Unauthorized'}), 401

    return None


@cloud_bp.route('/api/sync', methods=['POST'])
def receive_sync():
    """Receive dashboard data from local app and save to disk."""
    auth_error = _check_auth()
    if auth_error:
        return auth_error

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    # Save to flat file
    os.makedirs(os.path.dirname(SYNC_DATA_FILE), exist_ok=True)
    with open(SYNC_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return jsonify({'status': 'ok', 'synced_at': data.get('synced_at', '')}), 200


@cloud_bp.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Return the most recent synced dashboard data."""
    auth_error = _check_auth()
    if auth_error:
        return auth_error

    if not os.path.exists(SYNC_DATA_FILE):
        return jsonify({'error': 'No data synced yet'}), 404

    with open(SYNC_DATA_FILE, 'r') as f:
        data = json.load(f)

    return jsonify(data)
