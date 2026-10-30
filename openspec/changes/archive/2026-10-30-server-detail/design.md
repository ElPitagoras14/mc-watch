## Context

Lo que el código ya ofrece y este change aprovecha:

- `probe.py` es el único módulo que importa `mcstatus`. Devuelve `ProbeOk(online, max, latency_ms, edition) | ProbeUnreachable | ProbeUnresolvable` y descarta todo lo demás de la respuesta.
- `state.next_status()` es puro: fija la edición de un servidor desconocido y aplica la regla de dos fallos.
- `Poller._cycle()` trabaja sobre una copia de `self._statuses` y une el resultado con `[*updated, *self._statuses[len(current):]]`. Eso funciona porque hoy la lista solo crece al final; al quitar un servidor a mitad de ciclo, las posiciones se corren.
- `ServerManager` (`servers.py`) agrega servidores: valida, escribe con `config.append_server` y llama a `poller.add`. `config._update()` hace la lectura-modificación-escritura atómica con `tomlkit` y bajo un lock.
- La UI es un solo documento con dos vistas, `list` y `form`, controladas por `showView()` en `app.js`. Recibe datos por `mcw.render(payload)` y llama a Python por `window.pywebview.api`.
- Con mcstatus 14.2:
  - `JavaStatusResponse` trae `motd: Motd` (con `.parsed`, una lista de `str`, colores, `WebColor` y formatos), `version.name`, `version.protocol`, `icon` (data URI) y `players.sample` (`list[JavaStatusPlayer(name, id)] | None`).
  - `JavaServer.async_query(tries=)` consulta Query en `query_port`, que por defecto es el puerto de juego.
  - `Motd.to_html()` existe, pero **no escapa el texto**: `_handle_str` solo reemplaza `\n` por `<br>`.

Captura de `mecotronicos.aternos.me` apagado:

```
version:  {"protocol": -1, "name": "§c● Offline"}
players:  {"online": 0, "max": 20, "sample": []}
motd:     "This server is offline.\nGet this server more RAM for free! > craft.link/ram"
favicon:  presente
query:    timeout
```

Hoy la app lo muestra como online 0/20.

## Goals / Non-Goals

**Goals:**

- Que `probe` siga siendo el único punto que conoce mcstatus. El resto de la app ve solo tipos propios.
- Lógica de participantes (filtro, modo) y de Query (cuándo reintentar) en funciones puras, testeables sin red.
- Renombrar y eliminar en caliente sin reiniciar el poller y sin que un ciclo en curso deshaga el cambio.
- Ninguna ruta por la que texto del servidor (MOTD, versión, nombres) llegue al DOM como HTML.

**Non-Goals:**

- Query en un puerto distinto del de juego.
- Persistir `query_capable` en `config.toml`.
- Distinguir en la lista un servidor dormido de uno caído: ambos muestran Offline. Solo el detalle explica la diferencia.

## Decisions

### D1 - `ProbeOk` lleva la información completa; el dormido es su propio resultado

`models.py` gana:

```python
@dataclass(frozen=True)
class MotdSegment:
    text: str
    color: str | None = None  # "#rrggbb"
    bold: bool = False
    italic: bool = False
    underlined: bool = False
    strikethrough: bool = False


@dataclass(frozen=True)
class SamplePlayer:
    name: str
    id: str


@dataclass(frozen=True)
class ServerInfo:
    motd: tuple[MotdSegment, ...] = ()
    version: str = ""
    icon: str | None = None  # solo "data:image/png;base64,..."


class QueryOutcome(Enum):
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"
```

`ProbeOk` suma `info: ServerInfo`, `sample: tuple[SamplePlayer, ...] = ()`, `query: QueryOutcome = SKIPPED` y `query_players: tuple[str, ...] = ()`. Todo tiene default, así que los `ProbeOk(...)` de los tests actuales siguen siendo válidos.

