## Why

Para saber si alguien está jugando hoy hay que abrir el panel. La pregunta que motiva la app ("¿entró alguien?") debería llegar sola, como notificación de Windows. Además, el intervalo de sondeo solo se puede cambiar editando `config.toml` a mano, y el panel crece hasta su alto máximo antes de hacer scroll, sin que el usuario pueda elegir cuántos servidores ver de una vez.

## What Changes

- **Notificaciones de Windows** (apagadas por defecto) para estos eventos, comparando cada snapshot con el anterior:
  - "Alguien está jugando": un servidor online pasa de 0 a 1 o más jugadores.
  - "X entró": un nombre nuevo en la lista de participantes, **solo con `players_mode == full`** en ambos snapshots. La muestra parcial rota al azar y generaría falsos "entró". Cuando hay nombres, reemplaza a "Alguien está jugando".
  - "Se cayó": un servidor online pasa a offline o error.
  - "Volvió": un servidor offline o en error pasa a online.
- Cada evento se notifica una sola vez: sale de una transición entre dos snapshots, no del estado. El primer ciclo tras iniciar no notifica nada, ni tampoco un servidor recién agregado.
- Si un mismo snapshot produce más de tres eventos, se agrupan en una sola notificación.
- Click en una notificación: abre el panel en el detalle de ese servidor; en la agrupada, en la lista.
- **Diálogo de ajustes**: un botón de engranaje en la cabecera de la lista abre un diálogo dentro del panel con:
  - Notificaciones (activar o desactivar).
  - Segundos entre consultas (30 a 3600).
  - Servidores visibles: cuántas filas muestra la lista antes de hacer scroll (3 a 20).
  - Guardar y Cancelar. Guardar escribe `config.toml` y aplica los valores al instante, sin reiniciar.
- `config.toml` gana las claves `notifications` y `max_visible_servers`.
- Escape con el diálogo abierto lo cierra sin guardar.
- El preview simula el diálogo de ajustes.

### Non-goals

- Lista de amigos y filtro de notificaciones por nombre (fuera del MVP).
- Notificar por servidor (activar o silenciar uno solo).
- "X salió": el roadmap no lo pide y duplicaría el ruido.
- Autostart: llega en el change 5. El diálogo de ajustes queda listo para sumarlo.

## Capabilities

### New Capabilities

- `notifications`: qué eventos se notifican, cuándo (transiciones, sin repetir, sin avalancha al iniciar), la agrupación, el click y qué pasa si Windows no puede mostrarlas.
- `settings`: el diálogo de ajustes, sus campos y límites, guardar y cancelar, y la aplicación inmediata de los valores.

### Modified Capabilities

- `server-config`: formato con `notifications` y `max_visible_servers`, límite superior del intervalo y escritura de las claves de ajustes.
- `monitor-ui`: botón de ajustes en la cabecera, alto de la lista según los servidores visibles y el diálogo en el preview.
- `tray-app`: Escape con el diálogo abierto lo cierra sin ocultar el panel.

## Impact

- Código:
  - `notify.py` (nuevo): cálculo puro de los eventos y emisión con `desktop-notifier`.
  - `config.py`: lectura y escritura de los ajustes.
  - `settings.py` (nuevo): validar y guardar los ajustes desde el diálogo.
  - `poller.py`: cambiar el intervalo en caliente.
  - `app.py`, `window.py`, `view.py`: cableado, API del diálogo y apertura del detalle desde una notificación.
  - UI: `index.html`, `app.js`, `styles.css`; `preview.py`.
- Dependencias: `desktop-notifier` (la misma versión que usa pr-watch, 6.2.0), que en Windows usa las notificaciones nativas (WinRT).
- Sin cambios de red ni de sondeo.
