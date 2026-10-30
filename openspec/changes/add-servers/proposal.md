## Why

Hoy la única forma de agregar un servidor es editar `config.toml` a mano, saber dónde está y conocer de antemano si el servidor es Java o Bedrock. Para un jugador, lo natural es pegar la dirección que le pasó un amigo y que la app se encargue del resto. El walking skeleton ya dejó el botón agregar en la cabecera, deshabilitado; este change lo hace funcionar.

## What Changes

- El botón agregar de la cabecera se habilita y abre una vista de formulario dentro del mismo panel, con los campos nombre y dirección (`host` o `host:puerto`).
- Al enviar el formulario, la app detecta la edición del servidor mientras muestra "Detectando…": primero Java (con SRV) y, si no responde, Bedrock (UDP, puerto 19132 por defecto).
  - Si responde una de las dos, el servidor se agrega con esa edición.
  - Si el host no resuelve por DNS, el formulario muestra un error y no guarda nada.
  - Si el host resuelve pero ninguna edición responde, el servidor se agrega como edición "desconocida", con un aviso, y la detección se reintenta en cada ciclo de sondeo hasta que una responda.
- `probe` gana soporte para Bedrock. El sondeo periódico consulta cada servidor con el protocolo de su edición.
- La config gana el campo `edition` por servidor (`java`, `bedrock` o `unknown`). Una entrada sin `edition` se trata como desconocida y se autodetecta. La edición detectada se guarda en el archivo.
- **La app pasa a escribir `config.toml`**, conservando los comentarios y el formato que el usuario haya puesto a mano. Si el archivo tiene un error de sintaxis, la app sigue usando los valores por defecto, no lo sobrescribe y el formulario avisa que no se puede guardar.
- Un botón actualizar junto al de agregar fuerza un ciclo de sondeo inmediato.
- El servidor agregado aparece en la lista de inmediato, sin reiniciar la app ni esperar al siguiente ciclo.
- La fila de un servidor Bedrock lo indica, y la de uno de edición desconocida muestra el aviso.
- El estado vacío invita a usar el botón agregar en lugar de remitir al archivo.

### Non-goals

- Renombrar y eliminar servidores (change 3, `server-detail`). Hasta entonces, un servidor agregado por error se quita editando el toml.
- Editar la dirección de un servidor existente (fuera del MVP).
- Recargar la config cuando el usuario la edita a mano con la app abierta. Los cambios manuales se siguen tomando al reiniciar.
- Cambiar la edición de un servidor ya detectado. Solo los de edición desconocida se vuelven a detectar.

## Capabilities

### New Capabilities

- `server-management`: alta de servidores desde la UI. Cubre el formulario, la validación de nombre y dirección, los duplicados, la detección de edición al agregar y el resultado de cada caso. Los changes siguientes sumarán aquí renombrar y eliminar.

### Modified Capabilities

- `server-config`: la app pasa a escribir el archivo; aparece el campo `edition`; con un error de sintaxis se bloquea la escritura.
- `server-probing`: sondeo de Bedrock, sondeo según la edición configurada, autodetección en cada ciclo para los servidores de edición desconocida y sondeo a demanda.
- `monitor-ui`: aparece el botón actualizar, el botón agregar se habilita, el estado vacío cambia de texto, las filas indican la edición Bedrock o desconocida y el preview incluye el formulario.
- `tray-app`: Escape vuelve a la lista cuando el formulario está abierto, en lugar de ocultar el panel.

## Impact

- Código: `models.py` (edición, `ServerConfig.edition`, edición en `ProbeOk`), `probe.py` (Bedrock y detección), `state.py`, `config.py` (escritura), `poller.py` (agregar servidores en caliente), `app.py`, `window.py` (`js_api` para agregar), `view.py`, `ui/*`, `preview.py`.
- Dependencias: se agrega `tomlkit`, para escribir el TOML sin perder los comentarios del usuario.
- Red: además de TCP al 25565 o al puerto del SRV, datagramas UDP salientes al 19132 o al puerto indicado.
- Disco: la app escribe `config.toml` (escritura atómica). La primera vez que corre sobre una config escrita a mano, agrega `edition` a las entradas que no lo tienen en cuanto las detecta.
