# server-config Specification

## Purpose

Definir dónde vive y qué formato tiene la configuración de `mc-watch` (lista de servidores e intervalo de sondeo), y cómo se comporta la app cuando el archivo falta o es inválido.

## Requirements

### Requirement: Ubicación del archivo de configuración
El sistema SHALL leer y escribir la configuración en `config.toml` dentro de `%APPDATA%\mc-watch`. Cuando la variable de entorno `MC_WATCH_CONFIG_DIR` esté definida, el sistema SHALL usar `config.toml` en ese directorio en su lugar. Si el archivo o el directorio no existen cuando hay que escribir, el sistema SHALL crearlos.

#### Scenario: Ubicación por defecto
- **WHEN** `MC_WATCH_CONFIG_DIR` no está definida
- **THEN** el sistema lee `%APPDATA%\mc-watch\config.toml`

#### Scenario: Directorio sobrescrito
- **WHEN** `MC_WATCH_CONFIG_DIR` vale `D:\tmp\mcw`
- **THEN** el sistema lee `D:\tmp\mcw\config.toml`

#### Scenario: Primer servidor sin archivo
- **WHEN** no existe `config.toml` y el usuario agrega un servidor desde el panel
- **THEN** el sistema crea el directorio y el archivo con ese servidor

### Requirement: Formato de la configuración
La configuración SHALL admitir una clave opcional `poll_interval_secs` y una lista `[[servers]]`, donde cada servidor tiene `name` (texto visible), `address` (`host` o `host:puerto`) y un campo opcional `edition` con uno de los valores `java`, `bedrock` o `unknown`. Una entrada sin `edition`, o con un valor distinto de esos tres, SHALL tratarse como `unknown`. El sistema SHALL mostrar los servidores en el mismo orden en que aparecen en el archivo.

#### Scenario: Archivo válido
- **WHEN** el archivo contiene dos entradas `[[servers]]` con `name` y `address`
- **THEN** el panel muestra ambos servidores en ese orden

#### Scenario: Edición explícita
- **WHEN** una entrada tiene `edition = "bedrock"`
- **THEN** el servidor se consulta como Bedrock

#### Scenario: Sin edición
- **WHEN** una entrada escrita a mano no tiene `edition`
- **THEN** el servidor se trata como de edición desconocida y se autodetecta

### Requirement: Intervalo de sondeo
`poll_interval_secs` SHALL valer 60 por defecto. Un valor menor a 30 SHALL tratarse como 30 y uno mayor a 3600 SHALL tratarse como 3600.

#### Scenario: Sin intervalo configurado
- **WHEN** el archivo no define `poll_interval_secs`
- **THEN** el intervalo efectivo es 60 segundos

#### Scenario: Intervalo demasiado bajo
- **WHEN** `poll_interval_secs` vale 5
- **THEN** el intervalo efectivo es 30 segundos

#### Scenario: Intervalo demasiado alto
- **WHEN** `poll_interval_secs` vale 86400
- **THEN** el intervalo efectivo es 3600 segundos

### Requirement: Configuración ausente o inválida
Si el archivo no existe, el sistema SHALL iniciar sin servidores. Si el archivo tiene un error de sintaxis TOML o no se puede leer, el sistema SHALL iniciar sin servidores y con valores por defecto, y SHALL NOT modificar el archivo mientras la app esté en ejecución, ni al agregar servidores ni al guardar ediciones detectadas. Una entrada de servidor sin `name` o sin `address`, o con un puerto fuera de 1–65535, SHALL ignorarse sin afectar a las demás entradas.

#### Scenario: Archivo inexistente
- **WHEN** no existe `config.toml`
- **THEN** la app inicia y el panel muestra el estado vacío

#### Scenario: Error de sintaxis
- **WHEN** `config.toml` contiene TOML inválido
- **THEN** la app inicia sin servidores y el archivo queda intacto aunque el usuario intente agregar un servidor

