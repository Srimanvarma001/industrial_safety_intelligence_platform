import { getRiskLabel, getZoneClass } from '../risk-engine.js';

const ZONE_LAYOUT = [
  { id: 'Z1', x: 0, y: 0, w: 2, h: 1, equip: '\uD83D\uDD25', equipLabel: 'Blast Furnace' },
  { id: 'Z3', x: 2, y: 0, w: 2, h: 1, equip: '\u26A1', equipLabel: 'Gas Processing' },
  { id: 'Z8', x: 4, y: 0, w: 2, h: 1, equip: '\uD83D\uDEE0', equipLabel: 'Control Room' },
  { id: 'Z2', x: 0, y: 1, w: 2, h: 1, equip: '\uD83D\uDD25', equipLabel: 'Coke Oven' },
  { id: 'Z4', x: 2, y: 1, w: 2, h: 1, equip: '\u26CF', equipLabel: 'Ore Handling' },
  { id: 'Z6', x: 4, y: 1, w: 2, h: 1, equip: '\uD83D\uDCA8', equipLabel: 'Steam Plant' },
  { id: 'Z5', x: 0, y: 2, w: 3, h: 1, equip: '\u26FD', equipLabel: 'Slag Yard' },
  { id: 'Z7', x: 3, y: 2, w: 3, h: 1, equip: '\uD83C\uDF0A', equipLabel: 'Cooling Tower' },
];

const ZONE_WORKER_POSITIONS = {
  Z1: [{x:15,y:25},{x:35,y:25},{x:55,y:25},{x:75,y:25}],
  Z2: [{x:25,y:30},{x:55,y:30}],
  Z3: [{x:12,y:25},{x:30,y:25},{x:50,y:25},{x:70,y:25},{x:88,y:25}],
  Z4: [{x:20,y:30},{x:50,y:30},{x:75,y:30}],
  Z5: [{x:25,y:30},{x:55,y:30}],
  Z6: [{x:15,y:25},{x:35,y:25},{x:60,y:25},{x:82,y:25}],
  Z7: [{x:25,y:30},{x:55,y:30}],
  Z8: [{x:30,y:30},{x:60,y:30}],
};

function getHazardPlume(gasPct, thresh) {
  if (gasPct >= 100) return { opacity: 0.35, color: '#E24B4A', r: 50 };
  if (gasPct >= 80) return { opacity: 0.25, color: '#E24B4A', r: 38 };
  if (gasPct >= 60) return { opacity: 0.18, color: '#EF9F27', r: 28 };
  return { opacity: 0, color: 'transparent', r: 0 };
}

