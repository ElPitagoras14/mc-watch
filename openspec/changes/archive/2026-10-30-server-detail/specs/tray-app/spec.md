## MODIFIED Requirements

### Requirement: Ocultar el panel
El botón cerrar SHALL ocultar el panel sin terminar la app. La tecla Escape SHALL ocultar el panel cuando muestra la lista de servidores. Cuando muestra el formulario de agregar o el detalle de un servidor, Escape SHALL volver a la lista sin ocultar el panel. Si en el detalle hay un renombrado o una confirmación de eliminación en curso, Escape SHALL cancelar solo eso. Cuando el panel no está fijado, perder el foco SHALL ocultarlo, también con el formulario o el detalle abiertos. Lo escrito en el formulario y la vista abierta SHALL conservarse hasta que el panel vuelva a mostrarse. El sondeo SHALL continuar con el panel oculto.

#### Scenario: Botón cerrar
- **WHEN** el usuario hace click en cerrar
- **THEN** el panel se oculta y el icono sigue en la bandeja

#### Scenario: Escape
- **WHEN** el panel muestra la lista, tiene foco y el usuario presiona Escape
- **THEN** el panel se oculta

#### Scenario: Escape en el formulario
- **WHEN** el panel muestra el formulario y el usuario presiona Escape
- **THEN** el panel vuelve a la lista y sigue visible

#### Scenario: Escape en el detalle
- **WHEN** el panel muestra el detalle de un servidor, sin renombrado ni confirmación en curso, y el usuario presiona Escape
- **THEN** el panel vuelve a la lista y sigue visible

#### Scenario: Escape durante la confirmación
- **WHEN** la confirmación de eliminar está abierta y el usuario presiona Escape
- **THEN** la confirmación se cierra y el detalle sigue abierto

#### Scenario: Click fuera sin fijar
- **WHEN** el panel no está fijado y el usuario hace click en otra ventana
- **THEN** el panel se oculta

#### Scenario: Click fuera con el formulario a medias
- **WHEN** el usuario escribió una dirección en el formulario y el panel se oculta al perder el foco
- **THEN** al reabrir el panel el formulario sigue abierto con la dirección escrita

#### Scenario: Click fuera con el detalle abierto
- **WHEN** el detalle de un servidor está abierto y el panel se oculta al perder el foco
- **THEN** al reabrir el panel sigue mostrando ese detalle
