## Context

El repo parte vacío. La arquitectura se toma de dos proyectos de referencia: `pr-watch` (Python, `uv`, bandeja + panel HTML en `pywebview`, config TOML, preview en navegador) y `usage-monitor-for-claude` (un solo módulo concentra la red, popup anclado a la bandeja). Ver proposal.md para el porqué y el alcance; los requisitos están en `specs/`.

Restricciones que moldean el diseño:
- Solo Windows en este change.
- `pywebview` necesita el hilo principal (`webview.start()` bloquea).
- `mcstatus` ofrece API async y no documenta sus tipos de excepción.

## Goals / Non-Goals

**Goals:**
- Dejar las costuras definitivas desde el inicio: modelo neutral `ServerStatus`, módulo `probe` como único consumidor de `mcstatus`, poller separado de la UI. Los changes 2–4 deben poder crecer sin reestructurar.
- Que la lógica de estados sea pura y testeable sin red.

**Non-Goals:**
- Escribir la config, Bedrock, Query, detalle, notificaciones, empaquetado (changes posteriores).
- Instancia única, i18n.

## Decisions

### D1 - Estructura del paquete

```
mc_watch/
  __init__.py        __version__
  __main__.py        entry point: python -m mc_watch
  app.py             arranque: config -> poller -> tray -> ventana
  config.py          lectura de config.toml (tomllib), validación
  log.py             logging: archivo rotativo + stderr (D7)
  models.py          State, ServerConfig, ServerStatus, Snapshot, ProbeResult
  view.py            Snapshot -> dict JSON que recibe mcw.render() en la UI
  probe.py           ÚNICO módulo que importa mcstatus
  state.py           máquina de estados pura (fallos consecutivos)
  poller.py          hilo con asyncio loop, ciclos periódicos
  tray.py            pystray + dibujo del icono con Pillow
  window.py          pywebview: crear, posicionar, mostrar/ocultar, js_api
  winutil.py         ctypes: área de trabajo, tema de la barra de tareas
  preview.py         python -m mc_watch.preview
  ui/
    index.html  styles.css  app.js
tests/
```

### D2 - `probe` devuelve un resultado, `state` decide el estado

`probe.probe(server) -> ProbeResult` hace una sola consulta y clasifica: `Ok(online, max, latency)`, `Unreachable` (timeout, conexión rechazada, respuesta inválida) o `Unresolvable` (`socket.gaierror`). Como `mcstatus` no documenta sus excepciones, `probe` captura `OSError`, `TimeoutError`, `IOError` y `ValueError` y los mapea a `Unreachable`; cualquier otra excepción también se mapea a `Unreachable` y se registra en log, para que un bug de parseo nunca tumbe el poller.

`state.next_status(prev, result) -> ServerStatus` aplica la regla de dos fallos. Es una función pura, por lo que todos los escenarios de `server-probing` se prueban con unittest sin red.

- *Alternativa descartada*: que `probe` mantenga el contador de fallos. Mezclaría red y lógica, y obligaría a mockear `mcstatus` para probar la histéresis.

Se usa `JavaServer.async_lookup(address)` (resuelve SRV cuando no hay puerto) y `async_status()` con `timeout=3`; no se llama a `ping()` porque muchos servidores no vanilla no lo responden y `status` ya trae la latencia. Fijamos `mcstatus>=14,<15`.

### D3 - Tres hilos: ventana, poller y bandeja

```
 hilo principal          hilo "poller"              hilo "tray"
 ----------------        ------------------         --------------
 webview.start()  <----  asyncio loop:              pystray
   (ventana)       push    cada ciclo:              icon.run_detached()
                   JSON    gather(probe x N)          menú -> window.show/
                           -> state.next_status        quit
                           -> snapshot ------------>  icon.update(count)
```

- El poller corre `asyncio.run()` en un hilo daemon. Al terminar cada ciclo publica un snapshot inmutable (lista de `ServerStatus` + timestamp) a los suscriptores: la ventana y el tray.
- La ventana recibe el snapshot con `window.evaluate_js("mcw.render(<json>)")`, que pywebview permite llamar desde otros hilos. Además, al abrir el panel, el JS pide el último snapshot por `js_api.get_snapshot()` para no depender de un push perdido.
- El texto "Actualizado hace…" lo calcula el JS con un `setInterval` de 1 s a partir del timestamp; Python no empuja cada segundo.
- Salir: el tray llama a `poller.stop()`, `icon.stop()` y `window.destroy()`; con la ventana destruida, `webview.start()` retorna y el proceso termina.

- *Alternativa descartada*: que el JS haga polling a Python cada segundo. Funciona, pero añade tráfico constante y deja el push sin usar; el push con pull de respaldo es igual de simple.

### D4 - Ventana del panel frameless anclada al área de trabajo

