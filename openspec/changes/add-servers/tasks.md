## 1. Modelo y sondeo

- [x] 1.1 Agregar `Edition` a `models.py`, `edition` a `ServerConfig` (default `UNKNOWN`) y a `ProbeOk`, y ajustar `state.next_status()` para fijar la ediciÃ³n de un servidor `UNKNOWN` ante un `ProbeOk` (D1). Escribir tests en `tests/test_state.py` para: desconocido â†’ Java, desconocido â†’ Bedrock, fallo que no toca la ediciÃ³n y ediciÃ³n ya fijada que no cambia
- [x] 1.2 Extraer en `probe.py` el helper de clasificaciÃ³n de excepciones e implementar `_bedrock()` con `BedrockServer.lookup` + `async_status(tries=1)` y el despacho por ediciÃ³n (D2). Escribir tests con `mcstatus` mockeado para Bedrock ok, timeout y `gaierror`
- [x] 1.3 Implementar `_detect()` con los dos intentos en paralelo y prioridad Java (D2). Escribir tests para: solo Java responde, solo Bedrock responde, ambos responden (gana Java y se cancela Bedrock), Java `Unresolvable` (no espera a Bedrock) y ninguno responde (`Unreachable` en ~3 s, no ~6 s)
- [x] 1.4 Ampliar `scripts/probe_once.py` con `--edition java|bedrock|unknown` (default `unknown`) y verificarlo a mano con `mc.hypixel.net`, un servidor Bedrock pÃºblico (por ejemplo `play.cubecraft.net` o `geo.hivebedrock.network`) y `no-existe.invalid`

## 2. Config

- [x] 2.1 Agregar `tomlkit` con `uv add tomlkit` y verificar que `uv sync` termina sin errores
- [x] 2.2 Leer `edition` en `_parse_servers` (ausente o invÃ¡lida â†’ `UNKNOWN`) y agregar `writable` y `error` a `Config` (D5). Escribir tests para cada escenario de "Formato de la configuraciÃ³n" y "ConfiguraciÃ³n ausente o invÃ¡lida" en `specs/server-config`, incluido `writable=False` con TOML invÃ¡lido y `writable=True` sin archivo
- [x] 2.3 Implementar `validate_new_server(name, address, existing)` (D4). Escribir tests para direcciÃ³n vacÃ­a, puerto invÃ¡lido, espacios recortados, nombre vacÃ­o â†’ direcciÃ³n, nombre de mÃ¡s de 40 caracteres y duplicado sin distinguir mayÃºsculas
- [x] 2.4 Implementar `append_server`, `set_edition` y `ConfigWriteError` con `tomlkit`, escritura atÃ³mica, `mkdir` y lock de mÃ³dulo (D5). Escribir tests en un directorio temporal para: archivo inexistente (crea directorio y archivo), comentarios conservados, entrada al final con los tres campos, `set_edition` sobre una entrada escrita a mano sin `edition`, `set_edition` sin entrada (no escribe), archivo roto en disco (lanza el error y el archivo queda byte a byte igual) y round-trip (lo escrito lo vuelve a leer `load_config`)

## 3. Poller y alta

- [x] 3.1 Implementar `Poller.submit()` y `Poller.add()`, y hacer que `_cycle()` trabaje sobre una copia y conserve las altas hechas durante el ciclo (D3). Escribir tests en `tests/test_poller.py` para: `add` publica un snapshot con la fila nueva y el mismo `updated_at`, el servidor agregado se consulta en el ciclo siguiente, un alta durante un ciclo lento no se pierde ni rompe el `zip` y `submit` sin poller corriendo lanza `RuntimeError`
- [x] 3.2 Implementar `App.add_server()` con el lock, la validaciÃ³n, el bloqueo por config no escribible, la detecciÃ³n por `poller.submit`, la persistencia y `poller.add` (D4), y exponerlo como `_Api.add_server` en `window.py`. Escribir tests con un probe falso y un directorio temporal para: alta Java, host que no resuelve (no escribe ni agrega), nadie responde (agrega como `UNKNOWN`), falla de escritura (no agrega) y config no escribible (no consulta la red)
- [x] 3.3 Implementar en `App` el suscriptor que persiste la ediciÃ³n detectada (D6). Escribir un test en el que un servidor `UNKNOWN` responde en un ciclo y su entrada queda con `edition = "java"`, y otro en el que, con `writable=False`, no se escribe nada

## 4. UI

- [x] 4.1 Agregar `edition` por servidor y `config_error` al payload en `view.py`, y escribir el test correspondiente en `tests/test_view.py`
- [x] 4.2 Mostrar en la fila ` Â· Bedrock` o ` Â· ediciÃ³n desconocida` (en Ã¡mbar), y cambiar el estado vacÃ­o a la invitaciÃ³n a agregar, con la variante de config con error y su ruta (D7)
- [x] 4.3 Construir la vista de formulario en `index.html`, `styles.css` y `app.js`: cambio de vista y cabecera (tÃ­tulo, volver, agregar oculto), campos, errores por campo, mensaje general, "Detectandoâ€¦" con inputs deshabilitados, Enter para enviar, Escape segÃºn la vista, aviso de config con error con "Agregar" deshabilitado y `reportHeight()` al cambiar de vista (D7)
- [x] 4.4 Implementar en `app.js` el `js_api` simulado del preview y, en `preview.py`, sumar ejemplos Bedrock y desconocida y el escenario "Config con error" (D8). Actualizar `tests/test_preview.py` y verificar en el navegador con `uv run python -m mc_watch.preview` los tres resultados simulados, Escape en el formulario y el alto del panel en ambas vistas
- [x] 4.5 Implementar `Poller.refresh()` (ciclo inmediato, ignorado si hay uno en curso, siguiente ciclo periÃ³dico a `poll_interval_secs` del inicio del manual) y exponerlo como `_Api.refresh` en `window.py` y en `App`. Escribir tests en `tests/test_poller.py` para: un `refresh` con intervalo largo dispara un ciclo al instante, el pedido durante un ciclo en curso no duplica ciclos y `refresh` sin poller corriendo no falla
- [x] 4.6 Agregar el botÃ³n actualizar a la izquierda de agregar (oculto en el formulario) con estado ocupado hasta que llega un snapshot nuevo o pasan 15 s, y su simulaciÃ³n en el preview. Verificar en el preview que el botÃ³n gira, vuelve a normal y cambia "Actualizado haceâ€¦"

## 5. VerificaciÃ³n final

- [x] 5.1 Prueba de punta a punta con `MC_WATCH_CONFIG_DIR=local/demo` y la app real: agregar un servidor Java (`mc.hypixel.net` ya estÃ¡, usar otro) y uno Bedrock, y verificar que aparecen al instante, que el icono suma, que `config.toml` conserva lo existente y suma las entradas, y que tras reiniciar ambos siguen con su ediciÃ³n
- [x] 5.2 Con la app real, verificar los casos de error: `no-existe.invalid` muestra "No se encontrÃ³ el host" y no se guarda; un duplicado se rechaza; una entrada del toml sin `edition` queda con `edition = "java"` tras el primer ciclo; con `config.toml` roto a mano, el estado vacÃ­o y el formulario muestran el aviso y el archivo no cambia
- [x] 5.3 Verificar que el panel se oculta al perder el foco con el formulario a medias y que, al reabrirlo, conserva lo escrito
- [x] 5.4 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio
