const API = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? 'http://localhost:8000' : window.location.origin;

const WS_URL = API.replace(/^http/, 'ws') + '/ws';

const WS_MAX_RETRIES = 5;
const WS_RETRY_BASE_MS = 3000;

let ws = null;
let wsReconnectTimer = null;
let wsRetryCount = 0;
let onDashboardUpdate = null;
let onConnectionChange = null;
let isConnected = false;

function setConnected(val) {
  isConnected = val;
  if (onConnectionChange) onConnectionChange(val);
}

// ---- REST API ----

export async function apiFetch(path, opts = {}) {
  try {
    const resp = await fetch(API + path, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...opts.headers },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    setConnected(true);
    return await resp.json();
  } catch (e) {
    setConnected(false);
    throw e;
  }
}

// ---- WebSocket ----

export function connectWebSocket(handlers) {
  if (handlers.onDashboard) onDashboardUpdate = handlers.onDashboard;
  if (handlers.onConnectionChange) onConnectionChange = handlers.onConnectionChange;

  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setConnected(true);
      wsRetryCount = 0;
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'init' || msg.type === 'dashboard') {
          if (onDashboardUpdate) onDashboardUpdate(msg.data);
        } else if (msg.type === 'ping') {
          ws.send(JSON.stringify({ action: 'pong' }));
        }
      } catch (e) {
        console.warn('[ws] parse error', e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      scheduleReconnect(handlers);
    };

    ws.onerror = () => {
      ws?.close();
    };
  } catch (e) {
    setConnected(false);
    scheduleReconnect(handlers);
  }
}

function scheduleReconnect(handlers) {
  if (wsReconnectTimer) return;
  wsRetryCount++;
  if (wsRetryCount > WS_MAX_RETRIES) {
    console.warn('[ws] Max retries reached, stopping WebSocket reconnect');
    return;
  }
  const delay = WS_RETRY_BASE_MS * Math.min(wsRetryCount, 5);
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWebSocket(handlers);
  }, delay);
}

export function wsSend(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

export function disconnectWebSocket() {
  wsRetryCount = 0;
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
}

export function isWsConnected() {
  return ws && ws.readyState === WebSocket.OPEN;
}
