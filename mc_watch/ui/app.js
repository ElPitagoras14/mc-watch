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
    titleInput: $('title-input'),
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
    del: $('btn-delete'),
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
    detail: $('detail'),
    detailErr: $('detail-err'),
    dImg: $('d-img'),
    dGlyph: $('d-glyph'),
    dMotd: $('d-motd'),
    dFacts: $('d-facts'),
    dAddress: $('d-address'),
    dState: $('d-state'),
    dNames: $('d-names'),
    dMsg: $('d-msg'),
    dCount: $('d-count'),
    confirm: $('confirm'),
    confirmMsg: $('confirm-msg'),
    confirmErr: $('confirm-err'),
    confirmCancel: $('confirm-cancel'),
    confirmOk: $('confirm-ok'),
    settingsBtn: $('btn-settings'),
    settings: $('settings'),
    settingsForm: $('settings-form'),
    sNotice: $('s-notice'),
    sNoticePath: $('s-notice-path'),
    sNotifications: $('s-notifications'),
    sInterval: $('s-interval'),
    sVisible: $('s-visible'),
    errInterval: $('err-interval'),
    errVisible: $('err-visible'),
    settingsMsg: $('settings-msg'),
    sCancel: $('s-cancel'),
    sSave: $('s-save'),
  };

  const REFRESH_TIMEOUT_MS = 15000;
  const DEFAULT_SETTINGS = { notifications: false, poll_interval_secs: 60, max_visible_servers: 8 };
  // The same limits and messages as Python's settings.py, for the preview.
  const LIMITS = {
    poll_interval_secs: [30, 3600],
    max_visible_servers: [3, 20],
  };

  const state = {
    updatedAt: null,
    refreshing: false, // a manual cycle was requested and its result has not arrived
    refreshingOne: false, // the open server is being polled
    refreshFrom: null,
    refreshTimer: null,
    pinned: false,
    lastHeight: 0,
    view: 'list', // 'list' | 'form' | 'detail'
    busy: false, // an add-server call is in flight
    detail: null, // address of the server whose detail is open
    renaming: false, // the title is an input
    confirming: false, // the delete confirmation is open
    deleting: false, // the delete call is in flight
    payload: null, // last payload rendered
    settingsOpen: false, // the settings dialog is open, over the list
    saving: false, // the save-settings call is in flight
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

  function editionLabel(edition) {
    if (edition === 'java') return 'Java';
    if (edition === 'bedrock') return 'Bedrock';
    return 'edición desconocida';
  }

  function buildRow(server) {
    const row = document.createElement('li');
    row.className = 'server';
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-label', `${server.name}, ${STATE_LABELS[server.state] || server.state}`);
    row.dataset.address = server.address;

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
    const edition = document.createElement('span');
    edition.className = `edition ${server.edition}`;
    edition.textContent = ` · ${editionLabel(server.edition)}`;
    address.append(edition);
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
  // visible child with its margins (flex items' margins do not collapse). The list and the detail
  // count in full: they are the parts that scroll.
  function naturalHeight() {
    const px = (value) => parseFloat(value) || 0;
    const own = getComputedStyle(el.app);
    let total = px(own.paddingTop) + px(own.paddingBottom)
      + px(own.borderTopWidth) + px(own.borderBottomWidth);
    for (const child of el.app.children) {
      if (child.hidden || child === el.settings) continue;
      const style = getComputedStyle(child);
      let height = child.offsetHeight;
      if (child === el.detail) height = child.scrollHeight;
      if (child === el.list) height = Math.min(child.scrollHeight, listCap() ?? Infinity);
      total += height + px(style.marginTop) + px(style.marginBottom);
    }
    return Math.ceil(Math.max(total, dialogHeight()));
  }

  // Room the settings dialog needs, or 0 when it is closed. The dialog covers the panel, so the
  // panel grows when the dialog would not fit.
  function dialogHeight() {
    if (!state.settingsOpen) return 0;
    const overlay = getComputedStyle(el.settings);
    return el.settingsForm.offsetHeight
      + parseFloat(overlay.paddingTop) + parseFloat(overlay.paddingBottom);
  }

  const settings = () => (state.payload && state.payload.settings) || DEFAULT_SETTINGS;

  // Height of the first `max_visible_servers` rows, or null when every row fits.
  function listCap() {
    const rows = el.servers.children;
    const visible = settings().max_visible_servers;
    if (rows.length <= visible) return null;
    const last = rows[visible - 1];
    const bottom = last.getBoundingClientRect().bottom + parseFloat(getComputedStyle(last).marginBottom);
    return Math.ceil(bottom - el.list.getBoundingClientRect().top + el.list.scrollTop);
  }

  function applyListCap() {
    el.list.style.maxHeight = '';
    const cap = listCap();
    if (cap !== null) el.list.style.maxHeight = `${cap}px`;
  }

  // The window height follows the content: Python clamps it to its min/max.
  function reportHeight() {
    // The overlay fills the panel, so the panel itself must be as tall as the dialog.
    const room = dialogHeight();
    el.app.style.minHeight = room ? `${Math.ceil(room)}px` : '';
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
    if (state.view === 'list') applyListCap();

    // The form keeps what the user typed; only its config notice follows the payload.
    const broken = Boolean(payload.config_error);
    el.notice.hidden = !broken;
    el.noticePath.textContent = payload.config_path;
    el.submit.disabled = broken || state.busy;
    el.sNotice.hidden = !broken;
    el.sNoticePath.textContent = payload.config_path;
    el.sSave.disabled = broken || state.saving;

    if (state.view === 'detail') {
      const server = currentServer();
      if (server) renderDetail(server);
      else leaveDetail(); // it was deleted (here or in the file)
    }

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

  function syncRefreshButton() {
    const busy = state.refreshing || state.refreshingOne;
    el.refresh.disabled = busy;
    el.refresh.classList.toggle('busy', busy);
    el.refresh.setAttribute('aria-busy', String(busy));
  }

  function setRefreshing(on) {
    state.refreshing = on;
    clearTimeout(state.refreshTimer);
    syncRefreshButton();
    if (on) state.refreshTimer = setTimeout(() => setRefreshing(false), REFRESH_TIMEOUT_MS);
  }

  // In the detail the button polls only the open server; the call returns when it is done and
  // the poller has already pushed the new data.
  async function refreshOne() {
    if (state.refreshingOne) return;
    state.refreshingOne = true;
    syncRefreshButton();
    try {
      await refreshServer(state.detail);
    } catch (error) {
      // The next cycle brings the data anyway.
    }
    state.refreshingOne = false;
    syncRefreshButton();
  }

  async function refreshServer(address) {
    const api = bridge();
    if (api) return api.refresh_server(address);
    if (window.__MCW_PREVIEW__) {
      return new Promise((resolve) => setTimeout(() => {
        render({ ...state.payload });
        resolve();
      }, 800));
    }
    throw new Error('sin conexión con la app');
  }

  function refresh() {
    if (state.view === 'detail') {
      refreshOne();
      return;
    }
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

  // --- Views ---------------------------------------------------------------

  function showView(view) {
    state.view = view;
    const list = view === 'list';
    const form = view === 'form';
    const detail = view === 'detail';
    el.back.hidden = list;
    el.refresh.hidden = form;
    el.refresh.title = detail ? 'Actualizar este servidor' : 'Actualizar ahora';
    el.refresh.setAttribute('aria-label', el.refresh.title);
    el.add.hidden = !list;
    el.settingsBtn.hidden = !list;
    el.del.hidden = !detail;
    el.sectionTitle.hidden = !list;
    el.list.hidden = !list;
    el.form.hidden = !form;
    el.detail.hidden = !detail;
    el.title.classList.toggle('editable', detail);
    el.title.tabIndex = detail ? 0 : -1;
    if (detail) {
      el.title.setAttribute('role', 'button');
      el.title.title = 'Click para renombrar';
    } else {
      el.title.removeAttribute('role');
      el.title.removeAttribute('title');
      el.title.textContent = form ? 'Agregar servidor' : 'MC Watch';
    }
    if (form) el.address.focus();
    if (list) applyListCap();
    scheduleHeight();
  }

  // Esc and the back button: one level up.
  function goBack() {
    if (state.view === 'form') closeForm();
    else if (state.view === 'detail') leaveDetail();
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
      latency_ms: unknown ? null : 20,
      version: unknown ? null : '1.21.4',
      motd: [],
      icon: null,
      players_mode: unknown ? null : 'full',
      players: [],
      asleep: false,
    };
    render({ ...state.payload, servers: [...state.payload.servers, server] });
    return { ok: true };
  }

  // --- Server detail -------------------------------------------------------

  const currentServer = () => (state.payload
    ? state.payload.servers.find((s) => s.address === state.detail) || null
    : null);

  function openDetail(address) {
    state.detail = address;
    hideDetailError();
    showView('detail');
    const server = currentServer();
    if (server) renderDetail(server);
    scheduleHeight();
  }

  function leaveDetail() {
    if (state.renaming) endRename();
    state.confirming = false;
    state.deleting = false;
    el.confirm.hidden = true;
    state.detail = null;
    hideDetailError();
    showView('list');
  }

  function hideDetailError() {
    el.detailErr.hidden = true;
    el.detailErr.textContent = '';
  }

  function showDetailError(message) {
    el.detailErr.textContent = message;
    el.detailErr.hidden = false;
    scheduleHeight();
  }

  // The MOTD is built from segments with textContent: nothing the server sends is ever parsed
  // as HTML.
  function renderMotd(segments) {
    const spans = segments.map((segment) => {
      const span = document.createElement('span');
      span.textContent = segment.text;
      if (segment.color) span.style.color = segment.color;
      if (segment.bold) span.style.fontWeight = '700';
      if (segment.italic) span.style.fontStyle = 'italic';
      const lines = [];
      if (segment.underlined) lines.push('underline');
      if (segment.strikethrough) lines.push('line-through');
      if (lines.length) span.style.textDecoration = lines.join(' ');
      return span;
    });
    el.dMotd.replaceChildren(...spans);
  }

  function renderStateMessage(server) {
    el.dState.hidden = server.state === 'online';
    if (server.state === 'online') return;
    let text = 'Consultando…';
    if (server.state === 'offline') {
      text = server.asleep
        ? 'Offline: el proveedor responde, pero el servidor está apagado.'
        : 'Offline: el servidor no responde.';
    } else if (server.state === 'error') {
      text = 'Error: no se encontró el host.';
    }
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = text;
    el.dState.dataset.state = server.state;
    el.dState.replaceChildren(dot, label);
  }

  function renderPlayers(server) {
    const names = server.players || [];
    let message = '';
    let count = '';
    let list = [];
    if (server.state !== 'online') {
      message = 'Sin datos de jugadores.';
    } else if (server.players_mode === 'hidden') {
      message = 'Este servidor no comparte la lista de jugadores';
      count = `${server.online}/${server.max}`;
    } else if (names.length === 0) {
      message = 'Nadie está jugando';
    } else {
      list = names;
      if (server.players_mode === 'partial') count = `${names.length} de ${server.online} jugadores`;
    }
    el.dNames.replaceChildren(...list.map((name) => {
      const item = document.createElement('li');
      item.textContent = name;
      return item;
    }));
    el.dMsg.textContent = message;
    el.dMsg.hidden = !message;
    el.dCount.textContent = count;
    el.dCount.hidden = !count;
  }

  function renderDetail(server) {
    if (!state.renaming) el.title.textContent = server.name;
    const online = server.state === 'online';

    el.dAddress.textContent = server.address;
    el.dAddress.title = server.address;
    if (server.icon) {
      if (el.dImg.getAttribute('src') !== server.icon) el.dImg.src = server.icon;
    } else {
      el.dImg.removeAttribute('src');
    }
    el.dImg.hidden = !server.icon;
    el.dGlyph.hidden = Boolean(server.icon);

    renderMotd(online ? server.motd : []);
    const facts = [];
    if (online && server.version) facts.push(server.version);
    if (online && server.latency_ms !== null) facts.push(`${Math.round(server.latency_ms)} ms`);
    facts.push(editionLabel(server.edition));
    el.dFacts.textContent = facts.join(' · ');

    renderStateMessage(server);
    renderPlayers(server);
    scheduleHeight();
  }

  // Row click or Enter/Space on a focused row.
  function onRowActivate(event) {
    const row = event.target.closest('.server');
    if (row && row.dataset.address) openDetail(row.dataset.address);
  }

  // --- Rename --------------------------------------------------------------

  function startRename() {
    if (state.view !== 'detail' || state.renaming || state.confirming) return;
    const server = currentServer();
    if (!server) return;
    state.renaming = true;
    hideDetailError();
    el.titleInput.value = server.name;
    el.title.hidden = true;
    el.titleInput.hidden = false;
    el.titleInput.focus();
    el.titleInput.select();
  }

  // `state.renaming` goes first: hiding the focused input fires its blur, which must not save.
  function endRename() {
    state.renaming = false;
    el.titleInput.hidden = true;
    el.title.hidden = false;
  }

  async function commitRename() {
    if (!state.renaming) return;
    const address = state.detail;
    const server = currentServer();
    const name = el.titleInput.value;
    endRename();
    if (!server || name.trim() === server.name) return;
    let reply;
    try {
      reply = await renameServer(address, name);
    } catch (error) {
      reply = { ok: false, message: 'No se pudo guardar el nombre' };
    }
    if (reply.ok) {
      hideDetailError();
      if (state.detail === address && !state.renaming) el.title.textContent = reply.name;
    } else {
      showDetailError(reply.message);
    }
  }

  async function renameServer(address, name) {
    const api = bridge();
    if (api) return api.rename_server(address, name);
    if (window.__MCW_PREVIEW__) return previewRename(address, name);
    throw new Error('sin conexión con la app');
  }

  // Preview only: a name containing "fail" simulates a config that cannot be written.
  async function previewRename(address, name) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    if (/fail/i.test(name)) return { ok: false, field: 'name', message: 'No se pudo guardar el archivo' };
    const normalized = name.trim() || address;
    const servers = state.payload.servers.map((s) => (
      s.address === address ? { ...s, name: normalized } : s));
    render({ ...state.payload, servers });
    return { ok: true, name: normalized };
  }

  // --- Delete --------------------------------------------------------------

  function openConfirm() {
    const server = currentServer();
    if (state.view !== 'detail' || state.confirming || !server) return;
    if (state.renaming) endRename();
    state.confirming = true;
    el.confirmMsg.textContent = `¿Eliminar "${server.name}"?`;
    el.confirmErr.hidden = true;
    el.confirm.hidden = false;
    scheduleHeight();
    el.confirmCancel.focus();
  }

  function closeConfirm() {
    if (state.deleting) return;
    state.confirming = false;
    el.confirm.hidden = true;
    scheduleHeight();
  }

  function setDeleting(on) {
    state.deleting = on;
    el.confirmCancel.disabled = on;
    el.confirmOk.disabled = on;
    el.confirmOk.textContent = on ? 'Eliminando…' : 'Eliminar';
  }

  async function confirmDelete() {
    if (state.deleting) return;
    const address = state.detail;
    el.confirmErr.hidden = true;
    setDeleting(true);
    let reply;
    try {
      reply = await removeServer(address);
    } catch (error) {
      reply = { ok: false, message: 'No se pudo eliminar el servidor' };
    }
    setDeleting(false);
    if (reply.ok) {
      leaveDetail();
    } else {
      el.confirmErr.textContent = reply.message;
      el.confirmErr.hidden = false;
      scheduleHeight();
    }
  }

  async function removeServer(address) {
    const api = bridge();
    if (api) return api.remove_server(address);
    if (window.__MCW_PREVIEW__) return previewRemove(address);
    throw new Error('sin conexión con la app');
  }

  // Preview only: an address containing "readonly" simulates a config that cannot be written.
  async function previewRemove(address) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    if (/readonly/i.test(address)) {
      return { ok: false, field: null, message: 'No se pudo guardar el archivo' };
    }
    render({
      ...state.payload,
      servers: state.payload.servers.filter((s) => s.address !== address),
    });
    return { ok: true };
  }

  // --- Settings dialog -----------------------------------------------------

  const settingsFields = () => ({
    poll_interval_secs: [el.errInterval, el.sInterval],
    max_visible_servers: [el.errVisible, el.sVisible],
  });

  function clearSettingsErrors() {
    for (const [node, input] of [...Object.values(settingsFields()), [el.settingsMsg, null]]) {
      node.hidden = true;
      node.textContent = '';
      if (input) input.removeAttribute('aria-invalid');
    }
  }

  // Everything but the dialog stops taking clicks and focus while it is open.
  function setInert(on) {
    for (const child of el.app.children) {
      if (child !== el.settings) child.inert = on;
    }
  }

  function openSettings() {
    if (state.settingsOpen || state.view !== 'list') return;
    const current = settings();
    el.sNotifications.checked = current.notifications;
    el.sInterval.value = String(current.poll_interval_secs);
    el.sVisible.value = String(current.max_visible_servers);
    clearSettingsErrors();
    state.settingsOpen = true;
    el.settings.hidden = false;
    setInert(true);
    scheduleHeight();
    el.sNotifications.focus();
  }

  function closeSettings() {
    if (!state.settingsOpen || state.saving) return;
    state.settingsOpen = false;
    el.settings.hidden = true;
    setInert(false);
    scheduleHeight();
  }

  function setSaving(on) {
    state.saving = on;
    for (const input of [el.sNotifications, el.sInterval, el.sVisible, el.sCancel]) {
      input.disabled = on;
    }
    el.sSave.disabled = on || Boolean(state.payload && state.payload.config_error);
    el.sSave.textContent = on ? 'Guardando…' : 'Guardar';
  }

  function showSettingsError(reply) {
    const [node, input] = settingsFields()[reply.field] || [el.settingsMsg, null];
    node.textContent = reply.message;
    node.hidden = false;
    if (input) {
      input.setAttribute('aria-invalid', 'true');
      input.focus();
    }
    scheduleHeight();
  }

  // An empty field travels as null so Python reports it on the right field.
  const numberOrNull = (input) => (input.value.trim() === '' ? null : Number(input.value));

  async function submitSettings(event) {
    event.preventDefault();
    if (state.saving || el.sSave.disabled) return;
    clearSettingsErrors();
    const values = {
      notifications: el.sNotifications.checked,
      poll_interval_secs: numberOrNull(el.sInterval),
      max_visible_servers: numberOrNull(el.sVisible),
    };
    setSaving(true);
    let reply;
    try {
      reply = await saveSettings(values);
    } catch (error) {
      reply = { ok: false, field: null, message: 'No se pudieron guardar los ajustes' };
    }
    setSaving(false);
    if (reply.ok) closeSettings();
    else showSettingsError(reply);
  }

  async function saveSettings(values) {
    const api = bridge();
    if (api) return api.save_settings(values);
    if (window.__MCW_PREVIEW__) return previewSaveSettings(values);
    throw new Error('sin conexión con la app');
  }

  // Preview only: validates like Python and applies the values without saving anything.
  async function previewSaveSettings(values) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    for (const [field, [low, high]] of Object.entries(LIMITS)) {
      const value = values[field];
      if (!Number.isInteger(value) || value < low || value > high) {
        return { ok: false, field, message: `Entre ${low} y ${high}` };
      }
    }
    render({ ...state.payload, settings: values });
    return { ok: true };
  }

  // Click on a notification: that server's detail, or the list when it is gone. Whatever was
  // half done (form, dialog, rename, confirmation) is dropped.
  function showServer(address) {
    if (state.saving || state.busy || state.deleting) return;
    if (state.settingsOpen) closeSettings();
    if (state.view === 'form') closeForm();
    if (state.view === 'detail') leaveDetail();
    const exists = state.payload && state.payload.servers.some((s) => s.address === address);
    if (address && exists) openDetail(address);
  }

  // --- Escape --------------------------------------------------------------

  // One level at a time: rename, confirmation, form or detail, and only then the panel.
  function onEscape() {
    if (state.settingsOpen) closeSettings();
    else if (state.renaming) endRename();
    else if (state.confirming) closeConfirm();
    else if (state.view === 'form' && !state.busy) closeForm();
    else if (state.view === 'detail') leaveDetail();
    else hide();
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
  el.back.addEventListener('click', goBack);
  el.cancel.addEventListener('click', closeForm);
  el.form.addEventListener('submit', submitForm);
  el.pin.addEventListener('click', togglePin);
  el.close.addEventListener('click', hide);
  el.servers.addEventListener('click', onRowActivate);
  el.servers.addEventListener('keydown', (event) => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.server')) {
      event.preventDefault();
      onRowActivate(event);
    }
  });
  el.title.addEventListener('click', startRename);
  el.title.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      startRename();
    }
  });
  el.titleInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      commitRename();
    } else if (event.key === 'Escape') {
      event.stopPropagation(); // cancel the rename only: the detail stays open
      endRename();
    }
  });
  el.titleInput.addEventListener('blur', commitRename);
  el.del.addEventListener('click', openConfirm);
  el.confirmCancel.addEventListener('click', closeConfirm);
  el.confirmOk.addEventListener('click', confirmDelete);
  el.settingsBtn.addEventListener('click', openSettings);
  el.sCancel.addEventListener('click', closeSettings);
  el.settingsForm.addEventListener('submit', submitSettings);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') onEscape();
    if (event.key === 'Tab') document.body.classList.add('kbd');
  });
  document.addEventListener('pointerdown', () => document.body.classList.remove('kbd'));
  window.addEventListener('blur', () => {
    const api = bridge();
    if (api) api.on_blur();
  });

  window.mcw = { render, openDetail: showServer };
  setInterval(updateFooter, 1000);

  if (window.__MCW_PREVIEW__) {
    initPreview(window.__MCW_PREVIEW__);
  } else if (bridge()) {
    loadFromPython();
  } else {
    window.addEventListener('pywebviewready', loadFromPython);
  }
})();
