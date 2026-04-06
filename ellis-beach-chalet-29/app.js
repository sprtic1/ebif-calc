/**
 * RENCO Block Schedule — BIM6x Demo Page
 * Loads renco_data.json and renders all sections.
 */

const DATA_URL = 'data/renco_data.json';

// Block display names
const BLOCK_NAMES = {
  'COM-32': 'Commercial Long Block (32")',
  'COM-16': 'Commercial Standard Block (16")',
  'COM-8':  'Commercial Half Block (8")',
  'COM-4':  'Commercial Closure Block (4")',
  'RES-30': 'Residential Long Block (30")',
  'RES-12': 'Residential Standard Block (12")',
  'RES-6':  'Residential Half Block (6")',
  'RES-3':  'Residential Closure Block (3")',
};

// Chart colors — olive/sage palette
const CHART_COLORS = [
  '#6b7243', // dark olive
  '#868D54', // olive
  '#a5ab76', // light olive
  '#C2C8A2', // sage
  '#d4d9bc', // light sage
  '#e0e4d0', // pale sage
];

function fmt(n) {
  return n.toLocaleString('en-US');
}

function fmtWeight(n) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

async function init() {
  let data;
  try {
    const resp = await fetch(DATA_URL);
    data = await resp.json();
  } catch (e) {
    document.getElementById('project-name').textContent = 'Error loading data';
    console.error(e);
    return;
  }

  renderHero(data);
  renderKPIs(data);
  renderBlockChart(data);
  renderBlockTable(data);
  renderWallSchedule(data);
  renderShipping(data);
  renderConsumables(data);
  renderWarnings(data);
}

function renderHero(data) {
  document.getElementById('project-name').textContent = data.project.name;
  const d = new Date(data.project.run_date);
  let dateStr = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) +
    ' at ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  const dur = data.project.pipeline_duration_sec;
  if (dur && dur > 0) {
    const mins = Math.floor(dur / 60);
    const secs = Math.round(dur % 60);
    dateStr += ` (${mins > 0 ? mins + 'm ' : ''}${secs}s)`;
  }
  document.getElementById('run-date').textContent = dateStr;
  document.title = `RENCO Block Schedule — ${data.project.name}`;
  const caption = document.getElementById('preview-caption');
  if (caption) caption.textContent = data.project.name;
}

function renderKPIs(data) {
  document.getElementById('kpi-walls').textContent = fmt(data.project.total_walls);
  document.getElementById('kpi-blocks').textContent = fmt(data.summary.total_blocks);
  document.getElementById('kpi-weight').textContent = fmt(Math.round(data.summary.total_weight_lbs));
  const rec = data.summary.container_recommendation || (data.summary.containers_required + ' x ' + (data.summary.container_type || 'ISO-40'));
  document.getElementById('kpi-containers').textContent = rec;
}

function renderBlockChart(data) {
  // Sort largest to smallest
  const blocks = [...data.blocks].sort((a, b) => b.count - a.count);
  const ctx = document.getElementById('block-chart').getContext('2d');

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: blocks.map(b => b.id),
      datasets: [{
        data: blocks.map(b => b.count),
        backgroundColor: CHART_COLORS.slice(0, blocks.length),
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            font: { family: "'DM Sans', sans-serif", size: 12 },
            padding: 16,
            usePointStyle: true,
            pointStyleWidth: 10,
          }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const b = blocks[ctx.dataIndex];
              const pct = ((b.count / data.summary.total_blocks) * 100).toFixed(1);
              return `${b.id}: ${fmt(b.count)} blocks (${pct}%)`;
            }
          }
        }
      }
    }
  });
}

