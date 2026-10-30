## Why

Un servidor detrás de [lazymc](https://github.com/timvisee/lazymc) mientras duerme sigue respondiendo al Server List Ping: lazymc contesta en nombre del servidor real con su versión y protocolo normales (por ejemplo "26.3" y 777), 0 jugadores y el MOTD "☠ Server is sleeping". Hoy la app solo reconoce el modo dormido de Aternos (protocolo `-1`), así que un servidor lazymc dormido aparece **online**, cuando en realidad nadie puede jugar hasta que alguien entre y lo despierte.

## What Changes

- Una respuesta Java se considera también de un servidor dormido cuando el MOTD, sin códigos de formato `§`, contiene uno de los textos por defecto de lazymc, sin importar mayúsculas: "server is sleeping" (dormido), "server is starting" (arrancando) o "server going to sleep" (apagándose). En esos tres estados el servidor real no acepta jugadores, así que los tres cuentan como dormido.
- La regla de Aternos (protocolo `-1` con "offline"/"sleeping" en la versión) no cambia.
- Un servidor lazymc dormido queda offline y marcado como dormido, igual que uno de Aternos, y fija la edición Java durante la autodetección.

### Non-goals

- Reconocer lazymc con MOTD personalizados (`[motd]` editado o `from_server = true`): no hay otra señal fiable en la respuesta.
- Un estado nuevo "arrancando" distinto de dormido.
- Despertar el servidor desde la app.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `server-probing`: el requisito "Servidores dormidos" añade el reconocimiento por MOTD de lazymc.

## Impact

- Código: `mc_watch/probe.py` (detección de dormido) y su test en `tests/test_probe_detail.py`.
- Sin cambios en la UI, en `config.toml`, en el payload ni en dependencias: `ProbeAsleep` ya existe y la UI ya muestra "dormido".
