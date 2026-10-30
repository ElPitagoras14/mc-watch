(() => {
  'use strict';

  const STATE_LABELS = {
    querying: 'Consultando',
    online: 'Online',
    offline: 'Offline',
    error: 'Error',
  };

  const $ = (id) => document.getElementById(id);
  const el = {
    app: $('app'),
    list: $('list'),
    servers: $('servers'),
    empty: $('empty'),
    configPath: $('config-path'),
    updated: $('updated'),
    version: $('version'),
    pin: $('btn-pin'),
    close: $('btn-close'),
  };

  const state = { updatedAt: null, pinned: false, lastHeight: 0 };

  // Python side (pywebview). Absent when the page runs in a plain browser (preview).
  const bridge = () => (window.pywebview && window.pywebview.api) || null;

  function formatAge(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    if (s < 60) return `${s} s`;
    if (s < 3600) return `${Math.floor(s / 60)} min`;
    return `${Math.floor(s / 3600)} h`;
  }

  function updateFooter() {
    el.updated.textContent = state.updatedAt === null
      ? 'Actualizando…'
      : `Actualizado hace ${formatAge(Date.now() / 1000 - state.updatedAt)}`;
  }

  function buildRow(server) {
    const row = document.createElement('li');
    row.className = 'server';

    const info = document.createElement('div');
    info.className = 'info';
    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = server.name;
    name.title = server.name;
    const address = document.createElement('div');
    address.className = 'address';
    address.textContent = server.address;
    address.title = server.address;
    info.append(name, address);

    const meta = document.createElement('div');
    meta.className = 'meta';
    const status = document.createElement('div');
    status.className = 'status';
    status.dataset.state = server.state;
    const label = document.createElement('span');
    label.textContent = STATE_LABELS[server.state] || server.state;
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.setAttribute('aria-hidden', 'true');
    status.append(label, dot);
    const players = document.createElement('div');
    players.className = 'players';
    players.textContent = server.state === 'online' && server.online !== null
      ? `${server.online}/${server.max}`
      : '—';
    meta.append(status, players);

    row.append(info, meta);
    return row;
  }

  // The window height follows the content: Python clamps it to its min/max.
  function reportHeight() {
    let natural = 2; // the panel border
    for (const child of el.app.children) {
      natural += child === el.list ? child.scrollHeight : child.offsetHeight;
    }
    natural = Math.ceil(natural);
    if (natural === state.lastHeight) return;
    state.lastHeight = natural;
    const api = bridge();
    if (api) api.resize(natural);
  }

  function render(payload) {
    state.updatedAt = payload.updated_at;
    el.version.textContent = payload.version;
    el.configPath.textContent = payload.config_path;

    el.servers.replaceChildren(...payload.servers.map(buildRow));
    el.empty.hidden = payload.servers.length > 0;

    updateFooter();
    requestAnimationFrame(reportHeight);
  }

  function setPinned(pinned) {
    state.pinned = pinned;
    el.pin.setAttribute('aria-pressed', String(pinned));
    el.pin.title = pinned ? 'Desfijar panel' : 'Fijar panel';
    el.pin.setAttribute('aria-label', el.pin.title);
  }

  async function togglePin() {
    const api = bridge();
    setPinned(api ? await api.toggle_pin() : !state.pinned);
  }

  function hide() {
    const api = bridge();
    if (api) api.hide();
  }

  function initPreview(scenarios) {
    document.body.classList.add('preview');
    const bar = document.createElement('div');
    bar.id = 'preview-bar';
    const buttons = scenarios.map((scenario) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = scenario.label;
      button.addEventListener('click', () => {
        buttons.forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
        render(scenario.payload);
      });
      return button;
    });
    bar.append(...buttons);
    el.app.after(bar);
    // `#2` in the URL opens the third scenario directly.
    const start = Number(window.location.hash.slice(1)) || 0;
    buttons[Math.min(start, buttons.length - 1)].click();
  }

  function loadFromPython() {
    const api = bridge();
    if (api) api.get_snapshot().then(render);
  }

  el.pin.addEventListener('click', togglePin);
  el.close.addEventListener('click', hide);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hide();
  });
  window.addEventListener('blur', () => {
    const api = bridge();
    if (api) api.on_blur();
  });

  window.mcw = { render };
  setInterval(updateFooter, 1000);

  if (window.__MCW_PREVIEW__) {
    initPreview(window.__MCW_PREVIEW__);
  } else if (bridge()) {
    loadFromPython();
  } else {
    window.addEventListener('pywebviewready', loadFromPython);
  }
})();
