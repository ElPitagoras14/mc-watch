# mc-watch

Monitor de servidores de Minecraft en la bandeja de Windows: ¿hay alguien jugando? ¿entró alguien?

## Instalar

1. Descarga `mc-watch-<versión>-windows.exe` desde [Releases](https://github.com/ElPitagoras14/mc-watch/releases).
2. Ejecútalo. Es portable: no hay instalador ni hace falta Python.
3. Aparece un icono en la bandeja con el número de servidores online. Click izquierdo abre el panel; click derecho, el menú.

Windows SmartScreen puede avisar de que el ejecutable no está firmado: elige **Más información → Ejecutar de todas formas**.

## Uso

- **Agregar un servidor:** botón `+` del panel. Detecta solo si es Java o Bedrock.
- **Detalle:** click en un servidor para ver quién juega, renombrarlo o eliminarlo.
- **Notificaciones:** engranaje del panel (apagadas por defecto).
- **Arrancar con la sesión:** entrada marcable del menú de la bandeja (apagada por defecto).

La configuración vive en `%APPDATA%\mc-watch\config.toml`, junto al log.

## Desarrollo

```bash
uv sync
uv run python -m mc_watch           # la app
uv run python -m mc_watch.preview   # la UI en el navegador, sin Windows
uv run build.py                     # dist/mc-watch.exe
```

Para otra carpeta de configuración: `MC_WATCH_CONFIG_DIR=local/demo`.

Un release se publica al fusionar en `main` un commit que sube la versión (en `pyproject.toml` y `mc_watch/__init__.py`).