function renderBlockTable(data) {
  // Order: COM-32, COM-16, COM-8, COM-4, then RES
  const order = ['COM-32','COM-16','COM-8','COM-4','RES-30','RES-12','RES-6','RES-3'];
  const blocks = order.map(id => data.blocks.find(b => b.id === id)).filter(Boolean);

  const tbody = document.querySelector('#block-table tbody');
  blocks.forEach(b => {
    const tr = document.createElement('tr');
    const badge = b.confirmed_weight
      ? '<span class="badge badge-confirmed">Confirmed</span>'
      : '<span class="badge badge-estimated">Estimated</span>';
    tr.innerHTML = `
      <td><strong>${b.id}</strong></td>
      <td class="num">${fmt(b.count)}</td>
      <td class="num">${b.weight_per_block_lbs}</td>
      <td class="num">${fmtWeight(b.total_weight_lbs)}</td>
      <td>${badge}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('block-total-count').textContent = fmt(data.summary.total_blocks);
  document.getElementById('block-total-weight').textContent = fmtWeight(data.summary.total_weight_lbs);
}

function renderWallSchedule(data) {
  const tbody = document.querySelector('#wall-table tbody');
  // Sort by wall ID
  const walls = [...data.walls].sort((a, b) => {
    const na = parseInt(a.id.match(/\d+/)?.[0] || '999');
    const nb = parseInt(b.id.match(/\d+/)?.[0] || '999');
    if (na !== nb) return na - nb;
    return (a.id.endsWith('X') ? 1 : 0) - (b.id.endsWith('X') ? 1 : 0);
  });

  walls.forEach(w => {
    const tr = document.createElement('tr');
    const flagged = w.flagged;
    const idClass = flagged ? 'wall-id-flagged' : '';
    const blocks = w.blocks || {};

    tr.innerHTML = `
      <td class="${idClass}">${w.id}</td>
      <td>${w.story}</td>
      <td class="num">${w.length_ft_in}</td>
      <td class="num">${w.height_in}"</td>
      <td>${w.series}</td>
      <td class="num">${w.courses}</td>
      <td class="num">${w.openings || ''}</td>
      <td class="num">${blocks['COM-32'] || 0}</td>
      <td class="num">${blocks['COM-16'] || 0}</td>
      <td class="num">${blocks['COM-8'] || 0}</td>
      <td class="num">${blocks['COM-4'] || 0}</td>
      <td class="num"><strong>${w.total_blocks}</strong></td>
      <td class="num">${fmtWeight(w.weight_lbs)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderShipping(data) {
  const grid = document.getElementById('shipping-grid');
  if (!data.containers || data.containers.length === 0) {
    grid.innerHTML = '<p>No containers required.</p>';
    return;
  }

  // Show recommendation only
  const recEl = document.getElementById('shipping-rec');
  if (data.summary.container_recommendation) {
    recEl.innerHTML = `<strong>${data.summary.container_recommendation}</strong>`;
  }

  data.containers.forEach(ctr => {
    const card = document.createElement('div');
    card.className = 'shipping-card';

    const fmtDim = (inches) => {
      const ft = Math.floor(inches / 12);
      const rem = Math.round(inches % 12);
      return `${ft}'${rem}"`;
    };

    // Pallets by layer
    // Grid dimensions from container type: 40ft = 11 cols × 2 rows, 20ft = 5 cols × 2 rows
    const ppl = (ctr.max_pallets || 44) / 2;   // positions per layer
    const numCols = Math.round(ppl / 2);        // 11 or 5
    const numRows = 2;

    const layer1 = (ctr.pallets || []).filter(p => p.position.layer === 1);
    const layer2 = (ctr.pallets || []).filter(p => p.position.layer === 2);

    function buildLayerGrid(pallets, label) {
      // Build lookup: row-col → pallet
      const grid = {};
      let maxCol = 0;
      pallets.forEach(p => {
        grid[`${p.position.row}-${p.position.col}`] = p;
        if (p.position.col > maxCol) maxCol = p.position.col;
      });
      // Use the container's full column count, but no empty cells beyond last filled column
      const cols = Math.max(maxCol, 1);

      let html = `<div class="layer-label">${label}</div>`;
      html += `<div class="pallet-grid" style="grid-template-columns: repeat(${cols}, 1fr)">`;
      for (let r = 1; r <= numRows; r++) {
        for (let c = 1; c <= cols; c++) {
          const p = grid[`${r}-${c}`];
          if (p) {
            const cls = p.block_id.startsWith('COM') ? 'pallet-com' : 'pallet-res';
            html += `<div class="pallet-cell ${cls}" title="P${p.pallet_number}: ${p.block_id} x${p.block_count}">${p.block_id.split('-')[1]}<br>${p.block_count}</div>`;
          } else {
            html += '<div class="pallet-cell pallet-empty"></div>';
          }
        }
      }
      html += '</div>';
      return html;
    }

    const loadedWt = ctr.total_weight_lbs || 0;
    const maxWt = ctr.max_payload_lbs || 0;
    const maxPal = ctr.max_pallets || 0;
    const loadedPal = ctr.total_pallets || 0;
    const palPct = maxPal > 0 ? Math.round(loadedPal / maxPal * 100) : 0;
    const wtPct = maxWt > 0 ? Math.round(loadedWt / maxWt * 100) : 0;

    card.innerHTML = `
      <h3>Container ${ctr.container_number} of ${data.summary.containers_required}</h3>
      <div class="container-spec">${ctr.name}</div>
      <div class="container-stats">
        <span>Pallets: ${loadedPal} / ${maxPal} (${palPct}%)</span>
        <span>Weight: ${loadedWt.toLocaleString()} / ${maxWt.toLocaleString()} lbs (${wtPct}%)</span>
      </div>
      ${buildLayerGrid(layer1, 'Layer 1 (floor)')}
      ${layer2.length > 0 ? '<div class="layer-gap"></div>' + buildLayerGrid(layer2, 'Layer 2 (stacked)') : ''}
    `;
    grid.appendChild(card);
  });
}

function renderConsumables(data) {
  const el = document.getElementById('consumables');
  if (!el || !data.consumables) return;
  const c = data.consumables;
  const est = c.adhesive_confirmed ? '' : ' (estimated)';
  el.innerHTML = `
    <h3 class="consumables-title">Consumables & Equipment</h3>
    <div class="consumables-grid">
      <div class="consumable-item">
        <div class="consumable-value">${c.adhesive_cartridges}</div>
        <div class="consumable-label">Adhesive Cartridges${est}</div>
        <div class="consumable-detail">${fmt(c.adhesive_joint_linear_ft)} LF horizontal joints</div>
      </div>
      <div class="consumable-item">
        <div class="consumable-value">${c.mallets}</div>
        <div class="consumable-label">Rubber Mallets</div>
        <div class="consumable-detail">1 per 20 glue guns (${c.adhesive_cartridges} cartridges)</div>
      </div>
    </div>
    <p class="consumables-note">Shipped loose with container cargo — not palletized.</p>
  `;
}

function renderWarnings(data) {
  if (!data.warnings || data.warnings.length === 0) return;

  document.getElementById('warnings-section').style.display = '';
  const ul = document.getElementById('warning-list');
  data.warnings.forEach(w => {
    const li = document.createElement('li');
    if (w.wall_id) {
      li.innerHTML = `<strong>${w.wall_id}</strong> &mdash; ${w.reason || w.detail}`;
    } else {
      li.textContent = w.detail || w.reason || JSON.stringify(w);
    }
    ul.appendChild(li);
  });
}

// Go
document.addEventListener('DOMContentLoaded', init);
