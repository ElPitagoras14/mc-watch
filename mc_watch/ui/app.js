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
    title: $('title'),
    sectionTitle: $('section-title'),
    list: $('list'),
    servers: $('servers'),
    empty: $('empty'),
    emptyMsg: $('empty-msg'),
    emptyHint: $('empty-hint'),
    configPath: $('config-path'),
    updated: $('updated'),
    version: $('version'),
    refresh: $('btn-refresh'),
    add: $('btn-add'),
    back: $('btn-back'),
    pin: $('btn-pin'),
    close: $('btn-close'),
    form: $('add-form'),
    notice: $('form-notice'),
    noticePath: $('notice-path'),
    name: $('f-name'),
    address: $('f-address'),
    errName: $('err-name'),
    errAddress: $('err-address'),
    formMsg: $('form-msg'),
    cancel: $('f-cancel'),
    submit: $('f-submit'),
  };

  const REFRESH_TIMEOUT_MS = 15000;

  const state = {
    updatedAt: null,
    refreshing: false, // a manual cycle was requested and its result has not arrived
    refreshFrom: null,
    refreshTimer: null,
    pinned: false,
    lastHeight: 0,
    view: 'list', // 'list' | 'form'
    busy: false, // an add-server call is in flight
    payload: null, // last payload rendered
  };

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
    if (server.edition === 'bedrock' || server.edition === 'unknown') {
      const edition = document.createElement('span');
      edition.className = `edition ${server.edition}`;
      edition.textContent = server.edition === 'bedrock' ? ' · Bedrock' : ' · edición desconocida';
      address.append(edition);
    }
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

  // Height the panel would have if nothing were clipped: its own padding and border, plus every
  // visible child with its margins (flex items' margins do not collapse). The list counts in full.
  function naturalHeight() {
    const px = (value) => parseFloat(value) || 0;
    const own = getComputedStyle(el.app);
    let total = px(own.paddingTop) + px(own.paddingBottom)
      + px(own.borderTopWidth) + px(own.borderBottomWidth);
    for (const child of el.app.children) {
      if (child.hidden) continue;
      const style = getComputedStyle(child);
      const height = child === el.list ? child.scrollHeight : child.offsetHeight;
      total += height + px(style.marginTop) + px(style.marginBottom);
    }
    return Math.ceil(total);
  }

  // The window height follows the content: Python clamps it to its min/max.
  function reportHeight() {
    const natural = naturalHeight();
    if (natural === state.lastHeight) return;
    state.lastHeight = natural;
    const api = bridge();
    if (api) api.resize(natural);
  }

  const scheduleHeight = () => requestAnimationFrame(reportHeight);

  function renderEmpty(payload) {
    const broken = Boolean(payload.config_error);
    el.emptyMsg.textContent = broken
      ? 'El archivo de configuración tiene un error.'
      : 'No hay servidores configurados.';
    el.emptyMsg.title = payload.config_error || '';
    el.emptyHint.textContent = broken
      ? 'Corrígelo para poder agregar servidores:'
      : 'Usa el botón + para agregar uno.';
    el.configPath.textContent = payload.config_path;
    el.configPath.hidden = !broken;
  }

  function render(payload) {
    state.payload = payload;
    // Only a finished cycle moves `updated_at`; adding a server keeps it.
    if (state.refreshing && payload.updated_at !== state.refreshFrom) setRefreshing(false);
    state.updatedAt = payload.updated_at;
    el.version.textContent = payload.version;

    el.servers.replaceChildren(...payload.servers.map(buildRow));
    el.empty.hidden = payload.servers.length > 0;
    renderEmpty(payload);

    // The form keeps what the user typed; only its config notice follows the payload.
    const broken = Boolean(payload.config_error);
    el.notice.hidden = !broken;
    el.noticePath.textContent = payload.config_path;
    el.submit.disabled = broken || state.busy;

    updateFooter();
    scheduleHeight();
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

  // --- Manual refresh ------------------------------------------------------

  function setRefreshing(on) {
    state.refreshing = on;
    clearTimeout(state.refreshTimer);
    el.refresh.disabled = on;
    el.refresh.classList.toggle('busy', on);
    el.refresh.setAttribute('aria-busy', String(on));
    if (on) state.refreshTimer = setTimeout(() => setRefreshing(false), REFRESH_TIMEOUT_MS);
  }

  function refresh() {
    if (state.refreshing) return;
    state.refreshFrom = state.updatedAt;
    setRefreshing(true);
    const api = bridge();
    if (api) api.refresh();
    else if (window.__MCW_PREVIEW__) previewRefresh();
  }

  // Preview only: pretend a cycle ran.
  function previewRefresh() {
    setTimeout(() => render({ ...state.payload, updated_at: Date.now() / 1000 }), 800);
  }

  // --- Add-server form -----------------------------------------------------

  function clearErrors() {
    for (const node of [el.errName, el.errAddress, el.formMsg]) {
      node.hidden = true;
      node.textContent = '';
    }
    el.name.removeAttribute('aria-invalid');
    el.address.removeAttribute('aria-invalid');
  }

  function resetForm() {
    el.form.reset();
    clearErrors();
  }

  function setBusy(busy) {
    state.busy = busy;
    el.name.disabled = busy;
    el.address.disabled = busy;
    el.cancel.disabled = busy;
    el.submit.disabled = busy || Boolean(state.payload && state.payload.config_error);
    el.submit.textContent = busy ? 'Detectando…' : 'Agregar';
  }

  function showView(view) {
    state.view = view;
    const form = view === 'form';
    el.title.textContent = form ? 'Agregar servidor' : 'MC Watch';
    el.back.hidden = !form;
    el.refresh.hidden = form;
    el.add.hidden = form;
    el.sectionTitle.hidden = form;
    el.list.hidden = form;
    el.form.hidden = !form;
    if (form) el.address.focus();
    scheduleHeight();
  }

  function openForm() {
    resetForm();
    showView('form');
  }

  function closeForm() {
    if (state.busy) return;
    resetForm();
    showView('list');
  }

  function showError(reply) {
    const target = { name: [el.errName, el.name], address: [el.errAddress, el.address] }[reply.field];
    if (target) {
      target[0].textContent = reply.message;
      target[0].hidden = false;
      target[1].setAttribute('aria-invalid', 'true');
      target[1].focus();
    } else {
      el.formMsg.textContent = reply.message;
      el.formMsg.hidden = false;
    }
  }

  async function submitForm(event) {
    event.preventDefault();
    if (state.busy || el.submit.disabled) return;
    clearErrors();
    setBusy(true);
    let reply;
    try {
      reply = await addServer(el.name.value, el.address.value);
    } catch (error) {
      reply = { ok: false, field: null, message: 'No se pudo agregar el servidor' };
    }
    setBusy(false);
    if (reply.ok) {
      resetForm();
      showView('list');
    } else {
      showError(reply);
      scheduleHeight();
    }
  }

  async function addServer(name, address) {
    const api = bridge();
    if (api) return api.add_server(name, address);
    if (window.__MCW_PREVIEW__) return previewAddServer(name, address);
    throw new Error('sin conexión con la app');
  }

  // Preview only: no network and nothing is saved. `.invalid` hosts fail to resolve, an address
  // containing "unknown" is saved with an unknown edition, "bedrock" answers as Bedrock.
  async function previewAddServer(name, address) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const host = address.trim();
    const existing = state.payload.servers.map((s) => s.address.toLowerCase());
    if (!host) return { ok: false, field: 'address', message: 'La dirección es obligatoria' };
    if (existing.includes(host.toLowerCase())) {
      return { ok: false, field: 'address', message: 'Ese servidor ya está en la lista' };
    }
    if (/\.invalid(:\d+)?$/i.test(host)) {
      return { ok: false, field: 'address', message: 'No se encontró el host' };
    }
    const unknown = /unknown/i.test(host);
    const bedrock = /bedrock/i.test(host);
    const server = {
      name: name.trim() || host,
      address: host,
      edition: unknown ? 'unknown' : bedrock ? 'bedrock' : 'java',
      state: unknown ? 'querying' : 'online',
      online: unknown ? null : 0,
      max: unknown ? null : 20,
    };
    render({ ...state.payload, servers: [...state.payload.servers, server] });
    return { ok: true };
  }

  // --- Preview and startup -------------------------------------------------

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

  el.refresh.addEventListener('click', refresh);
  el.add.addEventListener('click', openForm);
  el.back.addEventListener('click', closeForm);
  el.cancel.addEventListener('click', closeForm);
  el.form.addEventListener('submit', submitForm);
  el.pin.addEventListener('click', togglePin);
  el.close.addEventListener('click', hide);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      // In the form, Escape goes back to the list; hiding the panel there would lose the context.
      if (state.view === 'form' && !state.busy) closeForm();
      else hide();
    }
    if (event.key === 'Tab') document.body.classList.add('kbd');
  });
  document.addEventListener('pointerdown', () => document.body.classList.remove('kbd'));
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
