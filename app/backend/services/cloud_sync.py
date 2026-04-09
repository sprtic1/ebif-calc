"""Cloud Sync — pushes dashboard data to DigitalOcean after each Refresh.

Builds a lightweight JSON payload with project info, schedule counts,
summary metrics, and pull history. POSTs it to the cloud endpoint
with a bearer token for authentication.

Only dashboard data is synced — never the Excel file.
"""

import json
import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def _load_settings():
    settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
    with open(os.path.normpath(settings_path), 'r') as f:
        return json.load(f)


def build_dashboard_payload(project, schedule_details=None, summary=None):
    """Build the dashboard JSON payload for cloud sync.

    Args:
        project: Project dict from projects.json
        schedule_details: Optional enriched schedule data from read_excel_details
        summary: Optional summary metrics dict

    Returns:
        dict ready to POST to the cloud endpoint
    """
    schedules = project.get('schedules', {})

    if not summary:
        total = sum(schedules.values())
        summary = {
            'total': total,
            'complete': 0,
            'incomplete': total,
            'empty_schedules': sum(1 for v in schedules.values() if v == 0),
        }

    # Strip rows from schedule_details (too large for cloud sync)
    details_summary = {}
    if schedule_details:
        for sid, sd in schedule_details.items():
            details_summary[sid] = {
                'count': sd.get('count', 0),
                'complete': sd.get('complete', 0),
                'incomplete': sd.get('incomplete', 0),
            }

    return {
        'projects': [{
            'id': project.get('id', ''),
            'project_name': project.get('project_name', ''),
            'client_name': project.get('client_name', ''),
            'address': project.get('address', ''),
            'last_synced': project.get('last_synced', ''),
            'schedules': schedules,
            'schedule_details': details_summary or None,
            'summary': summary,
            'pull_history': project.get('pull_history', []),
        }],
        'synced_at': datetime.utcnow().isoformat() + 'Z',
    }


def push_to_cloud(payload):
    """POST dashboard data to the DigitalOcean cloud endpoint.

    Returns (success: bool, message: str).
    """
    settings = _load_settings()
    cloud_url = settings.get('cloud_url', '').rstrip('/')
    sync_token = settings.get('sync_token', '')

    if not cloud_url:
        return False, 'Cloud URL not configured in settings.json'
    if not sync_token:
        return False, 'Sync token not configured in settings.json'

    url = f"{cloud_url}/api/sync"

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {sync_token}'},
            timeout=30,
        )

        if resp.status_code == 200 or resp.status_code == 201:
            logger.info("Cloud sync successful: %s", url)
            return True, 'Cloud sync complete'
        else:
            msg = f"Cloud sync failed: HTTP {resp.status_code}"
            try:
                err = resp.json().get('error', msg)
                msg = f"Cloud sync failed: {err}"
            except Exception:
                pass
            logger.warning(msg)
            return False, msg

    except requests.exceptions.ConnectionError:
        msg = "Cloud sync failed: cannot reach server"
        logger.warning(msg)
        return False, msg
    except requests.exceptions.Timeout:
        msg = "Cloud sync failed: server timeout"
        logger.warning(msg)
        return False, msg
    except Exception as e:
        msg = f"Cloud sync failed: {e}"
        logger.warning(msg)
        return False, msg


def sync_after_refresh(project):
    """Convenience: build payload and push to cloud.

    Called automatically after each successful Archicad refresh.
    Non-fatal — errors are logged but don't block the refresh.

    Returns (success, message).
    """
    try:
        # Try to get enriched details
        schedule_details = None
        summary = None
        try:
            from services.excel_reader import read_excel_details
            schedule_details = read_excel_details(project)
            if schedule_details:
                total = sum(d['count'] for d in schedule_details.values())
                complete = sum(d['complete'] for d in schedule_details.values())
                incomplete = sum(d['incomplete'] for d in schedule_details.values())
                summary = {
                    'total': total,
                    'complete': complete,
                    'incomplete': incomplete,
                    'empty_schedules': sum(1 for d in schedule_details.values() if d['count'] == 0),
                }
        except Exception:
            pass

        payload = build_dashboard_payload(project, schedule_details, summary)
        return push_to_cloud(payload)

    except Exception as e:
        msg = f"Cloud sync error: {e}"
        logger.warning(msg)
        return False, msg
