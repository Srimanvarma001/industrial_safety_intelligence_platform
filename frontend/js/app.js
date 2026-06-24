import { apiFetch, connectWebSocket, disconnectWebSocket, isWsConnected, wsSend } from './api.js';
import { recalcLocalScores, computeScore, getRiskLabel } from './risk-engine.js';
import { renderGrid } from './components/zone-grid.js';
import { showZoneDetail, destroySparklineCharts, sparklineCharts } from './components/zone-detail.js';
import { renderAlerts } from './components/alert-feed.js';
import { openIncident, closeIncident, downloadPDF } from './components/incident-modal.js';
import { DEFAULT_ZONES } from './constants.js';

// ---- State ----

let state = [];
let selectedZone = null;
let alerts = [];
let scenarioActive = false;
let incidentFired = false;
let simTime = new Date();
let currentIncidentZone = null;
let restPollInterval = null;
let clockInterval = null;

// ---- Expose to global for inline event handlers ----

window.__onWhatIfChange = onWhatIfChange;
window.__openIncident = (zid) => {
  currentIncidentZone = zid;
  openIncident(zid, state);
};
window.closeIncident = closeIncident;
window.downloadPDF = () => {
  if (currentIncidentZone) downloadPDF(currentIncidentZone);
};

// ---- Init ----

async function init() {
  // Try WebSocket first
  connectWebSocket({
    onDashboard: onDashboardWS,
    onConnectionChange: onConnectionChange,
  });

  // Fallback: REST polling if WebSocket fails
      await loadDashboardREST();
  renderAlerts(alerts);
  addAlert('Platform online', 'All 8 zones connected \u2014 sensor streams active', 'green');
  document.getElementById('loadingDetail').style.display = 'none';
  document.getElementById('noZoneMsg').style.display = '';

  restPollInterval = setInterval(async () => {
    if (isWsConnected()) return;
    try {
      await apiFetch('/api/tick', { method: 'POST' });
      await loadDashboardREST();
      await fetchAlerts();
    } catch {
      localTick();
    }
  }, 3000);

  clockInterval = setInterval(() => {
    simTime = new Date(simTime.getTime() + 15000);
    updateClock();
  }, 1000);
}

// ---- WebSocket handler ----

function onDashboardWS(data) {
  state = data.zones || [];
  simTime = new Date(data.timestamp || Date.now());
  updateMetrics(data.metrics);
  renderGrid(state, selectedZone, selectZone);
  if (selectedZone) {
    const z = state.find(x => x.id === selectedZone);
    if (z) showZoneDetail(selectedZone, state, currentIncidentZone);
  }
}

function onConnectionChange(connected) {
  const el = document.getElementById('connStatus');
  if (connected) {
    el.className = 'conn-status conn-online';
    el.textContent = '\u25CF WebSocket';
  } else {
    el.className = 'conn-status conn-offline';
    el.textContent = '\u26A0 Polling';
  }
}

// ---- REST fallback ----

async function loadDashboardREST() {
  try {
    const data = await apiFetch('/api/dashboard');
    state = data.zones;
    simTime = new Date(data.timestamp);
    updateMetrics(data.metrics);
    renderGrid(state, selectedZone, selectZone);
    if (selectedZone) {
      const z = state.find(x => x.id === selectedZone);
      if (z) showZoneDetail(selectedZone, state, currentIncidentZone);
    }
    return data;
  } catch {
    return fallbackLocalData();
  }
}

function fallbackLocalData() {
  if (state.length) return { zones: state };
  state = DEFAULT_ZONES.map(z => ({ ...z, currentGas: z.baseGas, gasHistory: [z.baseGas], score: 0, reasons: [] }));
  recalcLocalScores(state);
  renderGrid(state, selectedZone, selectZone);
  updateMetrics();
  document.getElementById('loadingDetail').style.display = 'none';
  document.getElementById('noZoneMsg').style.display = '';
  return { zones: state };
}

