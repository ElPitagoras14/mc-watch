# server-management Specification

## Purpose

Permitir que el usuario administre su lista de servidores desde el panel, sin editar `config.toml` a mano. En este change cubre el alta de servidores: formulario, validación, detección de la edición y persistencia.

## Requirements

### Requirement: Formulario para agregar
El botón agregar de la cabecera SHALL abrir, dentro del mismo panel, una vista de formulario con el título "Agregar servidor", un campo de nombre, un campo de dirección y los botones "Cancelar" y "Agregar". El foco SHALL quedar en el campo de dirección. "Cancelar", la tecla Escape y el botón volver SHALL regresar a la lista sin guardar nada. La tecla Enter en cualquiera de los campos SHALL equivaler a "Agregar".

#### Scenario: Abrir el formulario
- **WHEN** el usuario hace click en agregar
- **THEN** el panel muestra el formulario vacío con el foco en la dirección

#### Scenario: Cancelar
- **WHEN** el usuario escribió una dirección y presiona Escape
- **THEN** el panel vuelve a la lista, el servidor no se agrega y el panel sigue visible

### Requirement: Validación del formulario
La dirección SHALL ser obligatoria y tener la forma `host` o `host:puerto`, con el puerto en 1–65535; los espacios al inicio y al final SHALL ignorarse. El nombre SHALL ser opcional: si queda vacío, el servidor SHALL usar la dirección como nombre. El nombre SHALL tener como máximo 40 caracteres. Una dirección que ya está en la lista, sin distinguir mayúsculas de minúsculas, SHALL rechazarse. Un error de validación SHALL mostrarse junto al campo correspondiente y SHALL NOT iniciar la detección.

#### Scenario: Dirección vacía
- **WHEN** el usuario pulsa "Agregar" sin dirección
- **THEN** el formulario indica que la dirección es obligatoria y no consulta ningún servidor

#### Scenario: Puerto inválido
- **WHEN** la dirección es `play.example.com:70000`
- **THEN** el formulario indica que la dirección no es válida

#### Scenario: Nombre vacío
- **WHEN** el usuario agrega `play.example.com` sin nombre y el servidor responde
- **THEN** la fila nueva se llama "play.example.com"

#### Scenario: Duplicado
- **WHEN** la lista ya tiene `play.example.com` y el usuario intenta agregar `Play.Example.com`
- **THEN** el formulario indica que ese servidor ya está en la lista y no lo agrega

### Requirement: Detección de la edición al agregar
Al pulsar "Agregar" con datos válidos, el sistema SHALL detectar la edición del servidor y mientras tanto SHALL mostrar "Detectando…" con los campos y el botón "Agregar" deshabilitados. La detección SHALL terminar en a lo sumo unos pocos segundos aunque el servidor no responda. El resultado SHALL ser:
- Si el servidor responde como Java o como Bedrock, se agrega con esa edición y el panel vuelve a la lista.
- Si el host no resuelve por DNS, el formulario muestra "No se encontró el host" junto a la dirección, conserva lo escrito y no agrega nada.
- Si el host resuelve pero no responde como ninguna edición, el servidor se agrega con edición desconocida y el panel vuelve a la lista.

#### Scenario: Servidor Java
- **WHEN** el usuario agrega `mc.hypixel.net`
- **THEN** el panel muestra "Detectando…", vuelve a la lista y la fila nueva está online con su edición guardada como Java

#### Scenario: Servidor Bedrock
- **WHEN** el usuario agrega la dirección de un servidor que solo responde a Bedrock
- **THEN** la fila nueva aparece online y marcada como Bedrock

#### Scenario: Host inexistente
- **WHEN** el usuario agrega `no-existe.invalid`
- **THEN** el formulario sigue abierto con el error "No se encontró el host" y la lista no cambia

#### Scenario: Nadie responde
- **WHEN** el host resuelve pero no responde ni como Java ni como Bedrock
- **THEN** el servidor se agrega con edición desconocida y su fila muestra el aviso

### Requirement: Servidor agregado
Un servidor agregado SHALL aparecer al final de la lista de inmediato, con el estado y los jugadores obtenidos en la detección, sin esperar al siguiente ciclo de sondeo. Desde ese momento SHALL formar parte de los ciclos de sondeo y del conteo del icono de la bandeja. El servidor SHALL guardarse en `config.toml` antes de aparecer en la lista, de modo que siga presente al reiniciar la app.

