"""EID Project Manager — Server Entry Point (DigitalOcean Droplet)

Standalone Flask app for the DO server at apps.ellisid.com/project-hub/.
Self-contained — no imports from services/ or routes/ modules.

Routes:
  GET  /api/projects          — list all projects
  POST /api/projects          — create a project
  GET  /api/projects/:id      — get single project
  POST /api/sync              — receive dashboard data from local app (token auth)
  GET  /api/dashboard         — return synced dashboard data (token auth)
  GET  /team                  — read-only team dashboard HTML page
  GET  /                      — serve React frontend (catch-all)

Deployed as: /opt/eid-apps/project-hub/main.py
Run via: gunicorn main:app (behind nginx at /project-hub/)
"""

import json
import os
import re
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

app = Flask(__name__, static_folder='frontend/dist', static_url_path='/')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
SYNC_DATA_FILE = os.path.join(DATA_DIR, 'dashboard_sync.json')


# ---------- Helpers ----------

def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, 'r') as f:
        return json.load(f)


def save_projects(projects):
    os.makedirs(os.path.dirname(PROJECTS_FILE), exist_ok=True)
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text


def _get_sync_token():
    """Read sync token from environment or settings.json."""
    token = os.environ.get('EID_SYNC_TOKEN', '')
    if token:
        return token
    try:
        settings_path = os.path.join(BASE_DIR, 'settings.json')
        with open(settings_path, 'r') as f:
            return json.load(f).get('sync_token', '')
    except Exception:
        return ''


def _check_auth():
    """Validate Bearer token. Returns error response tuple or None."""
    token = _get_sync_token()
    if not token:
        return jsonify({'error': 'Sync not configured'}), 500
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer ') or auth[7:] != token:
        return jsonify({'error': 'Unauthorized'}), 401
    return None


# ---------- Project API Routes ----------

@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(load_projects())


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    project_name = data.get('project_name', '').strip()
    client_name = data.get('client_name', '').strip()
    address = data.get('address', '').strip()
    folder_location = data.get('folder_location', '').strip()

    if not project_name:
        return jsonify({'error': 'Project name is required'}), 400

    project = {
        'id': str(uuid.uuid4())[:8],
        'slug': slugify(project_name),
        'project_name': project_name,
        'client_name': client_name,
        'address': address,
        'folder_location': folder_location,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'last_synced': None,
        'schedules': {
            'appliances': 0, 'bath_accessories': 0, 'cabinetry_hardware': 0,
            'cabinetry_inserts': 0, 'cabinetry_style': 0, 'countertops': 0,
            'decorative_lighting': 0, 'door_hardware': 0, 'flooring': 0,
            'furniture': 0, 'lighting_electrical': 0, 'plumbing': 0,
            'shower_glass_mirrors': 0, 'specialty_equipment': 0,
            'surface_finishes': 0, 'tile': 0,
        },
    }

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


@app.route('/api/projects/<project_id>/details', methods=['GET'])
def get_project_details(project_id):
    """Return project with schedule details (server version — from stored data only)."""
    projects = load_projects()
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    schedules = project.get('schedules', {})
    total = sum(schedules.values())
    return jsonify({
        'project': project,
        'schedule_details': {sid: {'count': c, 'complete': 0, 'incomplete': c, 'rows': []}
                             for sid, c in schedules.items()},
        'summary': {
            'total': total, 'complete': 0, 'incomplete': total,
            'empty_schedules': sum(1 for v in schedules.values() if v == 0),
        },
        'pull_history': project.get('pull_history', []),
    })


# ---------- Cloud Sync Routes ----------