Nuevo resultado: `ProbeAsleep(edition=JAVA)`, que se suma al union `ProbeResult`. Es un resultado separado y no un flag dentro de `ProbeOk`. Así `next_status` lo trata con su propio `isinstance`, y ningún consumidor de `ProbeOk` (alta, autodetección, notificaciones futuras) lo confunde con un online.

- *Alternativa descartada*: `ProbeOk(asleep=True)`. Obliga a revisar el flag en cada sitio que hoy asume "ProbeOk = online", como `ServerManager._add` y `_detect`.

### D2 - Detección de dormidos en `probe`

```python
ASLEEP_KEYWORDS = ("offline", "sleeping")


def _is_asleep(protocol: int, version_name: str) -> bool:
    plain = _strip_codes(version_name).casefold()
    return protocol == -1 and any(word in plain for word in ASLEEP_KEYWORDS)
```

`_strip_codes` quita `§x`. Solo se aplica a Java; Bedrock no tiene ese mecanismo. En `_detect`, un `ProbeAsleep` de Java gana igual que un `ProbeOk`: Java respondió, así que la edición es Java.

- El `protocol == -1` es la señal fuerte: un servidor real anuncia su versión de protocolo. La palabra clave evita marcar como dormido a un proxy que usa `-1` para mostrar otros textos, como "Mantenimiento" (ver el escenario del spec).
- Las palabras clave viven en una constante. Si otro proveedor (exaroton, Minehut) usa otro texto, se agrega ahí.

### D3 - El MOTD viaja como segmentos, no como HTML

`probe._motd_segments(motd: Motd) -> tuple[MotdSegment, ...]` recorre `motd.parsed`, una secuencia de componentes de `mcstatus.motd.components`. Mantiene un estado actual (color y los cuatro estilos) y emite un segmento por cada `str`:

- `JavaMinecraftColor` y `BedrockMinecraftColor`: se mapean a hex con una tabla propia de los 16 colores estándar, más los `MATERIAL_*` de Bedrock (con `None` si no están en la tabla). Un color NO reinicia los estilos, igual que en mcstatus: solo `RESET` lo hace. Con un MOTD en JSON, la negrita heredada de un componente padre debe sobrevivir al color de sus hijos.
- `WebColor`: `"#%02x%02x%02x" % rgb`.
- `BOLD`, `ITALIC`, `UNDERLINED` y `STRIKETHROUGH` activan su flag. `RESET` vuelve al estado inicial. `OBFUSCATED`, `InvalidFormatting` y `TranslationTag` se ignoran.
- Los segmentos de texto vacío se descartan.

En la UI, cada segmento se convierte en un `<span>` con `textContent = text` y `style.color` / clases para los estilos. Los `\n` se respetan con `white-space: pre-line`.

- *Alternativa descartada*: `Motd.to_html()`. No escapa el texto del servidor, y el webview tiene `window.pywebview.api` (agregar, renombrar, eliminar). Un MOTD con `<img onerror>` podría llamar a la API. Además, sus colores van en atributos `style` con `text-shadow` pensados para fondo claro.
- *Alternativa descartada*: escapar antes de `to_html()`. El escape tendría que ir dentro del transformer (texto y colores ya mezclados). Usar un transformer privado de mcstatus ata la app a sus internos.

El nombre de versión se expone con `_strip_codes` aplicado. El icono se acepta solo si empieza con `data:image/png;base64,`. Si no, `None`.

### D4 - Query en paralelo con el ping, decidido por el poller

Firma nueva: `probe(server, *, query: bool = False)`. Con `query=True` y edición Java, `_java` hace:

```
java = await JavaServer.async_lookup(address)         # SRV, una sola vez
status_task = java.async_status(tries=1)
query_task  = java.async_query(tries=1)               # query_port = puerto de juego
status = await status_task   (timeout 3 s)            # sus excepciones = las de hoy
query  = await query_task    (timeout 3 s, ambos corren a la vez)
         excepción o timeout -> QueryOutcome.FAILED, se loguea a DEBUG
```

