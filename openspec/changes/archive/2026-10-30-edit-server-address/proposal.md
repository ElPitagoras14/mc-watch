## Why

Si un servidor cambia de IP o de puerto, hoy no hay forma de corregirlo desde el panel: hay que eliminarlo y agregarlo de nuevo (perdiendo el nombre y su lugar en la lista) o editar `config.toml` a mano. El nombre ya se cambia con un click en el detalle; la dirección debería poder cambiarse igual de fácil.

## What Changes

- En el detalle, la dirección (`host` o `host:puerto`) se vuelve editable en línea, igual que el nombre: click o Enter sobre ella —o sobre un lápiz visible a su lado— la convierte en un campo; Enter guarda y Escape cancela.
- La dirección nueva pasa las mismas validaciones que el alta (obligatoria, formato `host[:puerto]`, sin duplicados) y, como en el alta, el sistema comprueba que el host resuelva antes de guardar.
- El servidor conserva su nombre y su lugar en la lista. Su estado se reinicia —la edición vuelve a detectarse— y se consulta al instante, sin esperar al siguiente ciclo y sin generar notificaciones.
- El cambio se guarda en `config.toml` sobre la misma entrada, conservando comentarios y orden.

### Non-goals

- Campos separados para IP y puerto: es un solo campo `host:puerto`, como en el formulario de alta.
- Editar la dirección desde la lista o desde el formulario de alta.
- Mantener el historial o las estadísticas del servidor con la dirección vieja (la app no guarda historial).

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `server-management`: nuevo requisito para cambiar la dirección de un servidor desde el detalle.
- `server-config`: la escritura de `config.toml` también puede cambiar el `address` de una entrada existente.

## Impact

- Código: `mc_watch/config.py` (escritura de la dirección), `mc_watch/servers.py` (validar, detectar y guardar), `mc_watch/poller.py` (sustituir el servidor conservando su posición), `mc_watch/window.py` y `mc_watch/app.py` (exponer la operación a la página) y la UI (`mc_watch/ui/index.html`, `app.js`, `styles.css`, más el soporte del preview).
- Sin dependencias nuevas ni cambios de formato en `config.toml`.