#### Scenario: Entrada incompleta
- **WHEN** una de tres entradas `[[servers]]` no tiene `address`
- **THEN** el panel muestra solo las otras dos

### Requirement: Escritura de la configuración
Al escribir `config.toml`, el sistema SHALL conservar los comentarios, el orden y el formato de lo que ya había en el archivo, y SHALL cambiar solo lo necesario:
- agregar la entrada nueva al final;
- actualizar el `edition` o el `name` de una entrada existente;
- quitar una entrada completa;
- actualizar o agregar las claves `notifications`, `poll_interval_secs` y `max_visible_servers`, en la parte superior del archivo, antes de las entradas `[[servers]]`.

Las entradas existentes SHALL identificarse por su `address`, sin distinguir mayúsculas de minúsculas. Si hay más de una con la misma dirección, SHALL modificarse la primera. El sistema SHALL partir del contenido actual del archivo en disco, de modo que no se pierdan cambios hechos a mano desde que la app inició. Si en ese momento el archivo tiene un error de sintaxis, el sistema SHALL abortar la escritura sin tocarlo. La escritura SHALL ser atómica: ante un fallo, el archivo SHALL quedar como estaba.

#### Scenario: Comentarios conservados
- **WHEN** el archivo tiene comentarios escritos a mano y el usuario agrega un servidor
- **THEN** el archivo resultante conserva esos comentarios y tiene la entrada nueva al final

#### Scenario: Archivo roto después de iniciar
- **WHEN** la app inició con un archivo válido, el usuario lo rompe a mano y luego agrega un servidor desde el panel
- **THEN** la app no escribe el archivo y el formulario informa el error

#### Scenario: Renombrar conserva el resto
- **WHEN** el usuario renombra el segundo de tres servidores
- **THEN** solo cambia el `name` de esa entrada y el resto del archivo, incluidos los comentarios, queda igual

#### Scenario: Quitar una entrada
- **WHEN** el usuario elimina el segundo de tres servidores
- **THEN** el archivo conserva la primera y la tercera entrada con sus comentarios, y la segunda desaparece por completo

#### Scenario: Guardar ajustes en un archivo con servidores
- **WHEN** el archivo solo tiene entradas `[[servers]]` y el usuario guarda los ajustes
- **THEN** las tres claves quedan antes de la primera entrada `[[servers]]` y las entradas no cambian

### Requirement: Edición detectada persistida
Cuando un servidor de edición desconocida responde en un ciclo de sondeo, el sistema SHALL guardar la edición detectada en su entrada de `config.toml`, identificándola por su dirección. Un fallo al guardar SHALL registrarse en el log y SHALL NOT interrumpir el sondeo.

#### Scenario: Detección tardía
- **WHEN** un servidor guardado como `unknown` empieza a responder como Java
- **THEN** su entrada en `config.toml` pasa a tener `edition = "java"`

#### Scenario: Config escrita a mano
- **WHEN** la app inicia con `mc.hypixel.net` sin `edition` y el servidor responde
- **THEN** la entrada queda con `edition = "java"` y el resto del archivo no cambia

### Requirement: Ajustes de notificaciones y lista
La configuración SHALL admitir una clave opcional `notifications` (booleano, `false` por defecto) y una clave opcional `max_visible_servers` (entero, 8 por defecto). Un `notifications` que no es booleano SHALL tratarse como `false`. Un `max_visible_servers` que no es entero SHALL tratarse como 8, y uno fuera de 3–20 SHALL llevarse al límite más cercano. Cada valor corregido SHALL registrarse como advertencia en el log.

#### Scenario: Sin ajustes
- **WHEN** el archivo no define `notifications` ni `max_visible_servers`
- **THEN** las notificaciones están desactivadas y la lista muestra hasta 8 servidores antes de hacer scroll

#### Scenario: Valor fuera de rango
- **WHEN** `max_visible_servers` vale 50
- **THEN** el valor efectivo es 20
