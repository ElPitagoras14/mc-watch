# monitor-ui Specification

## Purpose

Definir el panel principal de `mc-watch`: la lista de servidores con su estado y jugadores, la cabecera con sus acciones y el pie con la antigüedad de los datos y la versión.

## Requirements

### Requirement: Lista de servidores
El panel SHALL mostrar una fila por servidor configurado con su nombre, su dirección tal como está en la configuración, su estado (Consultando, Online, Offline o Error) con un indicador de color, y sus jugadores en formato `X/Y`. Cuando el servidor no está online, la columna de jugadores SHALL mostrar `—`. Junto a la dirección, la fila de un servidor Bedrock SHALL indicar "Bedrock" y la de un servidor de edición desconocida SHALL mostrar el aviso "edición desconocida". La fila de un servidor Java SHALL NOT llevar indicación de edición.

#### Scenario: Servidor online
- **WHEN** el servidor "Survival" en `play.example.com` está online con 3 de 20 jugadores
- **THEN** su fila muestra "Survival", "play.example.com", estado Online y "3/20"

#### Scenario: Servidor offline
- **WHEN** un servidor está offline
- **THEN** su fila muestra estado Offline y "—" en jugadores

#### Scenario: Estado distinguible
- **WHEN** hay servidores en los cuatro estados
- **THEN** cada estado se muestra con su propio texto y color de indicador

#### Scenario: Servidor Bedrock
- **WHEN** un servidor es de edición Bedrock
- **THEN** su fila muestra "Bedrock" junto a la dirección

#### Scenario: Edición desconocida
- **WHEN** un servidor es de edición desconocida
- **THEN** su fila muestra el aviso "edición desconocida" junto a la dirección, y el aviso desaparece cuando la edición se detecta

### Requirement: Tamaño del panel
El panel SHALL tener un ancho fijo y un alto que se adapta a su contenido entre un mínimo y un máximo. Cuando el contenido supera el alto máximo, la lista de servidores SHALL hacer scroll interno mientras la cabecera y el pie permanecen visibles. Al cambiar de alto, el panel SHALL mantener su borde inferior junto a la bandeja.

#### Scenario: Pocos servidores
- **WHEN** hay dos servidores configurados
- **THEN** el panel es más bajo que el máximo y no muestra espacio vacío bajo la lista

#### Scenario: Muchos servidores
- **WHEN** la lista no cabe en el alto máximo
- **THEN** la lista hace scroll y la cabecera y el pie siguen visibles

### Requirement: Estado vacío
Cuando no hay servidores configurados, el panel SHALL mostrar un mensaje que indique que no hay servidores y que invite a agregar uno con el botón agregar. Si la configuración tiene un error de sintaxis, el mensaje SHALL indicar además la ruta de `config.toml` que hay que corregir.

#### Scenario: Sin servidores
- **WHEN** la configuración no tiene servidores
- **THEN** el panel muestra el mensaje de estado vacío con la invitación a agregar un servidor

#### Scenario: Config con error de sintaxis
- **WHEN** `config.toml` tiene TOML inválido
- **THEN** el estado vacío indica que el archivo tiene un error y muestra su ruta

### Requirement: Cabecera del panel
La cabecera SHALL mostrar el nombre `MC Watch` y cuatro botones, en este orden: actualizar, agregar, fijar y cerrar. El botón agregar SHALL abrir el formulario para agregar un servidor. El botón fijar SHALL indicar visualmente si el panel está fijado. Mientras el formulario está abierto, el título SHALL ser "Agregar servidor", los botones actualizar y agregar SHALL ocultarse y SHALL mostrarse un botón volver que regresa a la lista.

#### Scenario: Botón agregar
- **WHEN** el usuario hace click en agregar
- **THEN** el panel muestra el formulario para agregar un servidor

#### Scenario: Botón actualizar junto a agregar
- **WHEN** el panel muestra la lista
- **THEN** el botón actualizar aparece inmediatamente a la izquierda del botón agregar

#### Scenario: Indicador de fijado
- **WHEN** el usuario activa fijar
- **THEN** el botón fijar se muestra activo

#### Scenario: Volver
- **WHEN** el formulario está abierto y el usuario hace click en volver
- **THEN** el panel muestra la lista sin agregar nada

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
El proyecto SHALL ofrecer un modo preview que abre el panel en un navegador con datos de ejemplo que cubren los cuatro estados, las ediciones Bedrock y desconocida, y el estado vacío, sin iniciar la bandeja ni hacer consultas de red. En el preview, el formulario de agregar SHALL poder abrirse y SHALL simular la detección y sus resultados (éxito, host inexistente y edición desconocida) sin consultar la red ni escribir la configuración.

#### Scenario: Abrir el preview
- **WHEN** el desarrollador ejecuta el comando de preview
- **THEN** el navegador muestra el panel con servidores de ejemplo en los cuatro estados

#### Scenario: Formulario en el preview
- **WHEN** el desarrollador abre el formulario en el preview y agrega `no-existe.invalid`
- **THEN** el formulario muestra "Detectando…" y luego el error "No se encontró el host"

### Requirement: Actualizar ahora
El botón actualizar SHALL pedir un ciclo de sondeo inmediato de todos los servidores. Mientras el ciclo está en curso, el botón SHALL mostrarse ocupado y deshabilitado, y SHALL volver a su estado normal cuando la lista se actualiza con el resultado, o a los 15 segundos como máximo. Al terminar el ciclo, el pie SHALL mostrar "Actualizado hace 0 s".

#### Scenario: Actualizar
- **WHEN** el último ciclo terminó hace 40 segundos y el usuario hace click en actualizar
- **THEN** el botón se muestra ocupado, la lista refleja el resultado del nuevo ciclo y el pie vuelve a "Actualizado hace 0 s"

#### Scenario: Doble click
- **WHEN** el usuario hace click en actualizar mientras el ciclo anterior sigue en curso
- **THEN** no se pide otro ciclo
