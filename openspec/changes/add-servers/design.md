## Context

El walking skeleton dejó estas costuras, que este change aprovecha:

- `probe.py` es el único módulo que importa `mcstatus` y devuelve `ProbeOk | ProbeUnreachable | ProbeUnresolvable`.
- `state.next_status()` es puro y aplica la regla de dos fallos.
- `Poller` corre un loop asyncio en su propio hilo, pero su lista de servidores es fija desde el constructor: `_cycle()` hace `gather` sobre `self._statuses` y luego un `zip(strict=True)` con los resultados.
- `config.py` solo lee, con `tomllib`, y descarta en silencio lo que no entiende. `load_config()` devuelve `Config(poll_interval_secs, servers, warnings)`.
- La UI es un solo documento (`ui/index.html` + `app.js`) que recibe datos por `mcw.render(payload)` y llama a Python por `window.pywebview.api` (`_Api` en `window.py`). pywebview ejecuta cada llamada del `js_api` en un hilo propio y la entrega al JS como una promesa.
- `mcstatus` 14.2 ofrece `BedrockServer.lookup(address, timeout)` y `async_status(tries=...)`, cuya respuesta trae `players.online`, `players.max` y `latency`, igual que la de Java.

## Goals / Non-Goals

**Goals:**

- Agregar servidores en caliente, sin reiniciar el poller ni la app.
- Que la detección de la edición viva en `probe`, para que el alta y el sondeo periódico compartan el mismo código.
- Escribir el toml sin destruir lo que el usuario escribió a mano.
- Mantener testeables sin red la lógica de detección, la escritura de la config y el alta en el poller.

**Non-Goals:**

- Recargar la config ante cambios externos, o instancia única. Si se abren dos instancias de la app, la última escritura gana.
- Renombrar y eliminar, que llegan en el change 3.

## Decisions

### D1 - La edición es parte de `ServerConfig`

`models.py` gana `class Edition(Enum): JAVA = "java"; BEDROCK = "bedrock"; UNKNOWN = "unknown"`, y `ServerConfig` gana `edition: Edition = Edition.UNKNOWN`. Con el default, las construcciones existentes, como `ServerConfig("A", "a.example.com")` en los tests, siguen funcionando.

`ProbeOk` gana `edition: Edition`, que indica qué protocolo respondió. `state.next_status()`, ante un `ProbeOk` sobre un servidor `UNKNOWN`, reemplaza `status.server` por `replace(server, edition=result.edition)`. A partir de ese ciclo el servidor ya no es desconocido. Los resultados de fallo no tocan la edición.

- *Alternativa descartada*: guardar la edición en `ServerStatus` y no en `ServerConfig`. La edición es un dato de configuración que se persiste. Si viviera en el estado, habría dos fuentes de verdad.

### D2 - `probe()` despacha por edición y detecta en paralelo

```
probe(server)
  JAVA     -> _java(address)                      (igual que hoy)
  BEDROCK  -> _bedrock(address)                   BedrockServer.lookup + async_status(tries=1)
  UNKNOWN  -> _detect(address):
                java    = task(_java)             ambas arrancan a la vez,
                bedrock = task(_bedrock)          cada una con su timeout de 3 s
                r = await java
                  Ok           -> cancelar bedrock, devolver Ok(JAVA)
                  Unresolvable -> cancelar bedrock, devolver Unresolvable
                r = await bedrock
                  Ok           -> devolver Ok(BEDROCK)
                  otro         -> devolver Unreachable
```

- Correr los dos intentos en paralelo pero decidir con prioridad Java cumple "primero Java, luego Bedrock" y deja la detección en ~3 s en lugar de ~6 s. El formulario se siente más rápido y un ciclo con servidores desconocidos no se alarga.
- La clasificación de excepciones actual (`gaierror` → `Unresolvable`, timeout, `OSError`, `ValueError` o `DNSException` → `Unreachable`, cualquier otra → `Unreachable` con log) se extrae a un helper que envuelve cada intento, para que Java, Bedrock y la detección la compartan.
- Si Java da `Unresolvable`, no se espera a Bedrock: ambos usan el mismo host, así que tampoco resolvería.
- Bedrock usa la dirección tal cual, sin SRV, como el cliente Bedrock.

- *Alternativa descartada*: un `detect()` aparte, que solo usa el alta. Duplicaría la lógica, y el sondeo periódico de los servidores desconocidos también necesita detectar.

### D3 - El poller acepta altas y trabajos externos

`Poller` gana dos métodos, seguros para llamar desde cualquier hilo:

- `submit(coro) -> concurrent.futures.Future`: corre una corrutina en el loop del poller con `asyncio.run_coroutine_threadsafe`. El alta lo usa para ejecutar `probe()` sin crear otro loop. Si el poller no está corriendo, lanza `RuntimeError`.
- `add(server, result)`: agenda en el loop, con `call_soon_threadsafe`, un callback que hace `status = next_status(initial_status(server), result)`, lo agrega al final de `self._statuses` y publica un snapshot a los suscriptores. El `updated_at` se conserva, porque no terminó un ciclo. Devuelve cuando el callback corrió, usando un `Future` del módulo `concurrent`, para que el alta pueda responder al JS con la fila ya publicada.

