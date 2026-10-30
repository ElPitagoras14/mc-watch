## 1. Configuración y poller

- [x] 1.1 En `mc_watch/config.py`, agregar `set_address(directory, old, new, edition, name=None)` que edite en una sola escritura atómica la entrada identificada por `old` (D5). Test en `tests/test_config_edit.py`: con tres entradas y comentarios, cambiar la segunda modifica solo su `address` y `edition` (y `name` cuando se pasa) y deja lo demás idéntico; si la entrada no existe lanza `ConfigWriteError`.
- [x] 1.2 En `mc_watch/poller.py`, agregar `Poller.change_address(address, server, result)` que reemplace el estado del índice por `next_status(initial_status(server), result)` y publique el snapshot (D6). Test en `tests/test_poller.py`: el servidor conserva su posición, el estado parte de cero con el resultado sembrado, y el resultado de un ciclo en vuelo que consultaba la dirección anterior no lo pisa.

## 2. ServerManager

- [x] 2.1 En `mc_watch/servers.py`, agregar `ServerManager.change_address(address, new_address)` con el flujo de D3 y D4: validar excluyendo la dirección propia, exigir config escribible, detectar con `poller.submit`, rechazar `ProbeUnresolvable` con "No se encontró el host" (campo `address`), escribir con `set_address`, actualizar `_editions` y llamar al poller; responder `{"ok": True, "address", "name"}` o el error. Tests en `tests/test_servers.py`: cambio correcto (archivo y poller), dirección duplicada, dirección sin cambios sin escribir ni sondear, cambio solo de mayúsculas permitido, host inexistente sin cambios, config no escribible o fallo de escritura sin cambios, nombre igual a la dirección que sigue a la nueva, edición reiniciada y guardada.
- [x] 2.2 Test en `tests/test_notify.py`: `notices` no genera nada entre un snapshot con la dirección anterior y uno con la dirección nueva del mismo servidor.

## 3. Página

- [x] 3.1 Exponer `change_address` en `mc_watch/window.py` (`Panel` y `Api`) y cablearla en `mc_watch/app.py` (D8). Sin test propio: `tests/test_window.py` no cubre ninguna de las delegaciones análogas (`add_server`, `rename_server`) y esta es la misma delegación de una línea. Verificar que `uv run pyright` pasa.
- [x] 3.2 En `mc_watch/ui/index.html` y `styles.css`, convertir la línea de dirección del detalle en span enfocable más lápiz más input oculto (D1), con estilo coherente con el título editable (lápiz visible, con foco de teclado y deshabilitado mientras guarda). Verificar en `uv run python -m mc_watch.preview` que la dirección y el lápiz se ven bien en el ancho del panel, con una dirección larga recortada.
- [x] 3.3 En `mc_watch/ui/app.js`, implementar la edición (D2, D7): iniciar con click, Enter/Espacio o lápiz; Enter guarda con el campo deshabilitado mientras espera; Escape y perder el foco cancelan; los errores van al área de error del detalle con el campo abierto; `state.addressTarget` evita que `render` cierre el detalle; `leaveDetail`, `openConfirm` y `onEscape` terminan la edición. Agregar al preview la simulación (D8) y verificar en `mc_watch.preview` el flujo completo: cambio correcto, cancelar con Escape, dirección duplicada, vacía, `.invalid` y "fail".

## 4. Verificación final

- [x] 4.1 Con la app real (`MC_WATCH_CONFIG_DIR=local/demo`), cambiar la dirección de un servidor a otra válida y a una inexistente: se conserva el nombre y el lugar, el detalle sigue abierto, no hay notificaciones y `config.toml` queda con solo esa entrada cambiada.
- [x] 4.2 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio.
