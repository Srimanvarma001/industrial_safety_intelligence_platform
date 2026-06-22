import { getRiskLabel, getScoreClass, getBadgeClass } from '../risk-engine.js';
import { apiFetch } from '../api.js';

let sparklineCharts = {};

export function showZoneDetail(id, state, onOpenIncident) {
  const z = state.find(x => x.id === id);
  if (!z) return;

  document.getElementById('noZoneMsg').style.display = 'none';
  document.getElementById('loadingDetail').style.display = 'none';
  const det = document.getElementById('zoneDetail');
  det.style.display = 'block';
  const barColor = z.score >= 61 ? '#E24B4A' : z.score >= 31 ? '#EF9F27' : '#639922';

  det.innerHTML = `
    <div style="margin-bottom:16px">
      <div class="panel-zone-name">${z.id} \u2014 ${z.name}</div>
      <div class="panel-score-row">
        <div class="panel-score-big ${getScoreClass(z.score)}">${z.score}</div>
        <div class="score-bar-bg"><div class="score-bar-fill" style="width:${z.score}%;background:${barColor}"></div></div>
        <span class="badge ${getBadgeClass(z.score)}">${getRiskLabel(z.score)}</span>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Gas readings</div>
      <div class="sparkline-area"><canvas id="spark-${z.id}" role="img" aria-label="Gas trend for ${z.name}"></canvas></div>
      <div class="info-row">
        <span class="info-key">Current (CO)</span>
        <span class="info-val">${Math.round(z.currentGas ?? z.baseGas)} ppm</span>
      </div>
      <div class="info-row">
        <span class="info-key">Threshold</span>
        <span class="info-val">${z.gasThresh} ppm</span>
      </div>
      <div class="info-row">
        <span class="info-key">Utilisation</span>
        <span class="info-val">${Math.round(((z.currentGas ?? z.baseGas) / z.gasThresh) * 100)}%</span>
      </div>
      <div class="info-row">
        <span class="info-key">Trend</span>
        <span class="info-val">${z.gasTrending ? '\u2B06 Rising' : '\u2192 Stable'}</span>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Operational context</div>
      <div class="info-row">
        <span class="info-key">Active permit</span>
        <span class="info-val">${z.permit ? `<span class="badge badge-yellow">${z.permit.replace('_', ' ')}</span>` : '<span class="badge badge-green">none</span>'}</span>
      </div>
      <div class="info-row">
        <span class="info-key">Maintenance</span>
        <span class="info-val">${z.maintenance ? `<span class="badge badge-red">${z.maintenance.replace(/_/g, ' ')}</span>` : '<span class="badge badge-green">none</span>'}</span>
      </div>
      <div class="info-row">
        <span class="info-key">Shift changeover</span>
        <span class="info-val">${z.changeover ? '<span class="badge badge-yellow">window open</span>' : '<span class="badge badge-green">no</span>'}</span>
      </div>
      <div class="info-row">
        <span class="info-key">Workers present</span>
        <span class="info-val">${z.workers}</span>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Risk factors stacking</div>
      <div class="reasons-list">${z.reasons && z.reasons.length ? z.reasons.map(r => `<div class="reason-item"><span class="reason-weight">${r.w}</span><span>${r.t}${r.pct ? ' (' + r.pct + '% of threshold)' : ''}</span></div>`).join('') : '<div class="reason-item"><span style="color:var(--color-text-secondary)">No risk factors active</span></div>'}</div>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">AI Risk Analysis <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--color-text-secondary)">(OISD RAG)</span></div>
      <div class="llm-box" id="llmBox-${z.id}">
        <div class="llm-loading"><span class="llm-dot"></span><span class="llm-dot"></span><span class="llm-dot"></span> Analysing risk context...</div>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Historical Pattern Match</div>
      <div id="nearMissBox-${z.id}">
        <div class="llm-loading"><span class="llm-dot"></span><span class="llm-dot"></span><span class="llm-dot"></span> Checking patterns...</div>
      </div>
    </div>

    <div class="whatif-section">
      <div class="whatif-label">
        <span>What-If: Gas level adjustment</span>
        <span class="whatif-value" id="whatifVal-${z.id}">${Math.round(z.currentGas ?? z.baseGas)} ppm</span>
      </div>
      <input type="range" class="whatif-slider" id="whatifSlider-${z.id}"
        min="0" max="${z.gasThresh + 20}" value="${Math.round(z.currentGas ?? z.baseGas)}"
        oninput="window.__onWhatIfChange('${z.id}')">
      <div class="whatif-result" id="whatifResult-${z.id}" style="background:${barColor}22;color:${barColor}">
        Score: ${z.score}/100 \u2014 ${getRiskLabel(z.score)}
      </div>
    </div>

    ${z.score >= 61 ? `<button class="btn-report" onclick="window.__openIncident('${z.id}')">View incident report</button>` : `<button class="btn-report btn-report-inactive" disabled>Incident report (fires at score \u2265 61)</button>`}
  `;

  setTimeout(() => renderSparkline(z, sparklineCharts), 50);

  fetchLLMExplanation(z.id);
  fetchNearMisses(z.id);
}

