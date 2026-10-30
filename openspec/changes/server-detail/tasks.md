## 1. Modelo y lógica pura

- [x] 1.1 Agregar a `models.py` `MotdSegment`, `SamplePlayer`, `ServerInfo`, `QueryOutcome`, `PlayersMode`, los campos nuevos de `ProbeOk` (todos con default), `ProbeAsleep` en el union `ProbeResult` y los campos nuevos de `ServerStatus` (`info`, `latency_ms`, `players_mode`, `players`, `asleep`, `query_capable`, `query_wait`) (D1, D4, D5)
- [x] 1.2 Crear `players.py` con `clean_sample()` y `players_view()` (D5). Escribir `tests/test_players.py` con:
  - UUID nulo, `§` y nombres de 2 y de 17 caracteres descartados;
  - repetidos sin distinguir mayúsculas;
  - Query OK → full;
  - muestra igual a online → full;
  - muestra mayor que online → full;
  - muestra menor → partial;
  - muestra decorativa → hidden;
  - 0 jugadores → full sin nombres;
  - Bedrock con jugadores → hidden;
  - Bedrock con 0 → full.
- [x] 1.3 Ampliar `state.next_status()`: llenar `info`, `latency_ms`, `players_mode` y `players` con `ProbeOk` y limpiarlos en los demás estados; regla de Query (`QUERY_RETRY_CYCLES`, `wants_query()`); y `ProbeAsleep` → offline inmediato con `asleep=True`, `failures=0` y edición fijada (D4, D5, D6). Escribir tests en `tests/test_state.py` con:
  - online → dormido en un ciclo;
  - dormido → online;
  - desconocido dormido → Java;
  - fallo tras dormido que sigue offline;
  - Query OK, Query FAILED y el reintento exacto en el décimo ciclo online;
  - ciclos offline que no descuentan `query_wait`;
  - Bedrock nunca pide Query;
  - la información que se limpia al pasar a offline o error.

## 2. Sondeo

- [x] 2.1 Implementar en `probe.py` `_strip_codes()`, `_is_asleep()` y `ASLEEP_KEYWORDS`, devolver `ProbeAsleep` desde `_java` y tratarlo como respuesta Java en `_detect` (D2). Escribir tests con mcstatus mockeado:
  - la respuesta capturada de Aternos (`protocol=-1`, `"§c● Offline"`) → `ProbeAsleep`;
  - `protocol=-1` con "Mantenimiento" → `ProbeOk`;
  - detección de un desconocido dormido → `ProbeAsleep(JAVA)` sin esperar a Bedrock.
- [x] 2.2 Implementar `_motd_segments()` con la tabla de colores propia, el icono validado y el nombre de versión sin códigos en `_java` y `_bedrock` (D3). Escribir tests con `Motd.parse(...)` real:
  - `§aHola §lmundo`;
  - un MOTD en formato dict con `extra` y color web;
  - `§r` que reinicia;
  - un color que no reinicia los estilos;
  - un texto con `<b>` que sale literal en el segmento;
  - un icono que no es PNG → `None`;
  - un color Bedrock `MATERIAL_*`.
- [x] 2.3 Agregar `query: bool` a `probe()` y a `ProbeFn`, e implementar status y Query en paralelo en `_java`: un fallo de Query → `FAILED` sin afectar el resultado, y se cancela Query si el status falla (D4). Mapear `players.sample` a `SamplePlayer`. Escribir tests:
  - Query OK con nombres;
  - Query con timeout y status OK → `ProbeOk(query=FAILED)`;
  - status falla → Query cancelada;
  - `query=False` → `SKIPPED`;
  - la duración total con ambos lentos ronda los 3 s y no los 6 s.

  Ajustar los probes falsos de `tests/test_poller.py` y `tests/test_servers.py` a la nueva firma.
- [x] 2.4 Ampliar `scripts/probe_once.py`: `--query` e imprimir versión, MOTD plano, modo y nombres, y "dormido" cuando corresponda; forzar UTF-8 en stdout. Verificar a mano con `mc.hypixel.net` (muestra decorativa → hidden), `mecotronicos.aternos.me` apagado (→ dormido) y un servidor Bedrock.

## 3. Config y gestión

- [x] 3.1 Extraer `_find_entry()` y `normalize_name()` en `config.py` e implementar `set_name()` y `remove_server()` (D7). Escribir tests en `tests/test_config_write.py`:
  - renombrar la segunda de tres entradas sin tocar el resto ni los comentarios;
  - quitar la segunda de tres con comentarios entre entradas, y que el resultado se vuelva a leer con `load_config`;
  - dirección con otras mayúsculas;
  - entrada inexistente → `False` sin escribir;
  - archivo roto → `ConfigWriteError` con el archivo intacto.