- Las dos consultas arrancan juntas, así que el ciclo no se alarga más allá del timeout que ya existe.
- Un fallo de Query nunca convierte el resultado en `Unreachable`.
- Si el status falla, se cancela la tarea de Query.
- `query=False`, Bedrock y la detección de edición desconocida devuelven `QueryOutcome.SKIPPED`.

Quién decide si consultar Query es `state.py`, con funciones puras sobre el `ServerStatus`:

```python
QUERY_RETRY_CYCLES = 10


def wants_query(status) -> bool:
    return status.server.edition is Edition.JAVA and status.query_wait == 0
```

`ServerStatus` gana `query_capable: bool | None = None` (sin saber) y `query_wait: int = 0` (ciclos online que faltan para reintentar). En `next_status` con un `ProbeOk`:

- `OK` → `query_capable=True`, `query_wait=0`.
- `FAILED` → `query_capable=False`, `query_wait=QUERY_RETRY_CYCLES - 1`. Con ese valor, el décimo ciclo online vuelve a intentarlo, como pide el escenario del spec.
- `SKIPPED` → `query_wait = max(query_wait - 1, 0)`, sin cambiar `query_capable`.

Solo los ciclos online descuentan `query_wait`, porque Query solo tiene sentido con el servidor arriba. El poller llama `self._probe_fn(status.server, query=wants_query(status))`.

- *Alternativa descartada*: que `probe` recuerde el estado de Query. `probe` es una función sin estado y el poller ya es dueño del estado por servidor.
- *Alternativa descartada*: persistir `query_capable` en la config. Cuesta una escritura por cada cambio, y reaprenderlo al arrancar cuesta un datagrama.

`ProbeFn` cambia de firma. Los tests del poller y de `servers.py` que usan probes falsos se ajustan para aceptar `query`.

### D5 - `players.py`: filtro y modo, puros

```python
NULL_UUID = "00000000-0000-0000-0000-000000000000"
NAME_RE = re.compile(r"[A-Za-z0-9_]{3,16}")

def clean_sample(sample: Iterable[SamplePlayer]) -> tuple[str, ...]:
    # descarta UUID nulo, '§' y nombres que no hacen fullmatch; quita repetidos
    # (casefold) conservando el orden

class PlayersMode(Enum): FULL, PARTIAL, HIDDEN

def players_view(result: ProbeOk) -> tuple[PlayersMode, tuple[str, ...]]:
    if result.edition is Edition.BEDROCK:   -> (FULL, ()) si online == 0, si no (HIDDEN, ())
    if result.query is QueryOutcome.OK:     -> (FULL, query_players)
    if result.online == 0:                  -> (FULL, ())
    names = clean_sample(result.sample)
    if not names:                           -> (HIDDEN, ())
    if len(names) >= result.online:         -> (FULL, names)
    else:                                   -> (PARTIAL, names)
```

- `len(names) >= online` y no `==`: algunos servidores reportan `online` desactualizado por un instante. Si conocemos todos los nombres, la lista es completa.
- Bedrock con 0 jugadores es `FULL` sin nombres ("Nadie está jugando"). Es cierto, y es más útil que "no comparte".
- Los nombres de Query también pasan por la regex (sin UUID, que Query no trae). Así se protege la UI de nombres basura, y los nombres reales siempre la cumplen.

`ServerStatus` gana `info: ServerInfo | None`, `latency_ms: float | None`, `players_mode: PlayersMode | None`, `players: tuple[str, ...]` y `asleep: bool`. `next_status` los llena con un `ProbeOk` y los limpia (`None`, `()`, `False`) en cualquier otro estado, con la misma regla que hoy aplica a `online` y `max`. Esto deja los datos que el change 4 necesita en cada snapshot.

### D6 - Dormido en `next_status`

```python
if isinstance(result, ProbeAsleep):
    server = fijar edición si era UNKNOWN (igual que ProbeOk)
    return replace(prev, server=server, state=OFFLINE, asleep=True,
                   online=None, max=None, info=None, ..., failures=0)
```

