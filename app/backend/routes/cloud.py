"""Cloud sync routes — receive and serve dashboard data on DigitalOcean."""

import json
import os

from flask import Blueprint, jsonify, request, Response

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


@cloud_bp.route('/team', methods=['GET'])
def team_dashboard():
    """Serve a read-only team dashboard page (no auth required to view the page,
    but the JS fetches /api/dashboard which requires the token passed as a query param)."""
    return Response(TEAM_DASHBOARD_HTML, mimetype='text/html')


# --- Self-contained team dashboard HTML ---
TEAM_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EID Project Manager — Team Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Arial Narrow', Arial, sans-serif; background: #F0F2E8; color: #2C2C2C; min-height: 100vh; }
.heading { font-family: 'Lato', sans-serif; }
.header { background: #868C54; color: white; padding: 16px 24px; }
.header h1 { font-family: 'Lato', sans-serif; font-size: 24px; font-weight: 900; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.card { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 16px; text-align: center; border-top: 4px solid #868C54; }
.card.yellow { border-top-color: #D4A843; }
.card.gray { border-top-color: #ccc; }
.card .num { font-family: 'Lato', sans-serif; font-weight: 700; font-size: 32px; color: #868C54; }
.card.yellow .num { color: #D4A843; }
.card.gray .num { color: #ccc; }
.card .label { font-family: 'Lato', sans-serif; font-size: 14px; color: #737569; }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.tile { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 16px; text-align: center; border-top: 4px solid #ccc; }
.tile.green { border-top-color: #868C54; }
.tile.yellow { border-top-color: #D4A843; }
.tile .num { font-family: 'Lato', sans-serif; font-weight: 700; font-size: 32px; color: #ccc; }
.tile.green .num { color: #868C54; }
.tile.yellow .num { color: #D4A843; }
.tile .name { font-family: 'Lato', sans-serif; font-size: 13px; color: #999; }
.tile.green .name, .tile.yellow .name { color: #737569; }
.tile .sub { font-size: 11px; color: #D4A843; margin-top: 4px; }
.project-header { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 24px; }
.project-header h2 { font-family: 'Lato', sans-serif; font-size: 28px; font-weight: 700; color: #868C54; }
.project-header .client { color: #737569; font-size: 16px; }
.project-header .meta { color: #C2C8A2; font-size: 13px; margin-top: 4px; }
.history { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 16px; }
.history h3 { font-family: 'Lato', sans-serif; color: #868C54; font-weight: 700; margin-bottom: 12px; }
.history table { width: 100%; font-size: 14px; }
.history th { text-align: left; color: #737569; font-family: 'Lato', sans-serif; border-bottom: 1px solid #eee; padding-bottom: 8px; }
.history td { padding: 6px 0; }
.history tr:nth-child(even) { background: #F0F2E8; }
.loading { text-align: center; padding: 60px; color: #737569; font-family: 'Lato', sans-serif; }
.badge { display: inline-block; background: #F0F2E8; color: #868C54; font-family: 'Lato', sans-serif; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-top: 8px; }
@media (max-width: 768px) { .cards, .tiles { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<div class="header"><h1>EID Project Manager</h1></div>
<div class="container">
<div id="app"><div class="loading">Loading dashboard...</div></div>
</div>
<script>
const LABELS = {
  appliances:'Appliances', bath_accessories:'Bath Accessories', cabinetry_hardware:'Cabinetry Hardware',
  cabinetry_inserts:'Cabinetry Inserts', cabinetry_style:'Cabinetry Style & Species',
  countertops:'Countertops', decorative_lighting:'Decorative Lighting', door_hardware:'Door Hardware',
  flooring:'Flooring', furniture:'Furniture', lighting_electrical:'Lighting & Electrical',
  plumbing:'Plumbing', shower_glass_mirrors:'Shower Glass & Mirrors',
  specialty_equipment:'Specialty Equipment', surface_finishes:'Surface Finishes', tile:'Tile'
};
const params = new URLSearchParams(window.location.search);
const token = params.get('token') || '';
async function load() {
  const app = document.getElementById('app');
  try {
    const res = await fetch('/project-hub/api/dashboard', {
      headers: token ? {'Authorization': 'Bearer ' + token} : {}
    });
    if (res.status === 401) { app.innerHTML = '<div class="loading">Access denied — token required (?token=...)</div>'; return; }
    if (!res.ok) { app.innerHTML = '<div class="loading">No data synced yet</div>'; return; }
    const data = await res.json();
    render(data);
  } catch(e) { app.innerHTML = '<div class="loading">Error: ' + e.message + '</div>'; }
}
function render(data) {
  const p = data.projects?.[0];
  if (!p) { document.getElementById('app').innerHTML = '<div class="loading">No projects</div>'; return; }
  const s = p.summary || {total:0,complete:0,incomplete:0,empty_schedules:16};
  const sd = p.schedule_details || {};
  const sched = p.schedules || {};
  const hist = p.pull_history || [];
  let html = '';
  // Project header
  html += '<div class="project-header">';
  html += '<h2>' + esc(p.project_name) + '</h2>';
  if (p.client_name) html += '<div class="client">' + esc(p.client_name) + '</div>';
  if (p.address) html += '<div class="meta">' + esc(p.address) + '</div>';
  html += '<div class="meta">Last synced: ' + (p.last_synced ? new Date(p.last_synced).toLocaleString() : 'Never') + '</div>';
  html += '<div class="badge">Read-only team view</div>';
  html += '</div>';
  // Summary cards
  html += '<div class="cards">';
  html += card(s.total, 'Total Items', '');
  html += card(s.complete, 'Complete', '');
  html += card(s.incomplete, 'Needs Attention', s.incomplete > 0 ? 'yellow' : '');
  html += card(s.empty_schedules, 'Empty Schedules', 'gray');
  html += '</div>';
  // Tiles
  html += '<div class="tiles">';
  for (const [key, label] of Object.entries(LABELS)) {
    const d = sd[key] || {count:0, complete:0, incomplete:0};
    const count = d.count || sched[key] || 0;
    let cls = '';
    if (count > 0 && d.incomplete === 0) cls = 'green';
    else if (count > 0) cls = 'yellow';
    html += '<div class="tile ' + cls + '">';
    html += '<div class="num">' + count + '</div>';
    html += '<div class="name">' + esc(label) + '</div>';
    if (count > 0 && d.incomplete > 0) html += '<div class="sub">' + d.incomplete + ' incomplete</div>';
    html += '</div>';
  }
  html += '</div>';
  // Pull history
  if (hist.length > 0) {
    html += '<div class="history"><h3>Pull History</h3><table><thead><tr><th>Date</th><th style="text-align:right">Items</th></tr></thead><tbody>';
    for (const h of [...hist].reverse()) {
      html += '<tr><td>' + new Date(h.timestamp).toLocaleString() + '</td><td style="text-align:right;font-weight:700;color:#868C54">' + h.total + '</td></tr>';
    }
    html += '</tbody></table></div>';
  }
  // Synced at
  html += '<div style="text-align:center;margin-top:16px;font-size:12px;color:#C2C8A2">Data synced at ' + (data.synced_at ? new Date(data.synced_at).toLocaleString() : 'unknown') + '</div>';
  document.getElementById('app').innerHTML = html;
}
function card(num, label, cls) {
  return '<div class="card ' + cls + '"><div class="num">' + num + '</div><div class="label">' + label + '</div></div>';
}
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
load();
</script>
</body>
</html>"""
