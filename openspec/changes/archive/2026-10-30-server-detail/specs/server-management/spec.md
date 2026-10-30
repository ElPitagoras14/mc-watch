## ADDED Requirements

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
