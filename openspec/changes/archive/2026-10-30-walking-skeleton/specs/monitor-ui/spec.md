## Purpose

Definir el panel principal de `mc-watch`: la lista de servidores con su estado y jugadores, la cabecera con sus acciones y el pie con la antigüedad de los datos y la versión.

## ADDED Requirements

### Requirement: Lista de servidores
El panel SHALL mostrar una fila por servidor configurado con su nombre, su dirección tal como está en la configuración, su estado (Consultando, Online, Offline o Error) con un indicador de color, y sus jugadores en formato `X/Y`. Cuando el servidor no está online, la columna de jugadores SHALL mostrar `—`.

#### Scenario: Servidor online
- **WHEN** el servidor "Survival" en `play.example.com` está online con 3 de 20 jugadores
- **THEN** su fila muestra "Survival", "play.example.com", estado Online y "3/20"

#### Scenario: Servidor offline
- **WHEN** un servidor está offline
- **THEN** su fila muestra estado Offline y "—" en jugadores

#### Scenario: Estado distinguible
- **WHEN** hay servidores en los cuatro estados
- **THEN** cada estado se muestra con su propio texto y color de indicador

### Requirement: Tamaño del panel
El panel SHALL tener un ancho fijo y un alto que se adapta a su contenido entre un mínimo y un máximo. Cuando el contenido supera el alto máximo, la lista de servidores SHALL hacer scroll interno mientras la cabecera y el pie permanecen visibles. Al cambiar de alto, el panel SHALL mantener su borde inferior junto a la bandeja.

#### Scenario: Pocos servidores
- **WHEN** hay dos servidores configurados
- **THEN** el panel es más bajo que el máximo y no muestra espacio vacío bajo la lista

#### Scenario: Muchos servidores
- **WHEN** la lista no cabe en el alto máximo
- **THEN** la lista hace scroll y la cabecera y el pie siguen visibles

### Requirement: Estado vacío
Cuando no hay servidores configurados, el panel SHALL mostrar un mensaje que indique que no hay servidores y la ruta del archivo de configuración que se debe editar.

#### Scenario: Sin servidores
- **WHEN** la configuración no tiene servidores válidos
- **THEN** el panel muestra el mensaje de estado vacío con la ruta de `config.toml`

### Requirement: Cabecera del panel
La cabecera SHALL mostrar el nombre `mc-watch` y tres botones: agregar, fijar y cerrar. En este change el botón agregar SHALL mostrarse deshabilitado. El botón fijar SHALL indicar visualmente si el panel está fijado.

#### Scenario: Botón agregar
- **WHEN** el usuario hace click en agregar
- **THEN** no ocurre nada y el botón se ve deshabilitado

#### Scenario: Indicador de fijado
- **WHEN** el usuario activa fijar
- **THEN** el botón fijar se muestra activo

### Requirement: Pie del panel
El pie SHALL mostrar cuánto tiempo pasó desde que terminó el último ciclo de sondeo, en formato relativo ("Actualizado hace 12 s", "hace 2 min"), actualizándose al menos cada segundo mientras el panel está visible. El pie SHALL mostrar también la versión de la app. Antes de que termine el primer ciclo, SHALL mostrar "Actualizando…".

#### Scenario: Tras un ciclo
- **WHEN** el último ciclo terminó hace 40 segundos
- **THEN** el pie muestra "Actualizado hace 40 s" y la versión, por ejemplo "0.1.0"

#### Scenario: Antes del primer ciclo
- **WHEN** la app acaba de iniciar
- **THEN** el pie muestra "Actualizando…"

### Requirement: Actualización en vivo
Cuando termina un ciclo de sondeo, el panel SHALL reflejar los nuevos estados y conteos sin que el usuario tenga que cerrarlo y volver a abrirlo.

#### Scenario: Panel abierto durante un ciclo
- **WHEN** el panel está visible y un servidor pasa de offline a online
- **THEN** la fila se actualiza sola al terminar el ciclo

### Requirement: Preview en navegador
El proyecto SHALL ofrecer un modo preview que abre el panel en un navegador con datos de ejemplo que cubren los cuatro estados y el estado vacío, sin iniciar la bandeja ni hacer consultas de red.

#### Scenario: Abrir el preview
- **WHEN** el desarrollador ejecuta el comando de preview
- **THEN** el navegador muestra el panel con servidores de ejemplo en los cuatro estados