- `failures=0`: el servidor respondió, así que no es un fallo. Si después responde normal, pasa a online. Si después deja de responder, cuenta dos fallos desde cero, y mientras tanto sigue en offline (el estado previo), que es lo correcto.
- Un servidor online que se duerme pasa a offline en ese ciclo, sin esperar un segundo resultado. Es lo que dice el spec.

### D7 - El poller identifica servidores por dirección

`Poller` gana `rename(address, name)` y `remove(address)`. Igual que `add`, se ejecutan en el loop del poller con `call_soon_threadsafe` y publican un snapshot sin mover `updated_at`. La clave es `address.casefold()`.

`_cycle()` deja de unir por posición:

```python
by_key = {key(s): s for s in updated}
self._statuses = [
    _merge(by_key.get(key(s)), s)  # resultado del ciclo, si lo hay
    for s in self._statuses  # el orden y la membresía actuales mandan
]
```

`_merge(new, current)` toma el estado del ciclo, pero con `server=current.server`, para conservar un renombrado hecho durante el ciclo. Mientras tanto, el ciclo pudo fijar la edición. Si `new.server.edition` difiere de la de `current`, gana la de `new`, porque la edición solo la cambia el ciclo.

- Un servidor quitado durante el ciclo no está en `self._statuses`, así que su resultado se descarta.
- Uno agregado durante el ciclo no está en `by_key` y queda tal cual.
- Todo corre en el hilo del loop, así que `rename` y `remove` nunca se intercalan con la unión.

`ServerManager` gana `rename_server(address, name) -> Reply` y `remove_server(address) -> Reply`, con el mismo patrón que `add_server`:

1. lock;
2. bloqueo si `not config.writable`;
3. validación del nombre (se reutiliza la regla de `validate_new_server`, extraída a `normalize_name(name, address)`);
4. escritura con `config.set_name` o `config.remove_server` (`ConfigWriteError` → reply de error);
5. `poller.rename` o `poller.remove`.

Así el archivo se escribe antes de tocar la lista, igual que al agregar. Al eliminar, también se quita la dirección de `self._editions`.

`config.py` gana `set_name(directory, address, name) -> bool` y `remove_server(directory, address) -> bool`. Ambos usan `_update` y buscan la primera entrada cuya `address` coincide sin distinguir mayúsculas, el mismo bucle que ya usa `set_edition`, extraído a `_find_entry`. Para borrar se usa `del servers[index]` sobre el `AoT` de tomlkit. Un test verifica que los comentarios entre entradas no se corrompen; si tomlkit deja un comentario huérfano, se acepta, porque el spec solo exige que la entrada desaparezca y que el resto quede.

Si la entrada no existe en el archivo (alguien la borró a mano), `remove_server` devuelve `False` y el servidor igual se quita del poller: el resultado que el usuario pidió ya se cumple. En cambio, `set_name` sin entrada devuelve un error: "El servidor ya no está en la configuración".

### D8 - La UI suma la vista `detail`

`state.view` pasa a ser `'list' | 'form' | 'detail'`, y `state.detail = address` indica qué servidor muestra. `showView()` generaliza la lógica de cabecera:

| vista  | título           | volver | actualizar / agregar | eliminar |
|--------|------------------|--------|----------------------|----------|
| list   | MC Watch         | no     | sí                   | no       |
| form   | Agregar servidor | sí     | no                   | no       |
| detail | nombre (botón)   | sí     | no                   | sí       |

- **Filas**: cada `li.server` lleva `tabindex="0"`, `role="button"`, un `aria-label` con nombre y estado, y `data-address`. Un único listener delegado en `#servers` maneja click, Enter y Espacio.
- **Detalle**: `<section id="detail">` con:
  - `.info`: `<img>` del icono, o un glifo genérico de Segoe Fluent cuando no hay icono; `.motd`; una línea `versión · 45 ms · Bedrock`; y la dirección.
  - `.state-msg`: para offline, error, consultando y dormido.
  - La sección "Participantes": `<ul class="players">` o un mensaje según el modo.

  `renderDetail(server)` se llama desde `render()` cuando `state.view === 'detail'`. Si la dirección ya no está en el payload, vuelve a la lista.
