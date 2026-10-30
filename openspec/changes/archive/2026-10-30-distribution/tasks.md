## 1. Autostart

- [x] 1.1 Crear `autostart.py` con `Autostart` (D2). Tests en `tests/test_autostart.py` sobre una clave de prueba de HKCU:
  - activar y desactivar (desactivar dos veces no es error);
  - `refresh()` con otra ruta la reescribe sin duplicar, y sin entrada no la crea;
  - sin `frozen`, `available` es falso y `enable()` lanza `OSError` sin escribir.
- [x] 1.2 Sumar "Arrancar con la sesión" al menú de `Tray` y cablear en `app.py` `toggle_autostart()` y `refresh()` al arrancar (D3). Verificar con `uv run python -m mc_watch` que la entrada aparece deshabilitada.

## 2. Bandeja e instancia única

- [x] 2.1 Agregar a `tray.py` la subclase con el `_on_notify` que refresca el menú y fuerza el primer plano sobre `_menu_hwnd`, y activar Per-Monitor-V2 al arrancar (D4), y marcar la lección como aplicada en `docs/lecciones-bandeja-windows.md`. Verificar con la app que el menú sigue abriendo y respondiendo.
- [x] 2.2 Crear `single_instance.py` (D5) y usarlo en `__main__.py` y `app.py`. Tests en `tests/test_single_instance.py`:
  - la segunda adquisición con la misma carpeta devuelve `None` y activa `on_show` de la primera;
  - con otra carpeta, ambas adquieren.

## 3. Ejecutable y release

- [x] 3.1 Agregar `tray.app_icon()`, `build.py` (D1) y `pyinstaller` al grupo `dev`. Verificar que `uv run build.py` genera `dist/mc-watch.exe` con icono y versión en Propiedades, y agregar `dist/` y `build/` al `.gitignore` si faltan.
- [x] 3.2 Crear `scripts/release_version.py` (D6). Tests en `tests/test_release_version.py`:
  - versiones iguales → la imprime y la escribe en `GITHUB_OUTPUT`;
  - distintas → error que nombra ambas;
  - `0.1` → error de forma.
- [x] 3.3 Crear `.github/workflows/release.yml` (D6) y actualizar `README.md` con descarga, aviso de SmartScreen, autostart y ubicación de `config.toml`.

## 4. Verificación final

- [x] 4.1 Prueba de punta a punta con `dist/mc-watch.exe` lanzado con doble clic desde el Explorador:
  - el panel lista los servidores con su estado (incluido uno resuelto por SRV) y se puede agregar uno;
  - el menú del clic derecho resalta y responde;
  - activar "Arrancar con la sesión" crea el valor en `Run`, desactivarlo lo borra;
  - lanzar el `.exe` otra vez abre el panel existente sin segundo icono;
  - una notificación se muestra (por ejemplo, un servidor que vuelve a estar online).
- [x] 4.2 Actualizar `docs/roadmap.md` con lo que cambió respecto al plan del change 5 (instancia única y arreglo del menú).
- [x] 4.3 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio.
