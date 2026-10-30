## Why

Quiero saber desde la bandeja de Windows si mis servidores de Minecraft están arriba y cuánta gente hay jugando, sin abrir el juego. Este change es el walking skeleton de `mc-watch`: la porción vertical más delgada que recorre toda la arquitectura (config → sondeo → poller → UI → bandeja) y que se puede probar de punta a punta, para que los changes siguientes crezcan sobre una base que ya funciona.

## What Changes

- Nueva app de bandeja para Windows en Python (`mc-watch`), con proyecto gestionado por `uv` y checks de `ruff`, `pyright` y `unittest`.
- Lectura de la lista de servidores desde `config.toml` en `%APPDATA%\mc-watch`, editado a mano. La app no escribe el archivo en este change.
- Sondeo periódico y concurrente de servidores **Java** por Server List Ping, con resolución de registros SRV.
- Cuatro estados por servidor: consultando, online, offline (tras 2 fallos seguidos) y error (el host no resuelve).
- Icono de bandeja que muestra cuántos servidores están online, con menú Abrir / Salir.
- Panel principal según el boceto `reference/main.png`: lista de servidores (nombre, host, estado, jugadores X/Y), botones fijar y cerrar, pie con "Actualizado hace…" y versión. El botón agregar aparece deshabilitado.
- Preview de la UI en el navegador con datos de ejemplo, para iterar el diseño sin levantar la app.

### Non-goals (llegan en changes posteriores)

1. `add-servers`: formulario para agregar, autodetección Java → Bedrock, soporte Bedrock y escritura de la config.
2. `server-detail`: vista de detalle (MOTD, versión, latencia, icono), participantes en modos full/partial/hidden con Query, renombrar inline y eliminar.
3. `notifications`: avisos de "alguien está jugando", "X entró" y caída/vuelta del servidor.
4. `distribution`: `.exe` portable, autostart y workflow de release.

También quedan fuera Linux, macOS y servidores anteriores a 1.7.

## Capabilities

### New Capabilities

- `server-probing`: cómo se consulta un servidor, cada cuánto, y cómo se traduce el resultado a los cuatro estados y al conteo de jugadores.
- `server-config`: dónde vive la lista de servidores y los ajustes, su formato y qué pasa si el archivo falta o es inválido.
- `monitor-ui`: el panel principal y lo que muestra por servidor y en el pie.
- `tray-app`: el icono de bandeja, su menú y el comportamiento de la ventana (abrir, ocultar, fijar).

### Modified Capabilities

Ninguna: es el primer change del proyecto.

## Impact

- Proyecto nuevo desde cero: `pyproject.toml`, `uv.lock`, paquete `mc_watch/`, `tests/`.
- Dependencias: `mcstatus` (14.x), `pystray`, `pywebview`, `Pillow`.
- Red: conexiones TCP salientes a los hosts configurados (puerto 25565 o el del registro SRV) y consultas DNS. Ninguna otra.
- Disco: lectura de `%APPDATA%\mc-watch\config.toml` y escritura de un log rotativo `mc-watch.log` en el mismo directorio.
