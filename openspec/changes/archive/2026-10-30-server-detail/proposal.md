## Why

El panel responde "¿hay alguien?" con un `X/Y`, pero no "¿quién?", que es lo que un jugador quiere saber antes de entrar. Además, un servidor agregado por error solo se puede quitar o renombrar editando `config.toml` a mano. Y los servidores "dormidos" de Aternos aparecen como online 0/20: su proxy responde al ping aunque el servidor esté apagado. Capturado con `mecotronicos.aternos.me` apagado: `version.protocol = -1`, `version.name = "§c● Offline"` y el MOTD "This server is offline.".

## What Changes

- Click en una fila abre una **vista de detalle** dentro del mismo panel:
  - Cabecera con volver, el nombre del servidor, eliminar, fijar y cerrar.
  - Bloque de información con icono, MOTD con sus colores, versión, latencia y dirección.
  - Sección "Participantes".
  - El detalle se actualiza en vivo con cada ciclo de sondeo.
- **Participantes** en tres modos:
  - `full`: la lista de nombres. También cubre "Nadie está jugando" cuando hay 0 jugadores.
  - `partial`: los nombres que se conocen y "5 de 23 jugadores".
  - `hidden`: "Este servidor no comparte la lista de jugadores".
- **Query** (UDP) para servidores Java, como fuente de la lista completa:
  - Cada servidor recuerda en memoria si respondió a Query.
  - Si falla, se reintenta cada 10 ciclos.
  - Sin Query, se usa la muestra del Server List Ping.
- **Filtro de muestras falsas**: se descartan las entradas con UUID nulo, con códigos `§` o con nombres que no cumplen `[A-Za-z0-9_]{3,16}`. Hypixel, por ejemplo, usa la muestra para texto decorativo.
- **Renombrar** con un click en el nombre del detalle (edición inline) y **eliminar** con una confirmación dentro del panel. Ambos cambios se guardan en `config.toml`.
- **Servidores dormidos**: una respuesta Java con `protocol = -1` y una versión que dice "Offline" o "Sleeping" cuenta como offline de inmediato. La fila muestra Offline y el detalle explica que el servidor está apagado.
- El sondeo amplía lo que lee de cada respuesta: MOTD, versión, icono, muestra de jugadores y el resultado de Query.
- Escape en el detalle vuelve a la lista, igual que en el formulario.
- El preview gana escenarios para el detalle en sus tres modos, el servidor dormido, renombrar y eliminar.

### Non-goals

- Editar la dirección de un servidor existente (fuera del MVP).
- Query en un puerto distinto del de juego: Query se consulta en el mismo puerto que el ping, que es el valor por defecto de `query.port`.
- Avatares o cabezas de los jugadores: requieren servicios externos.
- Animar el formato "obfuscated" del MOTD: ese texto se muestra tal cual.
- Notificaciones: llegan en el change 4. Este change las prepara exponiendo `players_mode` y los nombres en cada ciclo.

## Capabilities

### New Capabilities

- `server-detail`: la vista de detalle de un servidor. Cubre cómo se abre y se cierra, el bloque de información, la sección de participantes en sus modos y la actualización en vivo.

### Modified Capabilities

- `server-probing`: datos adicionales de cada respuesta (MOTD, versión, icono, latencia), la lista de jugadores con Query y la muestra filtrada, el cálculo de `players_mode`, y los servidores dormidos como offline inmediato dentro de "Estados del servidor".
- `server-management`: renombrar y eliminar servidores.
- `server-config`: la escritura del archivo pasa a cubrir también el cambio de `name` y el borrado de una entrada.
- `monitor-ui`: las filas se pueden abrir, la cabecera tiene la variante de detalle y el preview cubre el detalle.
- `tray-app`: Escape en el detalle vuelve a la lista en lugar de ocultar el panel.

## Impact

- Código:
  - `models.py`: información del servidor, jugadores y estado de Query.
  - `probe.py`: Query, MOTD, icono, muestra y detección de dormidos.
  - `players.py` (nuevo): filtro de la muestra y `players_mode`.
  - `state.py`: estado de Query por servidor y regla de dormidos.
  - `poller.py`: renombrar y quitar en caliente, y combinar los resultados de cada ciclo por dirección.
  - `config.py`: `set_name` y `remove_server`.
  - `servers.py`: renombrar y eliminar.
  - Integración y UI: `window.py`, `view.py`, `ui/*`, `preview.py` y `scripts/probe_once.py`.
- Red: datagramas UDP de Query al puerto de juego de cada servidor Java, en paralelo con el ping. El ciclo no se alarga.
- Payload hacia la UI: crece con el icono (PNG en base64, unos pocos KB por servidor) y la lista de nombres.
- Dependencias: ninguna nueva.
