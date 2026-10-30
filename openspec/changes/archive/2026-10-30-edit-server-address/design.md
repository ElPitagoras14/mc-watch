## Context

Ver `proposal.md` (Why). Piezas relevantes de hoy:

- La dirección es la identidad del servidor: `config.py` localiza la entrada por `address` (`_find_entry`), el poller por `_index_of`, las notificaciones comparan snapshots por dirección y la UI guarda en `state.detail` la dirección del detalle abierto.
- El renombrado (`ServerManager.rename_server` → `config.set_name` + `Poller.rename`) ya es el patrón: valida, escribe `config.toml` y actualiza el poller, que publica un snapshot al instante. La UI lo expone con un campo en la cabecera.
- El alta (`ServerManager._add`) detecta la edición enviando un sondeo al poller (`submit`) con tope de `DETECT_TIMEOUT_SECS`, y siembra el estado con `Poller.add(server, result)`.
- Al terminar un ciclo, el poller fusiona por dirección: lo que ya no está en la lista viva se descarta y lo vivo conserva su nombre, así que un sondeo en vuelo de una dirección que cambió no puede pisar nada.
- `notices()` ignora los servidores cuya dirección no estaba en el snapshot anterior (la regla de "recién agregado"), y un servidor que pasa de Consultando a otro estado no notifica.

## Goals / Non-Goals

**Goals:**

- Cambiar la dirección con el mismo gesto y el mismo flujo que el renombrado, reutilizando lo que ya existe para validar, detectar y escribir.

**Non-Goals:**

- Cambiar cómo se identifican los servidores (la dirección sigue siendo la clave).
- Editar otros campos (edición, orden) desde el detalle.

## Decisions

### D1 - Un solo campo `host:puerto`, editado en línea con un lápiz

La línea de dirección del detalle pasa a ser un `<span>` enfocable (`tabindex="0"`, como el título) con un botón de lápiz al lado, más un `<input>` oculto que lo reemplaza al editar. Click o Enter/Espacio sobre cualquiera de los dos inicia la edición; el lápiz existe solo para que el gesto se descubra.

Alternativas descartadas: dos campos IP y puerto (el resto de la app maneja una sola cadena y el alta ya usa `host[:puerto]`); reabrir el formulario de alta precargado (más pesado que editar en línea y duplica la vista).

### D2 - Enter guarda, Escape cancela y perder el foco cancela

A diferencia del nombre (donde perder el foco guarda), guardar una dirección dispara una consulta de red de hasta unos segundos y puede fallar; un click suelto o el panel que se oculta al perder el foco no deben lanzarla. Mientras se guarda, el campo queda deshabilitado y Escape se ignora. Un error (validación, DNS, escritura) se muestra en el área de error del detalle y deja el campo abierto con lo escrito.

### D3 - Detección como en el alta, con la edición reiniciada

`ServerManager.change_address(address, new_address)` hace, bajo el lock del manager: (1) valida con las reglas del alta contra las demás direcciones —la propia no cuenta, de modo que cambiar solo mayúsculas y minúsculas es válido—, (2) comprueba que la config sea escribible, (3) sondea el servidor nuevo con edición desconocida por `poller.submit`, igual que `_add`, (4) rechaza con "No se encontró el host" si es `ProbeUnresolvable`, (5) escribe `config.toml` y (6) pide al poller el reemplazo. La edición se reinicia porque otra dirección puede ser otro tipo de servidor; si nadie responde queda `unknown` y el ciclo normal la persistirá cuando alguien responda (`on_snapshot`). `_editions` se actualiza antes de llamar al poller, como en `_add`, para que `on_snapshot` no confunda el reemplazo con una detección nueva.

Se reutiliza `validate_new_server` para no duplicar las reglas; el nombre que devuelve se ignora porque el servidor conserva el suyo (D4).

### D4 - El nombre se conserva, salvo que fuera la dirección

Un servidor sin nombre propio se llama como su dirección (`normalize_name`). Si al cambiar la dirección el nombre fuera exactamente la dirección anterior, quedaría mostrando una dirección que ya no existe; por eso en ese caso el nombre pasa a ser la dirección nueva. Cualquier otro nombre se conserva.

### D5 - `config.set_address`: misma entrada, mismas posiciones

`set_address(directory, old, new, edition, name=None)` localiza la entrada con `_find_entry` y modifica `address`, `edition` y, solo cuando D4 lo pide, `name`, todo en un solo `_update` atómico. No toca el resto del archivo, así que comentarios y orden se conservan como en el renombrado. Lanza `ConfigWriteError("El servidor ya no está en la configuración")` si la entrada desapareció.

### D6 - `Poller.change_address`: reemplazo en el mismo índice

Corre en el loop del poller como `rename` y `remove`: sustituye el `ServerStatus` del índice por `next_status(initial_status(nuevo), resultado)`, con lo que el estado, los jugadores y los contadores de fallo y de Query empiezan de cero, y publica el snapshot al instante. No hace falta tocar `_cycle`: su fusión por dirección ya descarta el resultado de un ciclo en vuelo que consultaba la dirección anterior, igual que con `remove`.

Notificaciones: el snapshot del reemplazo trae una dirección que el anterior no tenía, así que `notices()` no genera nada, y los siguientes parten de un estado ya sembrado, que no es `QUERYING` solo si la detección obtuvo respuesta. No hace falta tocar `notify.py`.

### D7 - El detalle sigue al servidor

El snapshot del reemplazo puede llegar a la página antes que la respuesta de `change_address`. Con `state.detail` aún apuntando a la dirección vieja, `render` no encontraría el servidor y cerraría el detalle (hoy eso significa "se eliminó"). Para evitarlo la UI guarda la dirección que está intentando guardar (`state.addressTarget`); si el detalle abierto ya no existe pero hay un servidor con esa dirección (sin distinguir mayúsculas), `state.detail` pasa a esa dirección en vez de salir. Al llegar la respuesta se asienta `state.detail` con la dirección devuelta y se limpia el objetivo.

### D8 - Superficie hacia la página

`change_address(address, new_address)` se expone igual que `rename_server`: `ServerManager` → `Panel` → `Api` en `window.py` y en `app.py`. Responde `{"ok": True, "address": ..., "name": ...}` o `{"ok": False, "field": "address", "message": ...}`. En el preview se simula como el renombrado: una dirección con "fail" simula una config no escribible y una `.invalid`, un host inexistente.

## Risks / Trade-offs

- [La consulta de detección puede tardar hasta `DETECT_TIMEOUT_SECS` y el campo queda deshabilitado] → Es el mismo comportamiento y tope que el alta; el campo muestra que está ocupado y el error de tiempo agotado deja la dirección anterior intacta.
- [Perder el foco cancela lo escrito, y el panel se oculta al perder el foco] → Es la contrapartida de no lanzar una consulta de red por accidente; una dirección es corta de reescribir.
- [Se pierde el estado anterior (jugadores, fallos acumulados)] → Es lo pedido: otra dirección es otro servidor a efectos de estado; el reinicio evita notificaciones espurias de transiciones que no ocurrieron.
- [Dos cambios o un cambio y una eliminación a la vez] → Todo pasa bajo el lock del manager y en el loop del poller; si la entrada ya no existe, la escritura falla con su mensaje y el poller ignora la dirección desconocida.
