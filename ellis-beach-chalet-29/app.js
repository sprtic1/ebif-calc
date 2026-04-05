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
  renderWarnings(data);
}

function renderHero(data) {
  document.getElementById('project-name').textContent = data.project.name;
  const d = new Date(data.project.run_date);
  document.getElementById('run-date').textContent =
    d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) +
    ' at ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
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

  // Show recommendation
  const recEl = document.getElementById('shipping-rec');
  if (data.summary.container_recommendation) {
    const util = data.summary.container_utilisation || 0;
    recEl.textContent = `Recommended: ${data.summary.container_recommendation} — ${util}% utilisation`;
  }

  data.containers.forEach(ctr => {
    const card = document.createElement('div');
    card.className = 'shipping-card';

    const fmtDim = (inches) => {
      const ft = Math.floor(inches / 12);
      const rem = Math.round(inches % 12);
      return `${ft}'${rem}"`;
    };

    // Container spec line
    let specLine = '';
    if (ctr.name && ctr.interior_length_in) {
      const l = ctr.interior_length_in, w = ctr.interior_width_in, h = ctr.interior_height_in;
      specLine = `<div class="container-spec">${ctr.name} &mdash; ${fmtDim(l)} &times; ${fmtDim(w)} &times; ${fmtDim(h)} interior &mdash; ${ctr.max_payload_lbs.toLocaleString()} lbs max payload &mdash; ${ctr.max_pallets} pallets max</div>`;
    }

    // Split pallets by layer
    const layer1 = (ctr.pallets || []).filter(p => p.position.layer === 1);
    const layer2 = (ctr.pallets || []).filter(p => p.position.layer === 2);
    const maxPerLayer = (ctr.max_pallets || 44) / 2;

    function buildLayerGrid(pallets, label) {
      let html = `<div class="layer-label">${label}</div><div class="pallet-grid">`;
      for (let i = 0; i < maxPerLayer; i++) {
        const p = pallets[i];
        if (p) {
          const cls = p.block_id.startsWith('COM') ? 'pallet-com' : 'pallet-res';
          html += `<div class="pallet-cell ${cls}" title="P${p.pallet_number}: ${p.block_id} x${p.block_count}">${p.block_id.split('-')[1]}</div>`;
        } else {
          html += '<div class="pallet-cell pallet-empty"></div>';
        }
      }
      html += '</div>';
      return html;
    }

    // Stack height check
    const palletH = ctr.loaded_pallet_height_in || 48;
    const layers = ctr.layers_used || 2;
    const stackH = ctr.stack_height_in || (palletH * layers);
    const interiorH = ctr.interior_height_in || 90;
    const exceeds = stackH > interiorH;
    const heightClass = exceeds ? 'height-warning' : 'height-ok';
    const heightLine = `<div class="stack-height ${heightClass}">Layer height: ${palletH}in (estimated) &times; ${layers} layers = ${stackH}in total &mdash; Container interior height: ${interiorH}in${exceeds ? ' &#x26A0; EXCEEDS' : ''}</div>`;

    card.innerHTML = `
      <h3>Container ${ctr.container_number} of ${data.summary.containers_required}</h3>
      ${specLine}
      <div class="stat"><strong>${ctr.total_pallets} pallets loaded</strong></div>
      ${buildLayerGrid(layer1, 'Layer 1 (floor level)')}
      <div class="layer-gap"></div>
      ${layer2.length > 0 ? buildLayerGrid(layer2, 'Layer 2 (stacked)') : ''}
      ${heightLine}
    `;
    grid.appendChild(card);
  });
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