function localTick() {
  if (!state.length) return;
  state.forEach(z => {
    const noise = (Math.random() - 0.5) * 4;
    z.currentGas = Math.max(0, (z.currentGas || z.baseGas) + noise);
    if (!z.gasHistory) z.gasHistory = [z.baseGas];
    z.gasHistory.push(Math.round(z.currentGas));
    if (z.gasHistory.length > 12) z.gasHistory.shift();
  });
  recalcLocalScores(state);
  renderGrid(state, selectedZone, selectZone);
  updateMetrics();
  if (selectedZone) showZoneDetail(selectedZone, state, currentIncidentZone);
}

// ---- Select zone ----

function selectZone(id) {
  selectedZone = id;
  renderGrid(state, selectedZone, selectZone);
  showZoneDetail(id, state, currentIncidentZone);
}

// ---- Metrics ----

function updateMetrics(metrics) {
  if (!metrics && state.length) {
    const maxZ = state.reduce((a, b) => a.score > b.score ? a : b);
    metrics = {
      zonesMonitored: state.length,
      workersOnFloor: state.reduce((s, z) => s + z.workers, 0),
      activeAlerts: state.filter(z => z.score >= 61).length,
      highestRiskZone: maxZ.id,
      highestRiskScore: maxZ.score,
    };
  }
  if (!metrics) return;
  document.getElementById('m-zones').textContent = metrics.zonesMonitored ?? '\u2014';
  document.getElementById('m-workers').textContent = metrics.workersOnFloor ?? '\u2014';
  document.getElementById('m-alerts').textContent = metrics.activeAlerts ?? 0;
  document.getElementById('m-alerts').style.color = (metrics.activeAlerts || 0) > 0 ? '#E24B4A' : 'var(--color-text-primary)';
  document.getElementById('m-topzone').textContent = metrics.highestRiskZone ?? '\u2014';
  document.getElementById('m-topscore').textContent = 'score: ' + (metrics.highestRiskScore ?? '\u2014');
}

// ---- Alerts ----

function addAlert(title, desc, type) {
  const timeStr = new Date().toISOString().slice(11, 19) + 'Z';
  alerts.unshift({ title, desc, time: timeStr, type });
  if (alerts.length > 20) alerts.pop();
  renderAlerts(alerts);
}

async function fetchAlerts() {
  try {
    const data = await apiFetch('/api/alerts');
    if (data.alerts && data.alerts.length) {
      const existingIds = new Set(alerts.map(a => a.id).filter(Boolean));
      data.alerts.forEach(a => {
        if (!existingIds.has(a.id)) {
          alerts.push({
            id: a.id,
            title: a.title,
            desc: a.description,
            time: a.timestamp ? a.timestamp.slice(11, 19) + 'Z' : new Date().toISOString().slice(11, 19) + 'Z',
            type: a.type === 'red' ? 'red' : a.type === 'green' ? 'green' : a.type === 'yellow' ? 'yellow' : 'blue',
          });
        }
      });
      if (alerts.length > 20) alerts.splice(20);
      renderAlerts(alerts);
    }
  } catch {}
}

// ---- What-If ----

function onWhatIfChange(zid) {
  const slider = document.getElementById('whatifSlider-' + zid);
  const valDisplay = document.getElementById('whatifVal-' + zid);
  const resultBox = document.getElementById('whatifResult-' + zid);
  if (!slider || !valDisplay || !resultBox) return;

  const newGas = parseFloat(slider.value);
  valDisplay.textContent = newGas + ' ppm';

  const z = state.find(x => x.id === zid);
  if (!z) return;

  const result = computeScore({ ...z, currentGas: newGas }, z.gasHistory);
  const color = result.score >= 61 ? '#E24B4A' : result.score >= 31 ? '#EF9F27' : '#639922';
  resultBox.style.background = color + '22';
  resultBox.style.color = color;
  resultBox.textContent = 'Score: ' + result.score + '/100 \u2014 ' + getRiskLabel(result.score);
}

// ---- Scenario ----