// ---- Sparkline ----

function renderSparkline(z, chartCache) {
  const cid = 'spark-' + z.id;
  if (chartCache[cid]) { chartCache[cid].destroy(); delete chartCache[cid]; }
  const ctx = document.getElementById(cid);
  if (!ctx) return;
  const data = z.gasHistory || [z.baseGas];
  const barColor = z.score >= 61 ? '#E24B4A' : z.score >= 31 ? '#EF9F27' : '#639922';
  try {
    chartCache[cid] = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map((_, i) => i),
        datasets: [{ data, borderColor: barColor, borderWidth: 2, fill: true, backgroundColor: barColor + '22', tension: 0.4, pointRadius: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { display: false },
          y: { display: true, min: 0, max: z.gasThresh + 10, grid: { display: false }, ticks: { font: { size: 9 }, color: '#888', maxTicksLimit: 3 } }
        }
      }
    });
  } catch {}
}

// ---- LLM Explanation ----

async function fetchLLMExplanation(zid) {
  const box = document.getElementById('llmBox-' + zid);
  if (!box) return;
  try {
    const data = await apiFetch('/api/zones/' + zid + '/explain');
    let html = '<div style="margin-bottom:6px">' + data.explanation.replace(/\n/g, '<br>') + '</div>';
    if (data.regulatory_citations && data.regulatory_citations.length) {
      data.regulatory_citations.forEach(reg => {
        html += '<div class="reg-citation"><strong>' + reg.standard + ' ' + reg.section + ':</strong> ' + reg.text + '</div>';
      });
    }
    box.innerHTML = html;
  } catch {
    box.innerHTML = '<div style="color:var(--color-text-secondary)">Risk explanation unavailable (API offline).</div>';
  }
}

// ---- Near Miss ----

async function fetchNearMisses(zid) {
  const box = document.getElementById('nearMissBox-' + zid);
  if (!box) return;
  try {
    const data = await apiFetch('/api/zones/' + zid + '/near-misses');
    if (data.insight) {
      box.innerHTML = '<div class="near-miss-card pattern-critical">' +
        '<div class="nm-title">\u26A0 Pattern Match Found</div>' +
        '<div style="color:var(--color-text-primary)">' + data.insight + '</div></div>';
    } else {
      box.innerHTML = '<div style="font-size:12px;color:var(--color-text-secondary);padding:8px 0">No matching historical near-misses for current conditions.</div>';
    }
    if (data.matches && data.matches.length) {
      let extra = '';
      data.matches.slice(1).forEach(m => {
        extra += '<div class="near-miss-card pattern-warning" style="margin-top:4px">' +
          '<div class="nm-title">' + m.id + ' \u2014 ' + m.zone_name + ' (' + m.date + ')</div>' +
          '<div style="color:var(--color-text-primary);font-size:11px">' + m.description.slice(0, 120) + '...</div></div>';
      });
      if (extra) box.innerHTML += '<div style="margin-top:4px">' + extra + '</div>';
    }
  } catch {
    box.innerHTML = '<div style="font-size:12px;color:var(--color-text-secondary);padding:8px 0">Historical pattern matching unavailable (API offline).</div>';
  }
}

export function destroySparklineCharts(chartCache) {
  Object.keys(chartCache).forEach(k => { try { chartCache[k].destroy(); } catch {} });
}

export { sparklineCharts };
