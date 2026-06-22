export function renderAlerts(alerts) {
  const list = document.getElementById('alertList');
  if (!alerts.length) {
    list.innerHTML = '<div style="font-size:13px;color:var(--color-text-secondary);padding:8px 0">No events yet</div>';
    return;
  }
  list.innerHTML = alerts.map(a =>
    `<div class="alert-item"><div class="alert-dot dot-${a.type}"></div><div class="alert-content"><div class="alert-title">${a.title}</div><div class="alert-desc">${a.desc}</div><div class="alert-time">${a.time}</div></div></div>`
  ).join('');
}