- **Renombrar**: el `h1#title` se reemplaza por un `<input>` mientras se edita (`state.renaming`). `render()` no toca el input ni el título mientras `renaming` sea verdadero, así un ciclo de sondeo no pisa lo que el usuario escribe. Enter o blur llaman a `api.rename_server`. Si falla, se muestra un `.err` bajo la cabecera y se restaura el nombre anterior.

  El blur del input ocurre también cuando el panel pierde el foco y se oculta. En ese caso el renombrado se guarda, que es lo esperable de un blur.
- **Eliminar**: `#confirm` es un bloque dentro del detalle (no un `confirm()` del navegador, que bloquearía el webview) con "¿Eliminar *nombre*?", el aviso de que se quita de la configuración, "Cancelar" y "Eliminar" (botón de peligro). Mientras la llamada está en curso, los botones se deshabilitan.
- **Escape**, en orden de prioridad: renombrado → cancela; confirmación → la cierra; form o detail → vuelve a la lista; list → oculta el panel.
- **Alto**: `naturalHeight()` ya suma los hijos visibles de `#app`. La lista de participantes cuenta con su `scrollHeight`, igual que `#list`, para que crezca hasta el máximo y luego haga scroll.

Payload por servidor, en `view.py`:

```
latency_ms, version, motd: [{text, color, bold, italic, underlined, strikethrough}],
icon, players_mode: "full"|"partial"|"hidden"|null, players: [..], asleep: bool
```

`_Api` gana `rename_server(address, name)` y `remove_server(address)`. `Panel` las recibe como callables opcionales, igual que `add_server`.

### D9 - Preview

`preview.py` suma servidores al escenario mixto:

- uno con lista full (3 nombres);
- uno con 0 jugadores;
- uno partial (5 de 23);
- uno con muestra decorativa (hidden);
- uno Bedrock (hidden);
- uno dormido;
- un MOTD multicolor con estilos y un segmento con `<b>` literal, para comprobar a ojo que no se interpreta.

Para el icono se usa un PNG pequeño en base64, generado una vez y guardado como constante.

`app.js` simula `rename_server` y `remove_server` en preview: modifican `state.payload` y vuelven a renderizar. Un nombre que contiene "fail" simula el error de escritura.

## Risks / Trade-offs

- **[Heurística de dormidos incompleta]**: solo está verificada con Aternos apagado. Mitigación: tarea para capturar Aternos encendido y confirmar que su `protocol` es real y no `-1`; las palabras clave están en una constante.
- **[Query con falsos positivos de timeout]**: UDP puede perderse y marcar `query_capable=False` durante 10 ciclos, en los que se usa la muestra. Es una degradación visible (partial en lugar de full), no un error, y el reintento la corrige.
- **[`ConnectionResetError` al cerrar]**: en la captura de Aternos, una de las conexiones falló al cerrarse (`WinError 64` en `__aexit__`) aunque la siguiente respondió. Ya cae en `OSError` → `Unreachable` y la regla de dos fallos lo absorbe. No requiere cambios, pero se vigila en la verificación manual.
- **[Payload más pesado]**: el icono se manda en cada snapshot (unos pocos KB por servidor). Con decenas de servidores son cientos de KB cada 30 s por `evaluate_js`. Es aceptable para el MVP; si molesta, se manda el icono solo al abrir el detalle.
- **[Direcciones duplicadas escritas a mano]**: renombrar o eliminar afecta a la primera entrada y a la primera fila con esa dirección. El alta ya impide duplicados desde la UI.
- **[Blur guarda el renombrado]**: si el panel se oculta a mitad de un renombrado, se guarda lo escrito. Es coherente con "blur = guardar", y Escape sigue disponible para cancelar.

## Migration Plan

No hay migración de datos: `config.toml` no gana campos. `query_capable` vive en memoria.

## Open Questions

- ¿El Aternos encendido trae una muestra o Query utilizables? Se responde en la verificación manual. No cambia el diseño, solo el modo que se verá.
