## Why

Hoy `mc-watch` solo corre desde el código fuente con `uv`, y hay que lanzarlo a mano en cada sesión. Para usarlo de verdad hace falta un `.exe` que se descargue de un release, que arranque solo con Windows y que se comporte bien cuando se lanza con doble clic desde el Explorador.

## What Changes

- **Ejecutable portable**: `build.py` genera `dist/mc-watch.exe` (un solo archivo, sin consola, con icono y recurso de versión) con PyInstaller. La UI viaja dentro del ejecutable y el preview no.
- **Arrancar con la sesión**: entrada marcable "Arrancar con la sesión" en el menú de la bandeja. Escribe o borra un valor en la clave `Run` de HKCU. Viene apagada, solo está disponible en el ejecutable (desde el código fuente aparece deshabilitada) y refleja lo que hay en el registro. Si el `.exe` se movió, al arrancar se actualiza la ruta registrada.
- **Una sola instancia**: lanzar la app de nuevo con la misma carpeta de configuración no abre un segundo icono; muestra el panel de la instancia que ya corre y termina.
- **Menú de la bandeja fiable**: con el `.exe` lanzado desde el Explorador, el menú del clic derecho resalta la opción bajo el ratón y responde a los clics (la lección de pr-watch en `docs/lecciones-bandeja-windows.md`).
- **Release en GitHub Actions**: en cada push a `main`, `check-version` lee la versión (`pyproject.toml` y `mc_watch/__init__.py` deben coincidir y ser `MAJOR.MINOR.PATCH`); si el tag `v<versión>` no existe: verify (tests, ruff, pyright), build en Windows, tag y release con `mc-watch-<versión>-windows.exe` y notas generadas del log.
- El primer release será `v0.1.0`, la versión actual: se publicará al fusionar este change en `main`.
- README con instrucciones de descarga y uso.

### Non-goals

- Instalador, actualizaciones automáticas o firma de código.
- Builds de Linux o macOS (fuera del MVP).
- Autostart desde el diálogo de ajustes: el roadmap lo ubica en el menú de la bandeja.

## Capabilities

### New Capabilities

- `autostart`: iniciar con Windows desde el menú de la bandeja, su disponibilidad, el registro como fuente de verdad y la actualización de la ruta.
- `distribution`: el ejecutable portable y el pipeline de release (versión, tag, artefacto y notas).

### Modified Capabilities

- `tray-app`: el menú gana "Actualizar ahora" y "Arrancar con la sesión" (como el de pr-watch) y debe funcionar lanzado desde el Explorador; una sola instancia por carpeta de configuración.

## Impact

- Código:
  - `autostart.py` (nuevo): leer, escribir y refrescar el valor de la clave `Run`.
  - `single_instance.py` (nuevo): mutex y evento con nombre para detectar la instancia previa y pedirle el panel.
  - `tray.py`: entrada marcable de autostart y el `_on_notify` que fuerza el primer plano.
  - `app.py`, `__main__.py`: cableado de autostart y de la instancia única.
  - `build.py` (nuevo), `scripts/release_version.py` (nuevo), `.github/workflows/release.yml` (nuevo), `README.md`.
- Dependencias: `pyinstaller` en el grupo `dev`.
- Registro de Windows: solo `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\mc-watch`, y solo cuando el usuario lo activa.