export function renderGrid(state, selectedZone, onSelect) {
  const grid = document.getElementById('plantGrid');
  if (!state.length) {
    grid.innerHTML = '<div style="text-align:center;padding:20px;color:var(--color-text-secondary)">Loading...</div>';
    return;
  }

  const maxScore = Math.max(...state.map(z => z.score), 1);
  const svgW = 600, svgH = 340;

  let zonesHtml = '';
  let svgOverlays = '';
  let svgWorkers = '';

  ZONE_LAYOUT.forEach(layout => {
    const z = state.find(x => x.id === layout.id);
    if (!z) return;

    const zoneClass = getZoneClass(z.score) + (selectedZone === z.id ? ' selected' : '');
    const riskLabel = getRiskLabel(z.score);
    const gasPct = ((z.currentGas ?? z.baseGas) / z.gasThresh) * 100;
    const plume = getHazardPlume(gasPct, z.gasThresh);

    const px = layout.x * (svgW / 6);
    const py = layout.y * (svgH / 3);
    const pw = layout.w * (svgW / 6) - 6;
    const ph = layout.h * (svgH / 3) - 6;

    zonesHtml += `
      <div class="zone-cell ${zoneClass}" style="grid-column:${layout.x + 1} / span ${layout.w};grid-row:${layout.y + 1} / span ${layout.h}"
           onclick="window.__selectZone('${z.id}')">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <div class="zone-name">${z.id} — ${z.name}</div>
            <div class="zone-score">${z.score}</div>
            <div class="zone-label">${riskLabel}</div>
          </div>
          <div style="font-size:20px;opacity:0.6">${layout.equip}</div>
        </div>
        <div class="zone-workers">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          ${z.workers}${z.permit ? ' · <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> permit' : ''}${z.maintenance ? ' · <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> maint.' : ''}
        </div>
        <div style="font-size:10px;color:var(--color-text-secondary);margin-top:4px;display:flex;gap:4px;align-items:center">
          <span style="background:${z.score >= 61 ? 'var(--color-red-bg)' : 'var(--color-background-secondary)'};padding:1px 5px;border-radius:4px">
            ${Math.round(gasPct)}% of threshold
          </span>
          ${z.score >= 61 && z.detectionGap?.compoundOnlyDetection ? '<span style="background:var(--color-red-bg);color:var(--color-red);padding:1px 5px;border-radius:4px;font-weight:600">Compound catch</span>' : ''}
        </div>
      </div>`;

    if (plume.opacity > 0) {
      const cx = px + pw / 2;
      const cy = py + ph / 2;
      svgOverlays += `
        <circle cx="${cx}" cy="${cy}" r="${plume.r}" fill="${plume.color}" opacity="${plume.opacity}"
          stroke="${plume.color}" stroke-width="1" stroke-opacity="0.5">
          <animate attributeName="r" values="${plume.r};${plume.r + 10};${plume.r}" dur="3s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="${plume.opacity};${plume.opacity * 0.5};${plume.opacity}" dur="3s" repeatCount="indefinite"/>
        </circle>`;

      svgOverlays += `
        <text x="${cx}" y="${cy - plume.r - 6}" text-anchor="middle" font-size="9" fill="${plume.color}" font-weight="600" opacity="0.8">
          GAS HAZARD
        </text>`;
    }

    const positions = ZONE_WORKER_POSITIONS[z.id] || [];
    const visibleCount = Math.min(positions.length, z.workers || 0);
    for (let i = 0; i < visibleCount; i++) {
      const wp = positions[i];
      const wx = px + (wp.x / 100) * pw;
      const wy = py + (wp.y / 100) * ph;
      const isPermitWorker = i === 0 && z.permit;
      svgWorkers += `
        <g class="worker-dot" onclick="window.__selectZone('${z.id}')" style="cursor:pointer">
          <circle cx="${wx}" cy="${wy}" r="${isPermitWorker ? 6 : 5}" fill="${isPermitWorker ? '#EF9F27' : '#378ADD'}"
            stroke="#fff" stroke-width="1.5" opacity="0.95">
            ${z.score >= 61 ? `<animate attributeName="r" values="${isPermitWorker ? 6 : 5};${isPermitWorker ? 8 : 7};${isPermitWorker ? 6 : 5}" dur="2s" repeatCount="indefinite"/>` : ''}
          </circle>
          <text x="${wx}" y="${wy + 1.5}" text-anchor="middle" font-size="6" fill="#fff" font-weight="700">${i + 1}</text>
        </g>`;
    }
  });

  grid.innerHTML = `
    <div class="plant-layout-inner">
      ${zonesHtml}
      <svg class="plant-layout-svg" viewBox="0 0 ${svgW} ${svgH}" preserveAspectRatio="xMidYMid meet" aria-label="Plant floor geospatial layout with worker positions and hazard overlays">
        ${svgOverlays}
        ${svgWorkers}
      </svg>
      <div class="layout-legend">
        <span><span class="legend-dot" style="background:#378ADD"></span> Worker</span>
        <span><span class="legend-dot" style="background:#EF9F27"></span> Permit holder</span>
        <span><span class="legend-dot" style="background:#E24B4A;animation:pulse-anim 1.2s infinite"></span> Hazard zone</span>
      </div>
    </div>`;
}

window.__selectZone = (id) => {
  const event = new CustomEvent('zone-select', { detail: { id } });
  document.dispatchEvent(event);
};