window.triggerScenario = async function triggerScenario() {
  if (scenarioActive) return;
  scenarioActive = true;
  incidentFired = false;
  document.getElementById('scenarioBtn').disabled = true;
  document.getElementById('scenarioBtn').textContent = 'Scenario running...';

  try {
    const data = await apiFetch('/api/scenario/trigger', { method: 'POST' });
    addAlert('Vizag Scenario triggered', 'Scripted compound risk sequence started on Z3', 'yellow');
    if (data.steps) {
      for (const step of data.steps) {
        if (step.action === 'orchestrator_fired') {
          addAlert('COMPOUND RISK THRESHOLD BREACHED', 'Z3 risk score crossed 80 \u2014 no single sensor flagged this', 'red');
          setTimeout(async () => {
            if (!incidentFired) {
              incidentFired = true;
              addAlert('Emergency Response Orchestrator fired', 'Incident report generated \u00B7 Alerts dispatched \u00B7 Checklist surfaced', 'blue');
              addAlert('Evidence snapshot frozen', 'Sensor readings, permits, worker locations locked at trigger time', 'blue');
              setTimeout(() => {
                currentIncidentZone = 'Z3';
                openIncident('Z3', state);
              }, 500);
            }
          }, 1000);
        }
      }
    }
    await loadDashboardREST();
    selectZone('Z3');
    document.getElementById('scenarioBtn').textContent = 'Scenario complete';
  } catch {
    runLocalScenario();
  }
};

function runLocalScenario() {
  let z3 = state.find(x => x.id === 'Z3');
  if (!z3) return;
  let step = 0;
  const steps = [
    () => { z3.permit = 'hot_work'; addAlert('PTW-2291 issued', 'Hot work permit activated \u2014 Zone Z3', 'yellow'); },
    () => { z3.currentGas = 41; z3.gasTrending = true; addAlert('Gas trend detected', 'CO readings rising in Z3 \u2014 41 ppm', 'yellow'); },
    () => { z3.maintenance = 'confined_space_entry'; z3.workers = 8; addAlert('Maintenance crew entered', 'Confined space entry started \u2014 Z3', 'yellow'); },
    () => { z3.changeover = true; addAlert('Shift changeover window open', 'Supervisor handoff in progress', 'yellow'); },
    () => { z3.currentGas = 48; recalcLocalScores(state); addAlert('COMPOUND RISK BREACHED', 'Z3 risk score crossed', 'red'); },
    () => {
      if (!incidentFired) {
        incidentFired = true;
        addAlert('Orchestrator fired', 'Incident report generated', 'blue');
        setTimeout(() => {
          currentIncidentZone = 'Z3';
          openIncident('Z3', state);
        }, 500);
      }
    },
    () => { document.getElementById('scenarioBtn').textContent = 'Scenario complete'; },
  ];

  const intrvl = setInterval(() => {
    if (step < steps.length) {
      steps[step]();
      step++;
      recalcLocalScores(state);
      renderGrid(state, selectedZone, selectZone);
      updateMetrics();
      selectZone('Z3');
    } else {
      clearInterval(intrvl);
    }
  }, 2500);
}

// ---- Reset ----

window.resetSim = async function resetSim() {
  scenarioActive = false;
  incidentFired = false;
  selectedZone = null;
  currentIncidentZone = null;
  document.getElementById('scenarioBtn').disabled = false;
  document.getElementById('scenarioBtn').textContent = '\u25B6 Vizag Scenario';
  destroySparklineCharts(sparklineCharts);
  closeIncident();
  alerts = [];
  renderAlerts(alerts);
  try {
    await apiFetch('/api/reset', { method: 'POST' });
  } catch {}
  await loadDashboardREST();
  document.getElementById('noZoneMsg').style.display = '';
  document.getElementById('zoneDetail').style.display = 'none';
  document.getElementById('loadingDetail').style.display = 'none';
};

// ---- Clock ----

function updateClock() {
  document.getElementById('clock').textContent = simTime.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

// ---- Go ----

init();
