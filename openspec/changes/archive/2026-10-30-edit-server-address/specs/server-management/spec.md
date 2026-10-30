## ADDED Requirements

### Requirement: Cambiar la dirección de un servidor
En el detalle, la dirección del servidor SHALL poder editarse: un click o Enter sobre ella, o sobre el lápiz que se ve a su lado, SHALL convertirla en un campo con la dirección actual seleccionada y el foco en él. Enter SHALL guardar y Escape SHALL cancelar y restaurar la dirección anterior sin cerrar el detalle; perder el foco SHALL cancelar. La dirección nueva SHALL seguir las mismas reglas que en el formulario de agregar: se ignoran los espacios al inicio y al final, es obligatoria, tiene la forma `host` o `host:puerto` con el puerto en 1–65535 y no puede ser la de otro servidor de la lista, sin distinguir mayúsculas de minúsculas. Una dirección sin cambios SHALL NOT escribir la configuración ni consultar nada.

Con una dirección válida, el sistema SHALL detectar la edición del servidor en esa dirección, como al agregar, y mientras tanto el campo SHALL mostrarse deshabilitado. Si el host no resuelve por DNS, el detalle SHALL mostrar "No se encontró el host", dejar el campo abierto con lo escrito y no cambiar nada. Si el host resuelve pero no responde como ninguna edición, la dirección SHALL guardarse con edición desconocida.

Al guardar, el servidor SHALL conservar su lugar en la lista y su nombre, salvo que el nombre fuera igual a la dirección anterior, en cuyo caso SHALL pasar a llamarse como la dirección nueva. Su estado SHALL reiniciarse con el resultado de la detección, sin esperar al siguiente ciclo, y el detalle SHALL seguir abierto sobre el mismo servidor con la dirección nueva. El cambio SHALL guardarse en `config.toml` antes de verse en la lista, y SHALL NOT generar ninguna notificación. Si la configuración no se puede escribir, el detalle SHALL mostrar el motivo y conservar la dirección anterior.

#### Scenario: Cambiar el puerto
- **WHEN** el usuario hace click en la dirección `play.example.com`, escribe `play.example.com:25566` y presiona Enter, y el servidor responde en ese puerto
- **THEN** el detalle sigue abierto mostrando `play.example.com:25566`, la fila conserva su lugar y su nombre, y `config.toml` tiene esa dirección en la misma entrada

#### Scenario: Abrir con el lápiz o el teclado
- **WHEN** el usuario pulsa el lápiz junto a la dirección, o enfoca la dirección con el teclado y presiona Enter
- **THEN** la dirección se convierte en un campo editable con su texto seleccionado

#### Scenario: Cancelar
- **WHEN** el usuario está editando la dirección y presiona Escape
- **THEN** la dirección vuelve a ser la anterior, el detalle sigue abierto y el archivo no cambia

#### Scenario: Dirección duplicada
- **WHEN** la lista ya tiene `b.example.com` y el usuario cambia la dirección de otro servidor a `B.Example.com`
- **THEN** el detalle indica que ese servidor ya está en la lista y no cambia nada

#### Scenario: Dirección vacía o inválida
- **WHEN** el usuario deja la dirección vacía o escribe `play.example.com:70000` y presiona Enter
- **THEN** el detalle indica el error, el campo sigue abierto con lo escrito y no se consulta nada

#### Scenario: Host inexistente
- **WHEN** el usuario cambia la dirección a `no-existe.invalid`
- **THEN** el detalle muestra "No se encontró el host", la dirección guardada sigue siendo la anterior y el campo sigue abierto

#### Scenario: Nadie responde
- **WHEN** el host nuevo resuelve pero no responde ni como Java ni como Bedrock
- **THEN** la dirección se guarda, el servidor pasa a edición desconocida y el detalle muestra su estado

#### Scenario: Nombre igual a la dirección
- **WHEN** un servidor se llama como su dirección `a.example.com` y el usuario cambia la dirección a `b.example.com`
- **THEN** el servidor pasa a llamarse `b.example.com`

#### Scenario: Cambio de edición
- **WHEN** el servidor era Java y la dirección nueva responde como Bedrock
- **THEN** el detalle muestra "Bedrock" y `config.toml` guarda esa edición

#### Scenario: Sin notificaciones
- **WHEN** el servidor estaba online con jugadores y su dirección nueva responde online con otros jugadores
- **THEN** no se muestra ninguna notificación

#### Scenario: Ciclo en curso
- **WHEN** el usuario guarda la dirección nueva mientras hay un ciclo de sondeo en curso que consultaba la dirección anterior
- **THEN** el resultado de ese ciclo se descarta y el servidor conserva el estado de la dirección nueva

#### Scenario: Config no escribible
- **WHEN** `config.toml` tiene un error de sintaxis y el usuario intenta cambiar la dirección
- **THEN** el detalle muestra que no se pudo guardar y la dirección sigue siendo la anterior

#### Scenario: Persistencia
- **WHEN** el usuario cambia la dirección de un servidor y reinicia la app
- **THEN** el servidor conserva la dirección nueva y su lugar en la lista
