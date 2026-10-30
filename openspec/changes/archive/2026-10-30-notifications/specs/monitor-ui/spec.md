## MODIFIED Requirements

### Requirement: Tamaño del panel
El panel SHALL tener un ancho fijo y un alto que se adapta a su contenido entre un mínimo y un máximo. La lista SHALL mostrar como máximo tantas filas como indique el ajuste "Servidores visibles"; con más servidores, o cuando el contenido supera el alto máximo, la lista SHALL hacer scroll interno mientras la cabecera y el pie permanecen visibles. Al cambiar de alto, el panel SHALL mantener su borde inferior junto a la bandeja.

#### Scenario: Pocos servidores
- **WHEN** hay dos servidores configurados
- **THEN** el panel es más bajo que el máximo y no muestra espacio vacío bajo la lista

#### Scenario: Muchos servidores
- **WHEN** la lista no cabe en el alto máximo
- **THEN** la lista hace scroll y la cabecera y el pie siguen visibles

#### Scenario: Servidores visibles
- **WHEN** hay seis servidores y "Servidores visibles" vale 4
- **THEN** la lista muestra cuatro filas completas y hace scroll para ver las otras dos

### Requirement: Cabecera del panel
La cabecera SHALL mostrar el nombre `MC Watch` y cinco botones, en este orden: actualizar, agregar, ajustes, fijar y cerrar. El botón agregar SHALL abrir el formulario para agregar un servidor. El botón ajustes SHALL abrir el diálogo de ajustes. El botón fijar SHALL indicar visualmente si el panel está fijado. Mientras el formulario está abierto, el título SHALL ser "Agregar servidor", los botones actualizar, agregar y ajustes SHALL ocultarse y SHALL mostrarse un botón volver que regresa a la lista. Mientras el detalle está abierto, el título SHALL ser el nombre del servidor y SHALL poder editarse, los botones agregar y ajustes SHALL ocultarse, el botón actualizar SHALL seguir visible y actualizar solo ese servidor, SHALL mostrarse el botón volver y SHALL mostrarse un botón eliminar, siempre en rojo, antes de fijar y cerrar.

#### Scenario: Botón agregar
- **WHEN** el usuario hace click en agregar
- **THEN** el panel muestra el formulario para agregar un servidor

#### Scenario: Botón actualizar junto a agregar
- **WHEN** el panel muestra la lista
- **THEN** el botón actualizar aparece inmediatamente a la izquierda del botón agregar

#### Scenario: Botón ajustes
- **WHEN** el panel muestra la lista y el usuario hace click en el engranaje
- **THEN** se abre el diálogo de ajustes

#### Scenario: Indicador de fijado
- **WHEN** el usuario activa fijar
- **THEN** el botón fijar se muestra activo

#### Scenario: Volver
- **WHEN** el formulario está abierto y el usuario hace click en volver
- **THEN** el panel muestra la lista sin agregar nada

#### Scenario: Cabecera del detalle
- **WHEN** el detalle de "Survival" está abierto
- **THEN** la cabecera muestra volver, "Survival", actualizar, eliminar en rojo, fijar y cerrar, y no muestra agregar ni ajustes

### Requirement: Preview en navegador
El proyecto SHALL ofrecer un modo preview que abre el panel en un navegador con datos de ejemplo que cubren los cuatro estados, las ediciones Bedrock y desconocida, y el estado vacío, sin iniciar la bandeja ni hacer consultas de red. En el preview, el formulario de agregar SHALL poder abrirse y SHALL simular la detección y sus resultados (éxito, host inexistente y edición desconocida) sin consultar la red ni escribir la configuración. Los datos de ejemplo SHALL incluir servidores con participantes en los modos full (con y sin jugadores), partial y hidden, un servidor dormido y un MOTD con colores. En el preview, renombrar y eliminar SHALL simularse sin escribir la configuración. En el preview, el diálogo de ajustes SHALL abrirse y guardar SHALL aplicar los servidores visibles a la lista sin escribir la configuración.

#### Scenario: Abrir el preview
- **WHEN** el desarrollador ejecuta el comando de preview
- **THEN** el navegador muestra el panel con servidores de ejemplo en los cuatro estados

#### Scenario: Formulario en el preview
- **WHEN** el desarrollador abre el formulario en el preview y agrega `no-existe.invalid`
- **THEN** el formulario muestra "Detectando…" y luego el error "No se encontró el host"

#### Scenario: Detalle en el preview
- **WHEN** el desarrollador abre en el preview el detalle de un servidor con muestra parcial
- **THEN** el detalle muestra sus nombres y "N de M jugadores"

#### Scenario: Ajustes en el preview
- **WHEN** el desarrollador guarda "Servidores visibles" = 3 en el preview
- **THEN** la lista muestra tres filas y hace scroll