#### Scenario: Aparece al instante
- **WHEN** el usuario agrega un servidor que responde con 4 de 20 jugadores
- **THEN** la lista muestra su fila online con "4/20" y el icono de la bandeja suma uno, sin esperar al siguiente ciclo

#### Scenario: Persistencia
- **WHEN** el usuario agrega un servidor y reinicia la app
- **THEN** el servidor sigue en la lista, con la misma edición

### Requirement: Fallo al guardar
Si la configuración no se puede escribir, el formulario SHALL mostrar un mensaje con el motivo y SHALL NOT agregar el servidor a la lista. Cuando `config.toml` tiene un error de sintaxis, el formulario SHALL avisar, antes de detectar nada, que hay que corregir el archivo para poder agregar servidores, e indicar su ruta.

#### Scenario: Config con error de sintaxis
- **WHEN** `config.toml` contiene TOML inválido y el usuario abre el formulario
- **THEN** el formulario muestra el aviso con la ruta del archivo y el botón "Agregar" deshabilitado

#### Scenario: Archivo no escribible
- **WHEN** la escritura de `config.toml` falla por permisos
- **THEN** el formulario muestra que no se pudo guardar y la lista no cambia

### Requirement: Renombrar un servidor
Un click en el nombre del servidor, en la cabecera del detalle, SHALL convertirlo en un campo editable con el nombre actual seleccionado. Enter o perder el foco SHALL guardar el nombre, y Escape SHALL cancelar y restaurar el nombre anterior sin cerrar el detalle. El nombre SHALL seguir las mismas reglas que en el formulario de agregar: se recortan los espacios, admite hasta 40 caracteres y, si queda vacío, el servidor usa su dirección como nombre. Un nombre sin cambios SHALL NOT escribir la configuración. El nombre nuevo SHALL guardarse en `config.toml` y SHALL verse de inmediato en el detalle y en la lista, sin esperar al siguiente ciclo. Si la configuración no se puede escribir, el detalle SHALL mostrar el motivo y conservar el nombre anterior.

#### Scenario: Renombrar
- **WHEN** el usuario hace click en "play.example.com", escribe "Survival" y presiona Enter
- **THEN** el detalle y la lista muestran "Survival", y `config.toml` tiene `name = "Survival"` en esa entrada

#### Scenario: Cancelar
- **WHEN** el usuario está renombrando y presiona Escape
- **THEN** el nombre vuelve a ser el anterior, el detalle sigue abierto y el archivo no cambia

#### Scenario: Nombre vacío
- **WHEN** el usuario borra el nombre y presiona Enter
- **THEN** el servidor pasa a llamarse como su dirección

#### Scenario: Config no escribible
- **WHEN** `config.toml` tiene un error de sintaxis y el usuario intenta renombrar
- **THEN** el detalle muestra que no se pudo guardar y el nombre sigue siendo el anterior

#### Scenario: Persistencia
- **WHEN** el usuario renombra un servidor y reinicia la app
- **THEN** el servidor conserva el nombre nuevo

### Requirement: Eliminar un servidor
El botón eliminar de la cabecera del detalle SHALL pedir confirmación dentro del panel, sin diálogos del sistema, con el nombre del servidor y los botones "Cancelar" y "Eliminar". Cancelar o Escape SHALL cerrar la confirmación sin cambios. Al confirmar, el servidor SHALL quitarse de `config.toml` y luego de la lista y de los ciclos de sondeo, y el panel SHALL volver a la lista. El conteo del icono de la bandeja SHALL actualizarse de inmediato. Si la configuración no se puede escribir, la confirmación SHALL mostrar el motivo y el servidor SHALL seguir en la lista.

#### Scenario: Eliminar
- **WHEN** el usuario abre el detalle de "Survival", pulsa eliminar y confirma
- **THEN** el panel vuelve a la lista sin "Survival", su entrada desaparece de `config.toml` y el icono de la bandeja deja de contarlo

#### Scenario: Cancelar
- **WHEN** el usuario pulsa eliminar y luego "Cancelar"
- **THEN** el detalle sigue abierto y el servidor sigue en la lista y en el archivo

#### Scenario: Fallo al guardar
- **WHEN** la escritura de `config.toml` falla al confirmar la eliminación
- **THEN** la confirmación muestra el motivo y el servidor sigue en la lista

#### Scenario: Eliminar durante un ciclo
- **WHEN** el usuario confirma la eliminación mientras hay un ciclo de sondeo en curso
- **THEN** el servidor no reaparece cuando el ciclo termina

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
