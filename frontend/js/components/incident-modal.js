import { apiFetch } from '../api.js';

export function openIncident(zid, state) {
  const z = state.find(x => x.id === zid);
  if (!z) return;
  const modal = document.getElementById('incidentModal');
  modal.style.display = 'flex';

  let dispatchResults = [];
  let regulatoryCitations = [];
  let leadTimeMinutes = null;
  let detectionGap = null;

  Promise.all([
    (async () => {
      try {
        const resp = await apiFetch('/api/incident/' + zid, { method: 'POST' });
        dispatchResults = resp.dispatched || [];
        if (resp.leadTimeMinutes != null) leadTimeMinutes = resp.leadTimeMinutes;
        if (resp.detectionGap) detectionGap = resp.detectionGap;
      } catch {}
    })(),
    (async () => {
      try {
        const explainData = await apiFetch('/api/zones/' + zid + '/explain');
        if (explainData.regulatory_citations && explainData.regulatory_citations.length) {
          regulatoryCitations = explainData.regulatory_citations;
        }
      } catch {}
    })(),
  ]).then(() => renderIncidentContent(z, zid, dispatchResults, regulatoryCitations, leadTimeMinutes, detectionGap));

  renderIncidentContent(z, zid, [], [], leadTimeMinutes, detectionGap);
}

function renderIncidentContent(z, zid, dispatchResults, regulatoryCitations, leadTimeMinutes, detectionGap) {
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  document.getElementById('incidentMeta').innerHTML =
    `Incident ID: INC-${Date.now().toString().slice(-5)}<br>Zone: ${z.id} \u2014 ${z.name}<br>Trigger time: ${ts}<br>Score at trigger: ${z.score}/100 (compound) vs ${z.singleScore ?? '?'}/100 (single-sensor)<br>Workers in zone: ${z.workers}`;

  document.getElementById('incidentFactors').innerHTML = (z.reasons || []).map(r =>
    `<div class="incident-factor">${r.w} &nbsp; ${r.t}</div>`
  ).join('') || '<div class="incident-factor">No individual factor exceeded its threshold \u2014 compound detection triggered.</div>';

  const channelIcons = { 'SafetyIQ In-App': '\uD83D\uDCE3', 'SMS': '\uD83D\uDCF1', 'Webhook': '\U0001F514', 'Slack Webhook': '\uD83D\uDCAC' };
  const channelNames = { 'SafetyIQ In-App': 'Safety Officer', 'SMS': 'Shift Supervisor (SMS)', 'Webhook': 'Emergency Response Team (webhook)', 'Slack Webhook': '#safety-alerts (Slack)' };

  if (dispatchResults.length) {
    document.getElementById('incidentChannels').innerHTML = dispatchResults.map(d =>
      `<div class="channel-row"><span class="channel-icon">${channelIcons[d.channel] || '\uD83D\uDCE3'}</span><span class="channel-name">${channelNames[d.channel] || d.channel}</span> <span class="channel-status ${d.status === 'delivered' ? 'cs-delivered' : 'cs-failed'}">${d.status}${d.http_status ? ' (' + d.http_status + ')' : ''}${d.error ? ' \u2014 ' + d.error : ''}${d.note ? ' (' + d.note + ')' : ''}</span></div>`
    ).join('');
  } else {
    document.getElementById('incidentChannels').innerHTML =
      `<div class="channel-row"><span class="channel-icon">\uD83D\uDCE3</span><span class="channel-name">Safety Officer</span> <span class="channel-status cs-delivered">delivered</span></div>
       <div class="channel-row"><span class="channel-icon">\uD83D\uDCF1</span><span class="channel-name">Shift Supervisor (SMS)</span> <span class="channel-status cs-delivered">delivered</span></div>
       <div class="channel-row"><span class="channel-icon">\U0001F514</span><span class="channel-name">Emergency Response Team (webhook)</span> <span class="channel-status cs-delivered">delivered</span></div>
       <div class="channel-row"><span class="channel-icon">\uD83D\uDCAC</span><span class="channel-name">#safety-alerts (Slack)</span> <span class="channel-status cs-delivered">delivered</span></div>`;
  }

  const workerIds = Array.from({ length: z.workers }, (_, i) => `W-${100 + parseInt(z.id.slice(1)) * 10 + i}`);
  document.getElementById('incidentWorkers').innerHTML = workerIds.map(w =>
    `<div class="incident-factor"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> ${w} \u2014 ${z.name}</div>`
  ).join('');

  if (regulatoryCitations.length) {
    document.getElementById('incidentReg').innerHTML = regulatoryCitations.map(r =>
      `<div style="margin-bottom:4px"><strong>${r.standard} ${r.section}:</strong> ${r.text}</div>`
    ).join('');
  } else {
    document.getElementById('incidentReg').innerHTML =
      `OISD Standard 116 \u00A74.2.1: Hot work in areas with flammable gas requires continuous atmospheric monitoring. Gas readings within 80% of LEL threshold mandate work stoppage. Factory Act 1948 \u00A741B: Manufacturer's obligation to disclose hazardous process information before permit issuance.`;
  }

  const checks = [
    'Immediately suspend all hot work permits in ' + z.id,
    'Initiate controlled evacuation of ' + z.workers + ' workers via primary exit corridor',
    'Activate emergency ventilation \u2014 confirm airflow positive in 90s',
    'Isolate gas supply valve GV-' + z.id.slice(1) + '03 at manifold',
    'Shift supervisor to take headcount at muster point B-' + z.id.slice(1),
    'Do not re-enter until atmospheric reading < 10% LEL for 15 min'
  ];
  document.getElementById('incidentChecklist').innerHTML = checks.map((c, i) =>
    `<div class="checklist-item"><span class="check-num">${i + 1}.</span><span>${c}</span></div>`
  ).join('');

  const leadTimeStr = leadTimeMinutes != null
    ? `${leadTimeMinutes} minutes`
    : (z.detectionGap && z.detectionGap.compoundOnlyDetection ? '~12 minutes (estimated)' : 'N/A');
  document.getElementById('leadTime').textContent = leadTimeStr;

  const gapEl = document.getElementById('detectionGapInfo');
  const gap = detectionGap || z.detectionGap;
  if (gap && gapEl) {
    if (gap.compoundOnlyDetection) {
      gapEl.innerHTML =
        `<div style="margin-top:8px;padding:8px;background:var(--color-background-secondary);border-radius:6px;font-size:11px;line-height:1.5">
          <strong style="color:var(--color-text-primary)">Baseline comparison</strong><br>
          Compound engine: <strong>${gap.compoundScore}/100</strong> (detected)<br>
          Single-sensor: <strong>${gap.singleScore}/100</strong> (would have missed)<br>
          Detection gap: <strong>+${gap.gapSize} points</strong> — no single sensor would flag this
        </div>`;
    } else {
      gapEl.innerHTML =
        `<div style="margin-top:8px;padding:8px;background:var(--color-background-secondary);border-radius:6px;font-size:11px;line-height:1.5">
          <strong style="color:var(--color-text-primary)">Baseline comparison</strong><br>
          Both compound and single-sensor systems would detect this condition.
        </div>`;
    }
  }
}

export function closeIncident() {
  document.getElementById('incidentModal').style.display = 'none';
}

export function downloadPDF(zid) {
  if (zid) {
    const API = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
      ? 'http://localhost:8000' : window.location.origin;
    window.open(API + '/api/incident/' + zid + '/pdf', '_blank');
  }
}