Como todas las mutaciones de `_statuses` ocurren en el hilo del loop, no hace falta lock para la lista. Lo que sí puede pasar es que un alta llegue durante el `await gather(...)` de un ciclo. Para cubrirlo, `_cycle()` trabaja sobre una copia local: `current = list(self._statuses)`, `gather` sobre `current` y, al terminar, `self._statuses = updated + self._statuses[len(current):]`. Las altas solo agregan al final, así que lo agregado durante el ciclo se conserva y se consulta en el ciclo siguiente.

Un alta con resultado `ProbeUnreachable` (edición desconocida) arranca en `QUERYING` con un fallo. Si el ciclo siguiente también falla, pasa a `OFFLINE`, igual que un servidor configurado que falla el primer ciclo.

- *Alternativa descartada*: reiniciar el poller con la lista nueva. Perdería los contadores de fallos de todos los servidores y dejaría el panel en "Consultando".

### D4 - El alta la orquesta `ServerManager`, con validación en Python

`_Api.add_server(name, address)` delega en `Panel.add_server`, que llama a `ServerManager.add_server(name, address) -> dict` (`servers.py`; `App` solo lo conecta, para poder probarlo sin bandeja ni ventana). pywebview lo corre en un hilo propio. Bajo un `threading.Lock`, para que un doble envío no cree duplicados, `App.add_server`:

1. Valida con `config.validate_new_server(name, address, existing)`, una función pura: recorta espacios, exige la dirección, valida el formato con `is_valid_address`, limita el nombre a 40 caracteres, usa la dirección si el nombre queda vacío y rechaza duplicados sin distinguir mayúsculas. `existing` son las direcciones del último snapshot del poller.
2. Si la config no es escribible (D5), responde el error sin consultar la red.
3. Ejecuta `poller.submit(probe(ServerConfig(name, address, UNKNOWN))).result(timeout=10)`.
4. Ante `ProbeUnresolvable`, responde el error de host. Ante `ProbeOk`, usa `result.edition`; ante `ProbeUnreachable`, `UNKNOWN`.
5. Persiste con `config.append_server(...)` (D5). Si falla, responde el error y no toca el poller.
6. Ejecuta `poller.add(server, result)` y responde `{"ok": true}`.

La respuesta de error tiene la forma `{"ok": false, "field": "name" | "address" | null, "message": "..."}`. El JS solo la muestra: no duplica reglas de validación, salvo `maxlength="40"` en el input del nombre.

El orden "guardar y después mostrar" garantiza que nada que aparezca en la lista se pierda al reiniciar.

- *Alternativa descartada*: validar en JS. Habría que mantener dos copias de `is_valid_address`, y la de duplicados igual necesita el estado de Python. La llamada al `js_api` es local y tarda milisegundos.

### D5 - Escritura con `tomlkit`, atómica y desde el disco

Se agrega la dependencia `tomlkit`, que hace round-trip del TOML conservando comentarios, orden y espacios. La lectura sigue con `tomllib`, tal como está validada en el skeleton; `tomlkit` solo se usa para escribir.

- `Config` gana `writable: bool`. Vale `False` si el archivo existía y no se pudo leer o no es TOML válido; vale `True` si no existe o si es válido. Con `writable=False`, la app no escribe durante toda la sesión, como pide la spec, aunque el usuario corrija el archivo: lo toma al reiniciar. `Config` también gana `error: str | None`, el mensaje que se muestra en la UI.
- `config.append_server(directory, server)` y `config.set_edition(directory, address, edition)` siguen el mismo esquema:
  1. Leer el archivo actual. Si no existe, partir de un documento vacío.
  2. Parsearlo con `tomlkit`. Si falla, lanzar `ConfigWriteError("config.toml tiene un error de sintaxis")`.
  3. Modificar el documento. `append_server` agrega una tabla a `servers`, creando el array si no existe. `set_edition` busca la entrada por `address` sin distinguir mayúsculas; si no la encuentra, porque el usuario la borró a mano, no escribe.
  4. Escribir en `config.toml.tmp` dentro del mismo directorio y hacer `os.replace` sobre `config.toml`. Antes, `mkdir(parents=True, exist_ok=True)`.
  5. Cualquier `OSError` se convierte en `ConfigWriteError` con el motivo.
- La entrada nueva se escribe con los tres campos: `name`, `address` y `edition`, incluido `edition = "unknown"`. Así el archivo dice explícitamente qué detectó la app.

Ejemplo de la config después de agregar un servidor Bedrock:

```toml
poll_interval_secs = 30

[[servers]]
name = "Hypixel"
address = "mc.hypixel.net"
edition = "java"

[[servers]]
name = "Isla"
address = "isla.example.com"
edition = "bedrock"
```

