## Why

Hoy la edición de un servidor solo se ve cuando no es Java: la fila de un servidor Java no lleva indicación y el detalle solo dice "Bedrock". Con una lista de servidores Java (el caso común) la app nunca muestra la edición, y el usuario no puede confirmar que se detectó bien ni distinguirla a simple vista de una edición desconocida.

## What Changes

- La fila de la lista muestra la edición de **todos** los servidores junto a la dirección: "· Java", "· Bedrock" o, si no se detectó, el aviso "· edición desconocida". Se elimina la regla de que la fila Java no lleva indicación.
- El detalle muestra la edición siempre, junto a la versión y la latencia: "Java", "Bedrock" o "edición desconocida". Antes solo aparecía "Bedrock".
- El preview ya cubre las tres ediciones; no hace falta cambiar sus datos.

### Non-goals

- Cambiar cómo se detecta o se guarda la edición (`server-management` y `server-config` quedan igual).
- Iconos o colores por edición: se usa el mismo texto atenuado que ya tiene "Bedrock".
- Editar la edición a mano.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `monitor-ui`: la fila de la lista indica la edición de todos los servidores, también Java.
- `server-detail`: el detalle indica siempre la edición del servidor.

## Impact

- Código: solo la UI, `mc_watch/ui/app.js` (render de la fila y de los datos del detalle).
- Sin cambios en Python, en `config.toml`, en dependencias ni en el payload: `edition` ya viaja en cada servidor.
