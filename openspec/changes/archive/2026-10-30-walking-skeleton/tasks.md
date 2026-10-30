## 1. Proyecto base

- [x] 1.1 Crear `pyproject.toml` con `uv` (Python 3.13, dependencias `mcstatus>=14,<15`, `pystray`, `pywebview`, `Pillow`; dev `ruff`, `pyright`) y verificar que `uv sync` termina sin errores
- [x] 1.2 Crear el paquete `mc_watch/` con `__init__.py` (`__version__ = "0.1.0"`) y `__main__.py` vacío, y verificar que `uv run python -m mc_watch` sale sin error
- [x] 1.3 Configurar `ruff` y `pyright` en `pyproject.toml` y verificar que `uv run ruff check`, `uv run ruff format --check` y `uv run pyright` pasan
- [x] 1.4 Configurar logging según D7 (archivo rotativo 1 MB × 3 en el directorio de config, stderr solo si existe, `MC_WATCH_DEBUG`) y verificar con un test que escribe en un directorio temporal y que no falla con `sys.stderr = None`
- [x] 1.5 Agregar `tests/test_version.py` que compara la versión de `pyproject.toml` con `mc_watch.__version__` y verificar que `uv run python -m unittest` pasa

## 2. Modelo y config

- [x] 2.1 Definir `State`, `ServerConfig` y `ServerStatus` en `models.py` y verificar con `pyright`
- [x] 2.2 Implementar `config.py` (ruta por defecto y `MC_WATCH_CONFIG_DIR`, parseo de `address`, intervalo por defecto y mínimo, entradas inválidas ignoradas, TOML inválido → defaults sin tocar el archivo) y verificar con tests que cubren cada escenario de `specs/server-config`

## 3. Sondeo

- [x] 3.1 Implementar `state.next_status()` con la regla de dos fallos y verificar con tests que cubren cada escenario de "Estados del servidor" en `specs/server-probing`
- [x] 3.2 Implementar `probe.probe()` con `JavaServer.async_lookup` + `async_status(timeout=3)`, mapeando a `Ok` / `Unreachable` / `Unresolvable`, y verificar con tests que mockean `mcstatus` (respuesta ok, timeout, `gaierror`, excepción inesperada)
- [x] 3.3 Implementar `poller.py` (hilo con asyncio loop, `gather` por ciclo, intervalo, suscriptores, `stop()`) y verificar con un test que usa un probe falso y un intervalo corto que se publican snapshots y que `stop()` termina el hilo
- [x] 3.4 Agregar un script `scripts/probe_once.py <address>` que imprime el resultado de una consulta real y verificarlo contra un servidor público conocido y contra un host inexistente

## 4. UI del panel

- [x] 4.1 Crear `ui/index.html`, `styles.css` y `app.js` según `reference/main.png` (cabecera con agregar deshabilitado / fijar / cerrar, filas con nombre, dirección, estado con color y `X/Y` o `—`, estado vacío con ruta de config, pie con "Actualizado hace…" y versión) con `mcw.render(snapshot)` como única entrada de datos
- [x] 4.2 Implementar `preview.py` con snapshots de ejemplo en los cuatro estados y el estado vacío, y verificar que `uv run python -m mc_watch.preview` abre el navegador y muestra ambos casos

## 5. Ventana y bandeja

- [x] 5.1 Spike: ventana frameless de pywebview que se oculta con `window.blur`; verificar a mano que se oculta al hacer click en otra ventana y en la barra de tareas, y registrar el resultado en `design.md` si hay que cambiar de enfoque
- [x] 5.2 Implementar `winutil.py` (área de trabajo y tema de la barra de tareas por ctypes/registro) y verificar con un test que la lectura del tema devuelve un booleano sin lanzar excepción
- [x] 5.3 Implementar `window.py` (crear oculta, posicionar en el área de trabajo, mostrar/ocultar/alternar, `js_api` con `hide`, `on_blur`, `toggle_pin`, `get_snapshot`, `resize` con alto entre 240 y 600 y borde inferior anclado, guarda de ~300 ms contra reabrir tras blur) y verificar a mano cada escenario de "Abrir el panel", "Ocultar el panel" y "Fijar el panel" en `specs/tray-app` y de "Tamaño del panel" en `specs/monitor-ui`
- [x] 5.4 Implementar `tray.py` (icono dibujado con Pillow con conteo, "9+", sin número cuando no hay servidores, colores por tema, tooltip, menú Abrir / Salir) y verificar con un test que la función de dibujo produce una imagen 64×64 para 0, 3 y 12 servidores

## 6. Integración

- [x] 6.1 Conectar todo en `app.py` / `__main__.py` (config → poller → tray → ventana; Salir detiene poller, icono y ventana) y verificar que `uv run python -m mc_watch` arranca y que "Salir" termina el proceso
- [x] 6.2 Prueba de punta a punta: con un `config.toml` que tenga un servidor público, un host inexistente y una entrada inválida, verificar que el panel muestra Online con `X/Y`, Error y solo dos filas, que el icono muestra "1" y que el pie avanza "Actualizado hace…"
- [x] 6.3 Prueba de caída: con la app corriendo, cortar la red y verificar que el servidor pasa a Offline recién tras el segundo ciclo, y que vuelve a Online al restaurarla
- [x] 6.4 Verificar que `ruff`, `pyright` y `unittest` pasan en limpio
