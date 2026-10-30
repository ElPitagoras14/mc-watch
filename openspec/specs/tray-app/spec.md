# tray-app Specification

## Purpose

Definir la presencia de `mc-watch` en la bandeja de Windows: el icono con el conteo de servidores online, su menú y cómo se abre, oculta y fija el panel.

## Requirements

### Requirement: Icono con servidores online
El sistema SHALL mostrar un icono en la bandeja de Windows que contiene el número de servidores en estado online. Cuando no hay servidores configurados, el icono SHALL mostrarse sin número. El icono SHALL actualizarse al terminar cada ciclo de sondeo. El icono SHALL usar colores legibles tanto en la barra de tareas clara como en la oscura.

#### Scenario: Dos servidores online
- **WHEN** hay tres servidores configurados y dos están online
- **THEN** el icono muestra "2"

#### Scenario: Ninguno online
- **WHEN** hay servidores configurados y ninguno está online
- **THEN** el icono muestra "0"

#### Scenario: Diez o más servidores online
- **WHEN** diez o más servidores están online
- **THEN** el icono muestra "9+"

#### Scenario: Antes del primer ciclo
- **WHEN** la app acaba de iniciar y el primer ciclo de sondeo no ha terminado
- **THEN** el icono se muestra sin número y el tooltip dice "mc-watch — consultando…"

#### Scenario: Tema de la barra de tareas
- **WHEN** Windows usa la barra de tareas clara
- **THEN** el icono se dibuja con colores que contrastan con un fondo claro

### Requirement: Tooltip del icono
Al pasar el puntero sobre el icono, el sistema SHALL mostrar un tooltip con el nombre de la app y el conteo de servidores online sobre el total.

#### Scenario: Tooltip
- **WHEN** dos de tres servidores están online
- **THEN** el tooltip dice "mc-watch — 2/3 online"

### Requirement: Menú del icono
El click derecho sobre el icono SHALL abrir un menú con las entradas "Abrir mc-watch" y "Salir". "Salir" SHALL terminar la app por completo, incluido el sondeo.

#### Scenario: Salir
- **WHEN** el usuario elige "Salir"
- **THEN** el icono desaparece y el proceso termina

### Requirement: Abrir el panel
El click izquierdo sobre el icono, o la entrada "Abrir mc-watch", SHALL mostrar el panel junto al área de notificación, dentro del área de trabajo de la pantalla y sin quedar tapado por la barra de tareas. Si el panel ya está visible, el click izquierdo SHALL ocultarlo.

#### Scenario: Abrir
- **WHEN** el panel está oculto y el usuario hace click izquierdo en el icono
- **THEN** el panel aparece junto a la bandeja, al frente y con foco

#### Scenario: Alternar
- **WHEN** el panel está visible y el usuario hace click izquierdo en el icono
- **THEN** el panel se oculta

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

### Requirement: Fijar el panel
El botón fijar SHALL alternar el modo fijado. Con el panel fijado, perder el foco SHALL NOT ocultarlo, y el panel SHALL mantenerse por encima de las demás ventanas. El modo fijado SHALL durar solo mientras la app esté en ejecución.

#### Scenario: Click fuera con panel fijado
- **WHEN** el panel está fijado y el usuario hace click en otra ventana
- **THEN** el panel sigue visible

#### Scenario: Reinicio
- **WHEN** el usuario fijó el panel y luego reinicia la app
- **THEN** el panel inicia sin fijar
