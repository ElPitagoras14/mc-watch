## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Escritura de la configuración
Al escribir `config.toml`, el sistema SHALL conservar los comentarios, el orden y el formato de lo que ya había en el archivo, y SHALL cambiar solo lo necesario: agregar la entrada nueva al final o actualizar el `edition` de una entrada existente. El sistema SHALL partir del contenido actual del archivo en disco, de modo que no se pierdan cambios hechos a mano desde que la app inició. Si en ese momento el archivo tiene un error de sintaxis, el sistema SHALL abortar la escritura sin tocarlo. La escritura SHALL ser atómica: ante un fallo, el archivo SHALL quedar como estaba.

#### Scenario: Comentarios conservados
- **WHEN** el archivo tiene comentarios escritos a mano y el usuario agrega un servidor
- **THEN** el archivo resultante conserva esos comentarios y tiene la entrada nueva al final

#### Scenario: Archivo roto después de iniciar
- **WHEN** la app inició con un archivo válido, el usuario lo rompe a mano y luego agrega un servidor desde el panel
- **THEN** la app no escribe el archivo y el formulario informa el error

### Requirement: Edición detectada persistida
Cuando un servidor de edición desconocida responde en un ciclo de sondeo, el sistema SHALL guardar la edición detectada en su entrada de `config.toml`, identificándola por su dirección. Un fallo al guardar SHALL registrarse en el log y SHALL NOT interrumpir el sondeo.

#### Scenario: Detección tardía
- **WHEN** un servidor guardado como `unknown` empieza a responder como Java
- **THEN** su entrada en `config.toml` pasa a tener `edition = "java"`

#### Scenario: Config escrita a mano
- **WHEN** la app inicia con `mc.hypixel.net` sin `edition` y el servidor responde
- **THEN** la entrada queda con `edition = "java"` y el resto del archivo no cambia
