## Context

Lo que el código ya ofrece y este change aprovecha:

- `Poller` publica un `Snapshot` a sus suscriptores en el hilo del poller, al terminar cada ciclo y también tras `add`, `rename`, `remove` y `refresh_server` (snapshots "de membresía", con el mismo `updated_at`).
- `ServerStatus` ya trae `state`, `online`, `players_mode` y `players` (nombres filtrados). `next_status` aplica la regla de dos fallos, así que un `OFFLINE` en el snapshot ya es una caída confirmada.
- `config.py` lee con `tomllib` y escribe con `tomlkit` dentro de `_update()`, que parte del archivo en disco, bajo lock y de forma atómica. `Config` es inmutable y `App` guarda el que leyó al iniciar.
- `Poller._main()` espera `interval - duración` entre ciclos con `_wait_for_next_cycle`, que ya se despierta por `stop_event` o `refresh_event`.
- La UI tiene tres vistas (`list`, `form`, `detail`) en `showView()`, y el alto de la ventana sale de `naturalHeight()`, que cuenta la lista por su `scrollHeight`.
- pr-watch (proyecto hermano) ya emite notificaciones con `desktop-notifier` 6.2.0 en un bucle asyncio propio. En Windows registra un AppUserModelID en `HKCU\Software\Classes\AppUserModelId` y usa WinRT. Ese patrón funciona con la app sin empaquetar.

## Goals / Non-Goals

**Goals:**

- Cálculo de eventos en una función pura, testeable sin Windows: `(snapshot anterior, snapshot nuevo) → avisos`.
- Ninguna notificación repetida ni avalancha al iniciar o al activar el ajuste.
- Ajustes aplicados en caliente, sin reiniciar el poller.
- Que fallar al notificar nunca afecte al sondeo.

**Non-Goals:**

- Persistir qué se notificó entre reinicios: los eventos son transiciones y el primer ciclo es la línea base.
- Icono propio en la notificación: Windows muestra el nombre registrado ("mc-watch").
- Activación desde el Centro de actividades una vez que la app se cerró.

## Decisions

### D1 - Eventos por transición entre snapshots consecutivos

`notify.py` define:

```python
@dataclass(frozen=True)
class Notice:
    title: str
    body: str
    address: str | None  # None: la agrupada, abre la lista


def notices(prev: Snapshot, curr: Snapshot) -> list[Notice]: ...
```

Se emparejan los servidores por `address.casefold()`. Un servidor que no está en `prev` (recién agregado) se ignora. Para cada par:

| prev | curr | aviso |
|---|---|---|
| `ONLINE` | `OFFLINE`/`ERROR` | "<nombre> se cayó" |
| `OFFLINE`/`ERROR` | `ONLINE` | "<nombre> volvió a estar online" |
| `ONLINE`, full | `ONLINE`, full, nombres nuevos | "<j1>, <j2> entró/entraron a <nombre>" |
| `ONLINE`, `online == 0` | `ONLINE`, `online >= 1`, sin nombres nuevos notificados | "Alguien está jugando en <nombre>" |

`QUERYING` en `prev` nunca genera nada: cubre el primer ciclo y cualquier servidor sin respuesta aún. Los nombres se comparan con `casefold`. "Entró" y "Alguien está jugando" son excluyentes para un mismo servidor y snapshot: si hay nombres nuevos, gana "entró".

Se comparan **todos** los snapshots publicados, también los de membresía: `refresh_server` puede traer un cambio real, y un renombrado no cambia el estado, así que no genera nada. El título de cada aviso es el nombre del servidor y el cuerpo es el evento; en la agrupada, el título es "mc-watch: N novedades" y el cuerpo nombra los tres primeros servidores ("Survival, Hypixel, Lobby y más").

Alternativa descartada: guardar "hechos ya notificados" por servidor como pr-watch. Allí hace falta porque un PR puede seguir "listo para fusionar" muchos ciclos y la app se reinicia a menudo. Aquí los eventos son cambios y la transición ya ocurre una sola vez.

### D2 - `Notifications`: suscriptor con el último snapshot y la emisión

`notify.Notifications` se suscribe al poller. Guarda el último snapshot visto y en cada publicación calcula `notices(prev, curr)`, reemplaza `prev` y, si el ajuste está activo, agrupa (`GROUP_ABOVE = 3`) y emite. Como `prev` se actualiza siempre, aunque el ajuste esté apagado, activarlo no dispara nada de lo ya ocurrido. El estado `enabled` se cambia con un método llamado desde el guardado de ajustes.

La emisión sigue el patrón de pr-watch: un bucle asyncio en un hilo daemon propio, creado la primera vez que se emite, y `DesktopNotifier(app_name="mc-watch").send(title=, message=, on_clicked=)`. Un fallo de `send` se registra una sola vez (`broken = True`) y deja de intentarlo hasta que el ajuste se vuelva a activar. El import de `desktop_notifier` es perezoso para que los tests y el preview no lo necesiten.

No se emite desde el hilo del poller: `send` es una corrutina de otro bucle, y si el poller esperara a WinRT, un toast lento retrasaría el ciclo.

### D3 - Click: abrir el panel en el detalle

`on_clicked` llama a `App.open_server(address)`, que hace `panel.show()` y luego `panel.open_detail(address)`. Este último evalúa `mcw.openDetail(address)` en la página. En JS, `openDetail` ya existe; se expone en `window.mcw` y, si el servidor no está en el payload, muestra la lista. Para la agrupada (`address=None`) solo se muestra el panel con la lista. Si hay un formulario a medias o el diálogo de ajustes abierto, el click en la notificación los cierra sin guardar: el usuario pidió ver algo concreto.