- `webview.create_window(frameless=True, on_top=False, resizable=False, hidden=True)`.
- Tamaño: ancho fijo de 360 px; el alto se adapta al contenido entre un mínimo de 240 px y un máximo de 600 px, y por encima del máximo la lista hace scroll interno. El JS mide la altura del documento tras cada `render` y llama a `js_api.resize(height)` solo si cambió; Python recorta al rango y reposiciona.
- Posición: esquina inferior derecha del área de trabajo (`SystemParametersInfoW(SPI_GETWORKAREA)`), con margen. El borde inferior queda anclado, así que al crecer el panel sube y no tapa la barra de tareas. Cubre la barra de tareas abajo, que es el caso normal; otras posiciones de la barra quedan como riesgo aceptado.
- *Alternativa descartada*: tamaño fijo 360×480. Más simple, pero con uno o dos servidores el panel queda mayormente vacío.
- Ocultar al perder foco: el JS escucha `window.blur` y llama a `js_api.on_blur()`; Python oculta solo si no está fijado. Escape y el botón cerrar llaman a `js_api.hide()`.
- Fijar: alterna un flag en memoria y fija el estado *topmost* con `SetWindowPos` por ctypes. No se usa el setter `window.on_top` de pywebview: asigna `Form.TopMost` desde el hilo que llama y, como pythonnet mantiene el GIL durante la llamada .NET, se bloquea contra el hilo de la interfaz y congela todo el proceso (reproducido en la tarea 5.3).
- La geometría se aplica con `SetWindowPos` en píxeles físicos (escala del sistema) y no con `window.move`/`resize` de pywebview, para no depender de cómo estos escalan. La ventana se marca `WS_EX_TOOLWINDOW` mientras está oculta para que no tenga botón en la barra de tareas ni aparezca en Alt+Tab.
- Click en el icono con el panel recién oculto por blur: el click en la bandeja quita el foco al panel antes de que llegue el evento del icono, así que "alternar" lo reabriría. Se ignora un show si el panel se ocultó por blur hace menos de ~300 ms.

### D5 - Icono de bandeja dibujado con Pillow

Se dibuja con Pillow a 64×64: el número de servidores online en grande, color según el tema leído de `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\SystemUsesLightTheme`. Sin servidores, un glifo neutro sin número. Con 10 o más se muestra "9+".

### D6 - Config de solo lectura con `tomllib`

`tomllib` (stdlib). La validación produce `Config(poll_interval_secs, servers: list[ServerConfig])` más una lista de advertencias que se registran en log. El parseo de `address` (`host` o `host:puerto`, puerto 1–65535) vive en `config.py`; la resolución SRV es de `mcstatus`.

Formato de ejemplo:

```toml
poll_interval_secs = 60

[[servers]]
name = "Survival"
address = "play.example.com"
```

### D7 - Logs a archivo rotativo y a stderr

`logging` con dos handlers desde el arranque: un `RotatingFileHandler` en `%APPDATA%\mc-watch\mc-watch.log` (o en `MC_WATCH_CONFIG_DIR`), con 1 MB por archivo y 3 respaldos, y un `StreamHandler` a stderr solo cuando `sys.stderr` existe (con `uv run` hay consola; en el `.exe` sin consola, `sys.stderr` es `None`). Nivel `INFO` por defecto; `MC_WATCH_DEBUG=1` lo sube a `DEBUG`. Si el directorio no existe se crea; si no se puede escribir, se sigue solo con stderr.

Se registran: config cargada y advertencias de validación, inicio y fin de cada ciclo con su duración, cambios de estado de cada servidor y excepciones inesperadas de `probe`.

- *Alternativa descartada*: solo stderr y decidir en `distribution`. Habría que tocar el arranque de nuevo, y el archivo ya sirve para diagnosticar mientras se prueba el skeleton.

### D8 - Tooling igual que pr-watch

Python 3.13, `uv`, `ruff` (lint + format), `pyright` estricto en `mc_watch/`, `unittest`. La versión vive en `pyproject.toml` y en `mc_watch/__init__.py`; un test verifica que coincidan (igual que pr-watch).

## Risks / Trade-offs

- [El evento `blur` de WebView2 en ventana frameless podría no dispararse al hacer click en la barra de tareas] → Verificado en el spike (tarea 5.1): `window.blur` llega a Python en ~10 ms tanto al pasar el foco a otra ventana como a la barra de tareas, y tras volver a mostrar la ventana el ciclo se repite. No hace falta un hook nativo. Queda por verificar con el icono real de la bandeja la guarda de ~300 ms contra reabrir tras blur (tarea 6.x).
- [pywebview recorre los atributos del objeto `js_api` para exponerlos a JavaScript] → Verificado en el spike: guardar la ventana en un atributo público (`self.window`) hace que recurra sin fin por `window.native` y la app queda colgada. El `js_api` guarda la ventana como `_window` (los atributos con guion bajo se ignoran).
- [`mcstatus` puede lanzar excepciones no previstas] → `probe` captura todo y lo mapea a `Unreachable`, con log.
- [La barra de tareas arriba o a los lados deja el panel mal ubicado] → aceptado en este change; se usa el área de trabajo, así que al menos no queda tapado.
- [Muchos servidores × timeout de 3 s] → las consultas son concurrentes; el ciclo dura como máximo ~3 s más la resolución DNS.
- [`evaluate_js` antes de que cargue la página] → el JS hace pull de `get_snapshot()` en `DOMContentLoaded`, así que un push temprano perdido no importa.
- [Reposicionar en cada cambio de alto produce parpadeo] → `resize` y `move` se llaman juntos y solo cuando el alto cambia; con el panel oculto se aplican antes de mostrarlo.
