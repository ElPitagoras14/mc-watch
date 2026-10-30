## Context

- `__main__.main()` crea `App()` y llama a `run()`. `App` resuelve la carpeta de configuración con `config_dir()` (respeta `MC_WATCH_CONFIG_DIR`) y configura el log ahí.
- `window.UI_INDEX` se resuelve con `Path(__file__)`, así que basta con que la carpeta `ui` viaje junto al paquete dentro del ejecutable.
- `tray.Tray` usa `pystray.Icon` sin cambios. Su glifo se dibuja con `ImageFont.truetype` (necesita FreeType de Pillow). `docs/lecciones-bandeja-windows.md` documenta que, lanzado desde el Explorador, el menú del clic derecho no resalta ni responde, y cómo lo resolvió pr-watch.
- pr-watch (proyecto hermano) ya tiene `build.py`, `autostart.py`, `scripts/release_version.py` y `.github/workflows/release.yml` probados en releases reales. Este change los adapta: solo Windows y sin la parte de Linux.
- No hay tags en el repositorio. La versión actual es `0.1.0`.

## Goals / Non-Goals

**Goals:**

- Un `.exe` que se comporte igual que `uv run python -m mc_watch`.
- Autostart y release copiando lo que ya funciona en pr-watch, sin reinventar.
- Que la instancia de desarrollo (`MC_WATCH_CONFIG_DIR=local/demo`) pueda convivir con el `.exe` instalado.

**Non-Goals:**

- Reducir el tamaño del ejecutable más allá de excluir módulos que no se usan.
- Ejecutar el build en cada PR: el pipeline solo corre en `main`.

## Decisions

### D1 - `build.py` con PyInstaller `--onefile --windowed`

`build.py` en la raíz, ejecutado con `uv run build.py`, igual que en pr-watch:

- Un lanzador temporal (`from mc_watch.__main__ import main; sys.exit(main())`) como script de entrada, para que el paquete se importe como paquete y no como `__main__`.
- `--add-data mc_watch/ui;mc_watch/ui`, `--collect-submodules mc_watch`, `--collect-submodules desktop_notifier` y `--collect-submodules dns.rdtypes` (dnspython carga los tipos de registro de forma dinámica y la resolución SRV los necesita).
- `--exclude-module mc_watch.preview` y los módulos de Pillow que no se usan (AVIF, WebP, ImageCms, ImageTk/tkinter), además de `unittest`, `pydoc` y `doctest`. **No** se excluye `PIL._imagingft`: el icono de la bandeja dibuja texto.
- `--version-file` generado con la versión de `mc_watch.__version__`, como en pr-watch.
- `--icon` con un `.ico` generado al vuelo: `tray.app_icon()` devuelve el glifo sin número (anillo y punto) en el verde de la UI (`#3fb950`), legible tanto en el Explorador claro como en el oscuro. Si no se puede generar, el `.exe` sale sin icono y se avisa.
- `pyinstaller` se agrega al grupo `dev`.

Alternativa descartada: `--onedir`. Arranca algo más rápido, pero el roadmap pide un `.exe` portable que se descarga solo.

### D2 - `autostart.py`: la clave `Run` como única fuente de verdad

Port de la parte Windows de `pr_watch/autostart.py`:

```python
@dataclass
class Autostart:
    frozen: bool = field(default_factory=is_frozen)       # getattr(sys, "frozen", False)
    executable: str = field(default_factory=lambda: sys.executable)
    run_key: str = RUN_KEY                                 # Software\Microsoft\Windows\CurrentVersion\Run

    available -> bool       # == frozen
    current() -> str | None
    is_enabled() -> bool    # nunca lanza
    set_enabled(bool)       # lanza OSError; enable() falla si no está disponible
    refresh() -> bool       # al arrancar: reescribe si existe y apunta a otra ruta
```

El valor se llama `mc-watch` y contiene `"<ruta del exe>"` entre comillas. `run_key` es parametrizable para que los tests escriban en una clave propia de HKCU y no toquen la real. No se guarda nada en `config.toml`: si el usuario borra la entrada desde el Administrador de tareas, la app lo refleja.

### D3 - Entrada marcable en el menú y la marca siempre fresca

`Tray` recibe `on_autostart`, `autostart_on` y `autostart_available`. La entrada usa `checked=lambda _: autostart_on()` y `enabled=autostart_available`. pystray solo evalúa `checked` al reconstruir el menú, así que el `_on_notify` de D4 llama a `update_menu()` justo antes de abrirlo. Así no hace falta el refresco periódico de pr-watch.

`App.toggle_autostart()` invierte `is_enabled()`, registra en el log el resultado o el `OSError`, y no propaga. `App._start_background()` llama a `refresh()` y registra si actualizó la ruta.

### D4 - Menú del clic derecho: forzar el primer plano sobre `_menu_hwnd`

En `tray.py`, una subclase de `pystray.Icon` (solo cuando el backend es Win32) sobrescribe `_on_notify` para `WM_RBUTTONUP`, igual que pr-watch:

1. `update_menu()` (D3).
2. `AttachThreadInput` con el hilo del primer plano, `SetForegroundWindow(_menu_hwnd)` y espera de hasta 0,5 s en pasos de 10 ms a que `GetForegroundWindow() == _menu_hwnd`; desenganchar en `finally`.
3. `TrackPopupMenuEx(..., TPM_RETURNCMD)`, `PostMessage(WM_NULL)` y ejecutar el descriptor elegido.

El resto de mensajes (clic izquierdo) siguen por `super()._on_notify`.

Esto solo no basta con la pantalla escalada (125 % en la máquina de pruebas): el primer plano se logra y el menú igual no resalta, porque pywebview llama a `SetProcessDPIAware()`. Por eso `__main__.main()` activa antes Per-Monitor-V2 (`winutil.enable_per_monitor_dpi()`, `SetProcessDpiAwarenessContext(-4)`), y con eso pywebview ya no cambia el modo. Verificado con el panel: sigue colocándose junto a la bandeja. Se actualiza `docs/lecciones-bandeja-windows.md` para indicar que ya está aplicado.

### D5 - Una instancia por carpeta de configuración: mutex y evento con nombre

`single_instance.py`, con ctypes y sin dependencias:

- Nombre base: `Local\mc-watch-<8 hex>`, donde el sufijo es el SHA-1 de la ruta resuelta y en minúsculas de la carpeta de configuración. Así la instancia de `local/demo` convive con la normal (spec `tray-app`).
- `acquire(directory) -> Guard | None`: `CreateMutexW`; si devuelve `ERROR_ALREADY_EXISTS` o `ERROR_ACCESS_DENIED`, abre el evento `<base>-show`, hace `SetEvent` y devuelve `None`. Si no, crea el evento (auto-reset) y devuelve el `Guard`, que conserva ambos handles mientras vive el proceso.
- `Guard.serve(on_show)`: un hilo daemon espera el evento con `WaitForSingleObject` y llama a `on_show` cada vez que se activa. `Guard.close()` cierra los handles.

`__main__.main()` llama a `acquire(config_dir())` antes de crear `App`: si ya hay otra instancia, sale con 0 sin tocar el log. `App` recibe el guard y en `_start_background` lo sirve con `panel.show`.

Alternativa descartada: el canal `multiprocessing.connection` de pr-watch. Allí sirve también para Linux; aquí solo se necesita una señal de un bit, y un evento de Windows es más simple. Si falla `CreateMutexW` por otro motivo, se arranca igual y se registra: no poder garantizar la unicidad no debe impedir usar la app.

### D6 - Versión y pipeline de release

- `scripts/release_version.py`: port del de pr-watch (solo biblioteca estándar, lee `mc_watch/__init__.py` como texto, valida `MAJOR.MINOR.PATCH` y la coincidencia con `pyproject.toml`, y escribe `version=` en `$GITHUB_OUTPUT`). `tests/test_version.py` sigue cubriendo la coincidencia en local; el script cubre el pipeline.
- `.github/workflows/release.yml`, en push a `main`, con `concurrency: release`:
  1. `check-version` (ubuntu): versión y `git ls-remote` del tag; si existe, termina.
  2. `verify` (windows): `uv sync --locked`, `unittest`, `ruff check`, `ruff format --check`, `pyright`. En Windows porque `winreg`, `ctypes.windll` y los tests de registro lo requieren.
  3. `build` (windows): `uv run build.py`, renombrar a `mc-watch-<versión>-windows.exe` y subir el artefacto.
  4. `tag` (ubuntu): tag anotado sin `--force`.
  5. `release` (ubuntu): notas con `git log` desde el tag anterior y `gh release create`.
- Mismas versiones de acciones que pr-watch (`actions/checkout@v7`, `astral-sh/setup-uv@v10.3.3`, `upload-artifact@v7`, `download-artifact@v8`).

## Risks / Trade-offs

- [SmartScreen y antivirus marcan los `.exe` de PyInstaller sin firmar] → El README explica "Más información → Ejecutar de todas formas". Firmar queda fuera del MVP.
- [`--onefile` descomprime en `%TEMP%` en cada arranque y tarda un par de segundos] → Aceptable para una app de bandeja que se inicia una vez por sesión.
- [Un módulo cargado dinámicamente que PyInstaller no detecta rompe el `.exe` y no los tests] → La verificación final prueba el `.exe` real: estado de servidores (incluido SRV), agregar uno, notificación y autostart.
- [Fusionar este change publica `v0.1.0` en un repositorio público] → Es el objetivo del change; queda dicho en la propuesta.

## Migration Plan

Nada que migrar: la configuración en `%APPDATA%\mc-watch` es la misma desde el código fuente y desde el `.exe`. Para retirar un release defectuoso basta con borrarlo en GitHub junto con su tag y publicar una versión nueva.