### D4 - Ajustes en `config.toml`

`Config` gana `notifications: bool = False` y `max_visible_servers: int = 8`, con su parseo en el estilo de `_parse_interval` (advertencias en el log, límites 3–20). `_parse_interval` suma el tope de 3600.

`config.save_settings(directory, settings)` usa `_update()` y escribe las tres claves de primer nivel. tomlkit agrega una clave nueva de primer nivel antes de la primera tabla, y la actualiza en su sitio si ya existe; un test lo fija para no depender de eso sin verlo. La función devuelve si escribió algo.

```python
@dataclass(frozen=True)
class Settings:
    notifications: bool
    poll_interval_secs: int
    max_visible_servers: int
```

`Settings` vive en `config.py` junto a sus límites (`MIN/MAX_POLL_INTERVAL_SECS`, `MIN/MAX_VISIBLE_SERVERS`) y `Config.settings` lo construye.

### D5 - `SettingsManager`: validar, guardar, aplicar

`settings.py` expone `SettingsManager(directory, config, poller, notifications)` con `save(raw: dict) -> Reply`, llamado desde la página:

1. Valida cada campo (`bool`; enteros, rechazando `bool` y decimales) y devuelve `{"ok": False, "field": ..., "message": "Entre 30 y 3600"}` en el primero que falle.
2. Si la config no es escribible (`Config.writable` es `False`), devuelve el error del archivo.
3. Escribe con `save_settings`; un `ConfigWriteError` vuelve como error general sin aplicar nada.
4. Aplica: `notifications.set_enabled(...)`, `poller.set_interval(...)` y guarda el `Settings` vigente, que `view.snapshot_payload` incluye en cada payload como `settings`. Luego pide a la app que publique el payload para que la lista adopte el alto nuevo.

Como `ServerManager`, nunca lanza y usa un lock propio.

### D6 - Intervalo en caliente

`Poller.set_interval(secs)` cambia `_interval_secs` en el bucle del poller y despierta la espera con un `_reschedule_event`. `_main` pasa a esperar en un bucle: tras despertar por reprogramación, recalcula `interval - (ahora - inicio del ciclo anterior)` y, si es `<= 0`, arranca el ciclo; si no, vuelve a esperar lo que falta. Así "acortar a 30 s cuando el anterior empezó hace 40 s" cicla de inmediato y alargar no dispara un ciclo extra. `refresh` sigue como estaba.

### D7 - UI: diálogo modal dentro del panel

- Botón `#btn-settings` con el glifo engranaje (`&#xE713;`, Segoe Fluent) entre agregar y fijar. Visible solo en la vista `list`.
- `<div id="settings" role="dialog" aria-modal="true">` con un fondo que cubre el panel bajo la cabecera y una tarjeta con los tres campos, un aviso de archivo roto, los errores por campo y Cancelar/Guardar. No se usa `<dialog>` nativo: `showModal()` en WebView2 funciona, pero su `::backdrop` y el foco se pelean con el blur que oculta el panel; un `div` es más simple de controlar.
- `state.settingsOpen` es un estado aparte de la vista: el diálogo vive sobre la lista. Mientras está abierto, el resto queda `inert`. El foco va al primer campo y Tab queda dentro del diálogo gracias a `inert`.
- Escape: el diálogo va primero en `onEscape()`, antes que renombrar y la confirmación (no pueden coexistir, pero el orden lo deja explícito).
- Guardar está deshabilitado mientras la llamada está en curso, y siempre si el payload trae `config_error`.
- Alto: `naturalHeight()` devuelve `max(alto actual, alto de cabecera + alto de la tarjeta + márgenes)` mientras el diálogo está abierto.
- Servidores visibles: `render()` calcula el alto máximo de `#list` como `N × alto de fila` (más los huecos entre filas) a partir de la primera fila medida, y `naturalHeight()` cuenta la lista por `min(scrollHeight, ese máximo)`. El tope de la ventana (`MAX_HEIGHT`) sigue aplicando.

### D8 - Preview

El preview incluye `settings` en sus payloads. `saveSettings` simulado valida igual que Python (los mismos rangos y mensajes), cierra el diálogo y re-renderiza con los ajustes nuevos sin escribir nada. No se simulan notificaciones: son del sistema.

## Risks / Trade-offs

- [Un servidor que oscila entre online y offline genera una notificación por vuelta] → La regla de dos fallos ya filtra los cortes de un solo ciclo. Si molesta en la práctica, se puede sumar un enfriamiento por servidor más adelante.
- [La notificación "volvió" de muchos servidores al recuperar el wifi] → La agrupación de más de tres la reduce a una.
- [WinRT no disponible o las notificaciones bloqueadas por el usuario en Windows] → Se registra una vez y se sigue sin notificar (D2).
- [desktop-notifier registra un AppUserModelID en HKCU] → Es una clave de presentación inofensiva; la misma que deja pr-watch.
- [Click en una notificación que ya está en el Centro de actividades con la app cerrada] → No hace nada; fuera de alcance.

## Migration Plan

Sin migración: las claves nuevas son opcionales y sus valores por defecto reproducen el comportamiento actual (sin notificaciones). La lista pasa a mostrar hasta 8 filas antes de hacer scroll; antes crecía hasta el alto máximo de la ventana, que equivale a unas 9.

## Open Questions

Ninguna.