@app.route('/api/sync', methods=['POST'])
def receive_sync():
    """Receive dashboard data from the local app and save to disk."""
    auth_error = _check_auth()
    if auth_error:
        return auth_error

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    data['received_at'] = datetime.utcnow().isoformat()

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SYNC_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return jsonify({'status': 'ok', 'synced_at': data.get('synced_at', '')}), 200


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Return the most recent synced dashboard data."""
    auth_error = _check_auth()
    if auth_error:
        return auth_error

    if not os.path.exists(SYNC_DATA_FILE):
        return jsonify({'error': 'No data synced yet'}), 404

    with open(SYNC_DATA_FILE, 'r') as f:
        return jsonify(json.load(f))


# ---------- Team Dashboard (Read-Only HTML) ----------

@app.route('/team')
def team_dashboard():
    """Serve the read-only team dashboard page."""
    return Response(TEAM_DASHBOARD_HTML, mimetype='text/html')


# ---------- Frontend (React SPA catch-all) ----------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # Skip API and team routes
    if path.startswith('api/') or path == 'team':
        return jsonify({'error': 'Not found'}), 404

    dist_dir = os.path.join(BASE_DIR, 'frontend', 'dist')
    if path and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    index = os.path.join(dist_dir, 'index.html')
    if os.path.exists(index):
        return send_from_directory(dist_dir, 'index.html')
    return jsonify({'message': 'EID Project Manager API running.'}), 200


# ---------- Team Dashboard HTML (self-contained) ----------

TEAM_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>EID Project Manager - Team Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Arial Narrow',Arial,sans-serif;background:#F0F2E8;color:#2C2C2C;min-height:100vh}
.header{background:#868C54;color:white;padding:16px 24px}
.header h1{font-family:'Lato',sans-serif;font-size:24px;font-weight:900}
.container{max-width:1200px;margin:0 auto;padding:24px 16px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.card{background:white;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);padding:16px;text-align:center;border-top:4px solid #868C54}
.card.yellow{border-top-color:#D4A843}.card.gray{border-top-color:#ccc}
.card .num{font-family:'Lato',sans-serif;font-weight:700;font-size:32px;color:#868C54}
.card.yellow .num{color:#D4A843}.card.gray .num{color:#ccc}
.card .label{font-family:'Lato',sans-serif;font-size:14px;color:#737569}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.tile{background:white;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);padding:16px;text-align:center;border-top:4px solid #ccc}
.tile.green{border-top-color:#868C54}.tile.yellow{border-top-color:#D4A843}
.tile .num{font-family:'Lato',sans-serif;font-weight:700;font-size:32px;color:#ccc}
.tile.green .num{color:#868C54}.tile.yellow .num{color:#D4A843}
.tile .name{font-family:'Lato',sans-serif;font-size:13px;color:#999}
.tile.green .name,.tile.yellow .name{color:#737569}
.tile .sub{font-size:11px;color:#D4A843;margin-top:4px}
.project-header{background:white;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);padding:20px;margin-bottom:24px}
.project-header h2{font-family:'Lato',sans-serif;font-size:28px;font-weight:700;color:#868C54}
.project-header .client{color:#737569;font-size:16px}
.project-header .meta{color:#C2C8A2;font-size:13px;margin-top:4px}
.history{background:white;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);padding:16px}
.history h3{font-family:'Lato',sans-serif;color:#868C54;font-weight:700;margin-bottom:12px}
.history table{width:100%;font-size:14px}
.history th{text-align:left;color:#737569;font-family:'Lato',sans-serif;border-bottom:1px solid #eee;padding-bottom:8px}
.history td{padding:6px 0}
.history tr:nth-child(even){background:#F0F2E8}
.loading{text-align:center;padding:60px;color:#737569;font-family:'Lato',sans-serif}
.badge{display:inline-block;background:#F0F2E8;color:#868C54;font-family:'Lato',sans-serif;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;margin-top:8px}
@media(max-width:768px){.cards,.tiles{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="header"><h1>EID Project Manager</h1></div>
<div class="container"><div id="app"><div class="loading">Loading dashboard...</div></div></div>
<script>
const LABELS={appliances:'Appliances',bath_accessories:'Bath Accessories',cabinetry_hardware:'Cabinetry Hardware',cabinetry_inserts:'Cabinetry Inserts',cabinetry_style:'Cabinetry Style & Species',countertops:'Countertops',decorative_lighting:'Decorative Lighting',door_hardware:'Door Hardware',flooring:'Flooring',furniture:'Furniture',lighting_electrical:'Lighting & Electrical',plumbing:'Plumbing',shower_glass_mirrors:'Shower Glass & Mirrors',specialty_equipment:'Specialty Equipment',surface_finishes:'Surface Finishes',tile:'Tile'};
const token=new URLSearchParams(window.location.search).get('token')||'';
async function load(){
  const app=document.getElementById('app');
  try{
    const base=window.location.pathname.replace(/\\/team$/,'');
    const res=await fetch(base+'/api/dashboard',{headers:token?{'Authorization':'Bearer '+token}:{}});
    if(res.status===401){app.innerHTML='<div class="loading">Access denied &mdash; add ?token=YOUR_TOKEN to the URL</div>';return}
    if(!res.ok){app.innerHTML='<div class="loading">No data synced yet. Run Refresh from Archicad on the local app first.</div>';return}
    render(await res.json());
  }catch(e){app.innerHTML='<div class="loading">Error: '+e.message+'</div>'}
}
function render(data){
  const p=data.projects&&data.projects[0];
  if(!p){document.getElementById('app').innerHTML='<div class="loading">No projects synced</div>';return}
  const s=p.summary||{total:0,complete:0,incomplete:0,empty_schedules:16};
  const sd=p.schedule_details||{};const sched=p.schedules||{};const hist=p.pull_history||[];
  let h='';
  h+='<div class="project-header"><h2>'+esc(p.project_name)+'</h2>';
  if(p.client_name)h+='<div class="client">'+esc(p.client_name)+'</div>';
  if(p.address)h+='<div class="meta">'+esc(p.address)+'</div>';
  h+='<div class="meta">Last synced: '+(p.last_synced?new Date(p.last_synced).toLocaleString():'Never')+'</div>';
  h+='<div class="badge">Read-only team view</div></div>';
  h+='<div class="cards">'+card(s.total,'Total Items','')+card(s.complete,'Complete','')+card(s.incomplete,'Needs Attention',s.incomplete>0?'yellow':'')+card(s.empty_schedules,'Empty Schedules','gray')+'</div>';
  h+='<div class="tiles">';
  for(const[key,label]of Object.entries(LABELS)){
    const d=sd[key]||{count:0,complete:0,incomplete:0};
    const count=d.count||sched[key]||0;
    let cls='';if(count>0&&d.incomplete===0)cls='green';else if(count>0)cls='yellow';
    h+='<div class="tile '+cls+'"><div class="num">'+count+'</div><div class="name">'+esc(label)+'</div>';
    if(count>0&&d.incomplete>0)h+='<div class="sub">'+d.incomplete+' incomplete</div>';
    h+='</div>';
  }
  h+='</div>';
  if(hist.length>0){
    h+='<div class="history"><h3>Pull History</h3><table><thead><tr><th>Date</th><th style="text-align:right">Items</th></tr></thead><tbody>';
    for(const e of[...hist].reverse())h+='<tr><td>'+new Date(e.timestamp).toLocaleString()+'</td><td style="text-align:right;font-weight:700;color:#868C54">'+e.total+'</td></tr>';
    h+='</tbody></table></div>';
  }
  h+='<div style="text-align:center;margin-top:16px;font-size:12px;color:#C2C8A2">Data synced '+(data.synced_at?new Date(data.synced_at).toLocaleString():'unknown')+'</div>';
  document.getElementById('app').innerHTML=h;
}
function card(n,l,c){return'<div class="card '+c+'"><div class="num">'+n+'</div><div class="label">'+l+'</div></div>'}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
load();
</script>
</body>
</html>"""


if __name__ == '__main__':
    app.run(debug=True, port=5000)
