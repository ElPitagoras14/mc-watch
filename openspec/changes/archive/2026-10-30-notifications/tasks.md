## 1. Configuración y ajustes

- [x] 1.1 Agregar a `config.py` `Settings`, los límites (`MAX_POLL_INTERVAL_SECS`, `MIN/MAX_VISIBLE_SERVERS`, `DEFAULT_MAX_VISIBLE_SERVERS`), los campos `notifications` y `max_visible_servers` de `Config` con su parseo, `Config.settings` y el tope de 3600 en `_parse_interval` (D4). Tests en `tests/test_config.py`:
  - claves ausentes → defaults;
  - `notifications` no booleano → `false`;
  - `max_visible_servers` 50 → 20;
  - intervalo 86400 → 3600.
- [x] 1.2 Implementar `config.save_settings()` (D4). Tests en `tests/test_config_write.py`:
  - archivo solo con `[[servers]]` → las tres claves quedan antes de la primera entrada y las entradas no cambian;
  - claves existentes con comentarios → se actualizan en su sitio.
- [x] 1.3 Implementar `Poller.set_interval()` con `_reschedule_event` y la espera en bucle de D6. Tests en `tests/test_poller.py`:
  - acortar el intervalo cuando el ciclo anterior empezó hace más que el nuevo → cicla enseguida;
  - alargarlo → no cicla antes de tiempo.

## 2. Notificaciones

- [x] 2.1 Crear `notify.py` con `Notice`, `notices(prev, curr)` y `group()` (D1). Tests en `tests/test_notify.py`:
  - 0 → 2 jugadores en hidden → "Alguien está jugando";
  - full con nombre nuevo → "entró" sin "Alguien está jugando";
  - partial con nombres distintos → nada;
  - online → offline → "se cayó"; offline → online → "volvió";
  - `QUERYING` → online con jugadores → nada;
  - servidor nuevo en `curr` → nada;
  - cuatro avisos → una agrupada con los tres primeros nombres.
- [x] 2.2 Implementar `Notifications` (suscriptor, `set_enabled`, emisión con `desktop-notifier` en su propio bucle, `broken` una vez) (D2). Agregar `desktop-notifier==6.2.0` a `pyproject.toml`. Tests con un emisor falso:
  - desactivadas → no emite pero actualiza `prev`, y al activarlas no emite lo ya ocurrido;
  - un fallo del emisor se registra una vez.

## 3. Integración

- [x] 3.1 Crear `settings.py` con `SettingsManager.save()` (D5). Tests en `tests/test_settings.py`:
  - valores válidos → escribe, cambia el intervalo del poller y activa las notificaciones;
  - intervalo 10 → error en su campo sin escribir;
  - decimal o `bool` como número → error;
  - config no escribible → error sin aplicar;
  - `ConfigWriteError` → error sin aplicar.
- [x] 3.2 Sumar `settings` al payload (el archivo roto ya llega como `config_error`) de `view.snapshot_payload` (test en `tests/test_view.py`), exponer `save_settings` en `window.py` (`_Api` y `Panel`) y `Panel.open_detail()`, y cablear en `app.py`: `Notifications` suscrita al poller con click → `open_server`, `SettingsManager` y republicar el payload tras guardar (D3, D5).

## 4. UI

- [x] 4.1 Agregar el botón de ajustes y el diálogo a `index.html` y `styles.css`, y en `app.js`: abrir con los valores del payload, `inert` en el resto, guardar con errores por campo, aviso de archivo roto con Guardar deshabilitado, Cancelar, Escape primero en `onEscape()` y el alto mínimo del panel con el diálogo abierto (D7).
- [x] 4.2 Limitar el alto de la lista a `max_visible_servers` filas en `render()` y `naturalHeight()`, y exponer `mcw.openDetail()` que vuelve a la lista si el servidor no existe y cierra formulario o diálogo abiertos (D3, D7).
- [x] 4.3 Sumar `settings` a los payloads de `preview.py` y la simulación de `save_settings` en `app.js` (D8). Actualizar `tests/test_preview.py`. Verificar en el navegador con `uv run python -m mc_watch.preview`:
  - abrir, cancelar y Escape;
  - errores de rango;
  - guardar 3 visibles → la lista hace scroll;
  - el escenario de config rota → aviso y Guardar deshabilitado.

## 5. Verificación final

- [x] 5.1 Prueba de punta a punta con `MC_WATCH_CONFIG_DIR=local/demo` y la app real:
  - abrir ajustes, activar notificaciones, cambiar el intervalo y los visibles; `config.toml` conserva comentarios y servidores, y los valores persisten al reiniciar;
  - con un servidor de prueba que pasa de offline a online (por ejemplo, un servidor local) ver la notificación "volvió" y que el click abre su detalle;
  - entrar con una cuenta propia a un servidor monitoreado y recibir la notificación.
- [x] 5.2 Actualizar `docs/roadmap.md` con lo que cambió respecto al plan del change 4 (diálogo de ajustes).
- [x] 5.3 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio.
