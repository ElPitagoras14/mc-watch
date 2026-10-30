## 1. Detección

- [x] 1.1 En `mc_watch/probe.py`, añadir las frases de lazymc (`"server is sleeping"`, `"server is starting"`, `"server going to sleep"`) y hacer que `_is_asleep` reciba el MOTD y devuelva verdadero si su texto plano en `casefold` contiene alguna, además de la regla actual de Aternos; actualizar el comentario de `ASLEEP_*` y el docstring de `ProbeAsleep` en `mc_watch/models.py` para mencionar lazymc. Se verifica con los tests de 1.2.
- [x] 1.2 En `tests/test_probe_detail.py` (`AsleepTest`), añadir un test con la respuesta real de lazymc dormido (protocolo 777, versión "26.3", 0/0, MOTD "☠ Server is sleeping\n§2☻ Join to start it up") que espere `ProbeAsleep()`, y otro con el MOTD de arranque "§2☻ Server is starting...\n§7⌛ Please wait..." que también espere `ProbeAsleep()`.

## 2. Verificación final

- [x] 2.1 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, todo en verde.
- [x] 2.2 Con Kokoa apuntando a `192.168.1.100:25555` y el servidor real apagado, arrancar la app y comprobar que aparece offline y marcado como dormido.