- [x] 3.2 Implementar `Poller.rename()` y `Poller.remove()`, y la unión por dirección en `_cycle()` con `_merge()`, y pasar `query=wants_query(status)` al probe (D4, D7). Escribir tests en `tests/test_poller.py`:
  - `rename` y `remove` publican un snapshot con el mismo `updated_at`;
  - un servidor quitado durante un ciclo lento no reaparece;
  - un renombrado durante un ciclo lento se conserva y la edición detectada en ese ciclo también;
  - un alta durante el ciclo sigue funcionando;
  - el probe recibe `query=True` solo para Java con `query_wait == 0`.
- [x] 3.3 Implementar `ServerManager.rename_server()` y `remove_server()` (D7) y exponerlos en `window.py` (`_Api` y `Panel`) y en `app.py`. Escribir tests en `tests/test_servers.py`:
  - renombrar escribe y actualiza el poller;
  - nombre vacío → dirección;
  - nombre sin cambios → no escribe;
  - nombre de más de 40 caracteres → error;
  - config no escribible → error sin tocar el poller;
  - `ConfigWriteError` → error;
  - eliminar escribe, quita del poller y limpia `_editions`;
  - eliminar una entrada que ya no está en el archivo igual la quita del poller.

## 4. UI

- [x] 4.1 Ampliar `snapshot_payload()` en `view.py` con `latency_ms`, `version`, `motd`, `icon`, `players_mode`, `players` y `asleep`, y escribir sus tests en `tests/test_view.py` (online completo, offline con todo en null o vacío, dormido)
- [x] 4.2 Hacer las filas interactivas en `app.js` y `styles.css`: `tabindex`, `role`, `aria-label`, hover y foco, y un listener delegado para click, Enter y Espacio. Construir la vista `detail` en `index.html`, `styles.css` y `app.js`:
  - `showView()` con las tres vistas y la tabla de cabecera de D8;
  - bloque de información con icono o glifo genérico, MOTD por segmentos con `textContent`, versión, latencia, edición y dirección;
  - mensajes de estado, incluido el de dormido;
  - participantes en los cuatro casos;
  - render en vivo y vuelta a la lista si el servidor desaparece;
  - alto del panel con la lista de participantes.
- [x] 4.3 Implementar el renombrado inline en `app.js`: input en el título, Enter o blur guardan, Escape cancela, `render()` no pisa el input y se muestra el error bajo la cabecera. Implementar la confirmación de eliminar: bloque dentro del detalle, botones deshabilitados durante la llamada, error en la confirmación y vuelta a la lista al eliminar. Implementar la prioridad de Escape de D8.
- [x] 4.4 Sumar a `preview.py` los servidores de D9 y el icono PNG de ejemplo, y en `app.js` la simulación de `rename_server` y `remove_server` (con "fail" en el nombre → error). Actualizar `tests/test_preview.py`. Verificar en el navegador con `uv run python -m mc_watch.preview`:
  - los cuatro modos de participantes;
  - el dormido;
  - el MOTD con `<b>` literal;
  - renombrar (Enter, Escape, error);
  - eliminar (cancelar, confirmar);
  - Escape en cada nivel;
  - teclado sobre las filas;
  - el alto del panel en las tres vistas.

## 5. Actualizar desde el detalle

- [x] 5.1 Agregar `Poller.refresh_server()` (consulta solo ese servidor, descarta el resultado si lo quitaron, no mueve `updated_at`), exponerlo en `window.py` y `app.py`, y mostrar el botón actualizar en la cabecera del detalle (ocupado hasta que vuelve la llamada) con la papelera siempre en rojo. Escribir un test en `tests/test_poller.py`

## 6. Verificación final

- [ ] 6.1 Prueba de punta a punta con `MC_WATCH_CONFIG_DIR=local/demo` y la app real:
  - abrir `mc.hypixel.net` → hidden con versión, MOTD con colores e icono;
  - agregar `mecotronicos.aternos.me` → Offline en la lista y "servidor apagado" en el detalle;
  - abrir un servidor Bedrock → hidden con "Bedrock";
  - si hay acceso a un servidor pequeño con muestra o Query, ver los nombres.
- [ ] 6.2 Con el Aternos **encendido**, capturar con `uv run python scripts/probe_once.py --query mecotronicos.aternos.me` y confirmar que el `protocol` es real (no `-1`), que la app lo muestra online y qué modo de participantes ofrece. Anotar el resultado en el design (sección Context).
- [ ] 6.3 Renombrar y eliminar con la app real y verificar:
  - que `config.toml` conserva los comentarios y el resto de las entradas;
  - que el icono de la bandeja se actualiza al eliminar;
  - que tras reiniciar se mantienen los cambios;
  - que con `config.toml` roto a mano, ambos muestran el error y el archivo no cambia.
- [ ] 6.4 Verificar que con el detalle abierto el panel se oculta al perder el foco y, al reabrirlo, sigue en el mismo detalle; y que el detalle se actualiza solo al terminar un ciclo.
- [x] 6.5 Actualizar `docs/roadmap.md` si la heurística de dormidos o el diseño de Query cambian algo de lo descrito para los changes 3 y 4.
- [x] 6.6 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio.