- *Alternativa descartada*: serializar el TOML a mano con f-strings. Es simple para agregar al final, pero `set_edition` necesita editar una tabla existente, y un serializador casero rompería los comentarios o el escape de comillas.

### D6 - La edición detectada se persiste desde un suscriptor

`ServerManager.on_snapshot` se suscribe al poller, como ya hace para la bandeja y el panel. En cada snapshot compara la edición de cada servidor con la última que vio, guardada en un diccionario por dirección. Si un servidor pasó de `UNKNOWN` a otra edición y la config es escribible, llama a `config.set_edition`. Los errores van al log. El suscriptor corre en el hilo del poller; la escritura es de unos pocos KB y no afecta el ciclo.

### D7 - UI: una segunda vista en el mismo panel

- `index.html` gana un `<section id="form-view" hidden>` hermano de `#list`. `app.js` lleva `state.view = 'list' | 'form'`. Al cambiar de vista se alternan `hidden` en la lista, el formulario y la sección "Servidores", el título de la cabecera (`MC Watch` ↔ `Agregar servidor`), el botón agregar (oculto en el formulario) y un botón volver a la izquierda del título (glifo `&#xE72B;` de Segoe Fluent Icons, como los demás).
- El formulario tiene "Nombre" (placeholder "Opcional", `maxlength="40"`), "Dirección" (placeholder `play.example.com`), una línea de error por campo, una línea de mensaje general y los botones "Cancelar" y "Agregar". Durante la detección, "Agregar" dice "Detectando…" y los inputs quedan `disabled`.
- `render(payload)` sigue funcionando con el formulario abierto: actualiza la lista oculta, así que al volver ya está al día. Con el panel oculto por blur no se reinicia nada: la ventana solo se esconde y el DOM conserva lo escrito.
- `naturalHeight()` ya recorre los hijos de `.panel`. Los hijos con `hidden` miden 0 con `offsetHeight`, así que basta con que el formulario sea un hijo más; tras cambiar de vista se llama a `reportHeight()`.
- El keydown de Escape pasa a: si `state.view === 'form'` y no hay detección en curso, volver a la lista; si no, `hide()`. Enter dentro del `<form>` lo envía de forma nativa, con `submit` y `preventDefault`.
- El payload gana `edition` por servidor y `config_error` (`str | null`) a nivel raíz. La fila agrega a la línea de la dirección ` · Bedrock` o ` · edición desconocida`, esta última en color ámbar. Con `config_error`, el estado vacío y el formulario muestran el aviso con la ruta y el botón "Agregar" se deshabilita.

### D8 - Preview con un `js_api` simulado

`app.js` ya distingue el preview con `window.__MCW_PREVIEW__`. En ese modo, `bridge()` devuelve un objeto falso con `add_server(name, address)`, que espera ~1 s y responde según la dirección:

- `*.invalid` → error de host.
- Una dirección que contiene `unknown` → la agrega con edición desconocida.
- Cualquier otra → la agrega online con `0/20`.

En los casos de éxito la agrega al payload del escenario actual y vuelve a renderizar, sin red ni escritura. `preview.py` suma ejemplos Bedrock y desconocida al escenario "Cuatro estados" y un escenario "Config con error" (`config_error` no nulo, sin servidores).

## Risks / Trade-offs

- [Un firewall bloquea UDP saliente y un servidor Bedrock queda como desconocido] → Se reintenta en cada ciclo y la fila muestra el aviso. Es el comportamiento que pide el roadmap.
- [Un servidor con Geyser responde a Java y a Bedrock] → Se toma como Java, que es el protocolo con más datos (y el que habilitará Query en el change 3).
- [Un host que hoy no responde pero en el futuro sí, con otra edición que la esperada] → Solo se detecta mientras está `UNKNOWN`. Una vez fijada, la edición no cambia; para corregirla, se edita el toml.
- [Los servidores desconocidos duplican las consultas por ciclo] → Son dos consultas en paralelo con el mismo timeout. El costo es mínimo y desaparece al detectar la edición.
- [`tomlkit` y `tomllib` podrían discrepar ante un TOML raro] → Si `tomllib` lo aceptó y `tomlkit` no, la escritura falla con `ConfigWriteError` y el archivo queda intacto. El error se ve en el formulario y en el log.
- [Escritura concurrente: alta y `set_edition` desde hilos distintos] → Ambas pasan por un `threading.Lock` de módulo en `config.py` que rodea todo el leer-modificar-escribir.
- [El usuario edita el toml mientras la app corre] → La escritura parte del disco, así que esos cambios no se pierden. Sí quedan fuera de la lista en memoria hasta reiniciar, lo cual está documentado como non-goal.
- [`App.add_server` bloquea un hilo de pywebview hasta ~3 s] → pywebview usa un hilo por llamada, así que no congela la UI. El `result(timeout=10)` acota el peor caso.
