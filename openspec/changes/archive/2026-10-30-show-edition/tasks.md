## 1. UI

- [x] 1.1 En `mc_watch/ui/app.js`, agregar `editionLabel()` y usarla en la fila (siempre el `<span>`) y en `dFacts` del detalle (siempre, también offline) (D1, D2, D3). Verificar en `uv run python -m mc_watch.preview`:
  - la fila de un servidor Java muestra "· Java", la Bedrock "· Bedrock" y la desconocida "· edición desconocida" en ámbar;
  - el detalle de un servidor Java online muestra "Java" junto a versión y latencia;
  - el detalle de un servidor offline sigue mostrando su edición.

## 2. Verificación final

- [x] 2.1 Con `MC_WATCH_CONFIG_DIR=local/demo` y la app real, ver "Java" en la fila y el detalle de los servidores de la config demo.
- [x] 2.2 Ejecutar `uv run python -m unittest`, `uv run ruff check`, `uv run ruff format --check` y `uv run pyright`, y verificar que pasan en limpio.
