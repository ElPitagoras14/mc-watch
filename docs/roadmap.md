# Roadmap de changes de mc-watch

Monitor de servidores de Minecraft en la bandeja de Windows, pensado para jugadores: "¿hay alguien jugando? ¿entró alguien?". Cada change es un vertical slice que se puede probar de punta a punta con la app real.

```
 1 walking-skeleton --> 2 add-servers --> 3 server-detail --> 4 notifications
        |
        +----------------------------------------------------> 5 distribution
                                          (independiente; puede ir en cualquier momento tras 1)
```

## 1. `walking-skeleton`: ver el estado de mis servidores desde la bandeja

- Tray icon con el número de servidores online y menú Abrir / Salir.
- Panel según `reference/main.png`: lista de servidores con estado y X/Y, fijar, cerrar, Escape, ocultar al perder foco. Pie con "Actualizado hace…" y versión. El botón agregar está deshabilitado.
- Los servidores se leen de `config.toml`, editado a mano. Solo Java.
- Módulo `probe` (status Java con SRV), poller async en su propio hilo y cuatro estados con la regla de dos fallos.
- Tooling: uv, ruff, pyright, unittest, preview en navegador.
- **Prueba:** `mc.hypixel.net` y un host falso en el toml. Uno sale online con X/Y y el otro en error. Al cortar el wifi pasan a offline tras dos polls.

## 2. `add-servers`: agregar servidores sin tocar el toml

- Vista de formulario (nombre, host[:puerto]) con estado "detectando…".
- Autodetección: primero Java (con SRV), luego Bedrock (UDP 19132). Si ninguna responde, se guarda como "desconocida" con aviso y se reintenta en cada poll. La edición detectada se guarda en la config.
- `probe` gana soporte Bedrock.
- La app escribe `config.toml`. Si el archivo tiene un error de sintaxis, se usan defaults sin sobrescribirlo.
- **Prueba:** agregar un servidor Java y uno Bedrock desde la UI. Ambos aparecen con su estado y persisten al reiniciar.

## 3. `server-detail`: quién está jugando, renombrar y eliminar

- Vista de detalle según `reference/server.png`: volver, cabecera con icono, MOTD, versión y latencia, y participantes.
- Tres modos de participantes:
  - `full`: lista de nombres.
  - `partial`: "5 de 23 jugadores".
  - `hidden`: "Este servidor no comparte la lista de jugadores".
- Query primero, con `query_capable` guardado por servidor (se reintenta cada ~10 polls si falla). Si no hay Query, se usa la muestra del ping.
- Filtro de muestras falsas: UUID nulo, códigos `§`, nombres que no cumplen `[A-Za-z0-9_]{3,16}`.
- `full` cuando Query responde o cuando `len(sample) == online`. `partial` cuando la muestra es menor que online. `hidden` cuando no hay muestra o el servidor es Bedrock.
- Renombrar inline (click en el nombre) y eliminar con confirmación.
- MOTD: `Motd.to_html()` de mcstatus 14 no escapa el texto, así que Python envía segmentos (texto, color y estilos) y la UI los pinta con `textContent`.
- Servidores "dormidos" (Aternos y similares): su proxy responde al ping aunque el servidor esté apagado, con un MOTD o una versión tipo "Offline" y 0 jugadores, y hoy `mc-watch` los marca online. Capturado con un Aternos apagado: `protocol = -1` y versión `"§c● Offline"`. Regla: `protocol == -1` y la versión contiene "offline" o "sleeping" → offline de inmediato, y el detalle explica que el servidor está apagado.
- **Prueba:** un servidor pequeño muestra nombres, uno grande muestra "12 de N" y uno Bedrock muestra "no comparte". Renombrar y eliminar persisten.

## 4. `notifications`: enterarme sin abrir el panel

- Toggle global, apagado por defecto.
- Eventos:
  - "Alguien está jugando": el servidor pasa de 0 a 1 o más jugadores.
  - "X entró": **solo si `players_mode == full`**. La muestra parcial rota al azar y generaría falsos "entró".
  - El servidor se cayó o volvió a estar online.
- Cada evento se notifica una sola vez. Más de tres en un mismo poll se agrupan.
- **Prueba:** entrar con una cuenta propia a un servidor monitoreado y recibir la notificación.

## 5. `distribution`: usarlo de verdad

- `build.py` genera un `.exe` portable.
- Autostart desde el menú de la bandeja (clave `Run` de HKCU).
- Workflow de release en GitHub Actions: check-version, build, tag y release.
- **Prueba:** descargar el `.exe` de un release, activar el autostart, reiniciar y ver que arranca solo.

## Fuera del MVP

- Lista de amigos y filtro de notificaciones por nombre.
- Editar el host de un servidor existente (solo se puede renombrar).
- Linux y macOS.
- Servidores anteriores a 1.7 (`LegacyServer`).

## Decisiones de corte

- Bedrock entra en el change 2, no en el 1: el skeleton queda más chico y Bedrock solo tiene sentido junto con la autodetección.
- Query entra en el change 3, no en el 4: es la fuente del modo `full` y el detalle es donde primero se ve si funciona.
- Cada change se crea con OpenSpec cuando llega su turno, no antes. Lo que se aprenda en los anteriores puede cambiar su diseño.
