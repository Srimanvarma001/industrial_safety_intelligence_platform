import { getRiskLabel, getZoneClass } from '../risk-engine.js';

export function renderGrid(state, selectedZone, onSelect) {
  const grid = document.getElementById('plantGrid');
  if (!state.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--color-text-secondary)">Loading...</div>';
    return;
  }
  grid.innerHTML = '';
  state.forEach(z => {
    const div = document.createElement('div');
    div.className = 'zone-cell ' + getZoneClass(z.score) + (selectedZone === z.id ? ' selected' : '');
    if (z.score >= 61) div.classList.add('pulse');
    div.onclick = () => onSelect(z.id);
    div.innerHTML = `
      <div>
        <div class="zone-name">${z.id} \u2014 ${z.name}</div>
        <div class="zone-score">${z.score}</div>
        <div class="zone-label">${getRiskLabel(z.score)}</div>
      </div>
      <div class="zone-workers">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        ${z.workers}${z.permit ? '  \u00B7  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> permit' : ''}${z.maintenance ? '  \u00B7  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> maint.' : ''}
      </div>
    `;
    grid.appendChild(div);
  });
}
