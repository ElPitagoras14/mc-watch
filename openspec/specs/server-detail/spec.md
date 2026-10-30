# server-detail Specification

## Purpose
TBD - created by archiving change server-detail. Update Purpose after archive.

## Requirements

### Requirement: Abrir y cerrar el detalle
Un click en la fila de un servidor SHALL abrir, dentro del mismo panel, la vista de detalle de ese servidor. La fila SHALL poder abrirse también con el teclado (Enter o Espacio con la fila enfocada). El botón volver, la tecla Escape y la eliminación del servidor SHALL regresar a la lista. Al volver, la lista SHALL mostrarse con los datos del último ciclo.

#### Scenario: Abrir con click
- **WHEN** el usuario hace click en la fila "Survival"
- **THEN** el panel muestra el detalle de "Survival"

#### Scenario: Abrir con teclado
- **WHEN** la fila "Survival" tiene el foco y el usuario presiona Enter
- **THEN** el panel muestra el detalle de "Survival"

#### Scenario: Volver
- **WHEN** el detalle está abierto y el usuario hace click en volver
- **THEN** el panel muestra la lista

### Requirement: Información del servidor
El detalle SHALL mostrar el icono del servidor, su MOTD con los colores y estilos (negrita, cursiva, subrayado y tachado) que define el servidor, la versión, la latencia en milisegundos, la dirección y la edición ("Java", "Bedrock" o "edición desconocida"). La edición SHALL mostrarse siempre, esté el servidor online o no. Cuando el servidor no tiene icono, como los Bedrock, SHALL mostrarse un icono genérico. Cuando el servidor no está online, el detalle SHALL mostrar su estado en lugar del MOTD, la versión y la latencia. El texto del MOTD SHALL mostrarse siempre como texto, nunca interpretarse como HTML.

#### Scenario: Servidor Java online
- **WHEN** el detalle muestra un servidor online con icono, MOTD "§aBienvenidos", versión "1.21.4" y 45 ms de latencia
- **THEN** se ven el icono, "Bienvenidos" en verde, "1.21.4", "45 ms" y la indicación "Java"

#### Scenario: Servidor Bedrock
- **WHEN** el detalle muestra un servidor Bedrock online
- **THEN** se ven un icono genérico, su MOTD, su versión, su latencia y la indicación "Bedrock"

#### Scenario: Servidor offline
- **WHEN** el detalle muestra un servidor Java offline
- **THEN** se ve el estado Offline en lugar del MOTD, la versión y la latencia, y se sigue viendo la indicación "Java"

#### Scenario: Edición desconocida
- **WHEN** el detalle muestra un servidor de edición desconocida
- **THEN** se ve la indicación "edición desconocida"

#### Scenario: MOTD con marcado HTML
- **WHEN** el MOTD de un servidor contiene `<img src=x onerror=alert(1)>`
- **THEN** el detalle muestra ese texto literal y no se ejecuta nada

### Requirement: Participantes
El detalle SHALL tener una sección "Participantes" cuyo contenido depende del modo de jugadores del servidor:
- **full** con jugadores: la lista de nombres.
- **full** con 0 jugadores: "Nadie está jugando".
- **partial**: los nombres conocidos y, debajo, "N de M jugadores", donde N es la cantidad de nombres y M el total conectado.
- **hidden**: "Este servidor no comparte la lista de jugadores" junto con el conteo `X/Y`.

Cuando el servidor no está online, la sección SHALL indicar que no hay datos de jugadores.

#### Scenario: Lista completa
- **WHEN** un servidor tiene 3 jugadores y comparte sus 3 nombres
- **THEN** la sección muestra los 3 nombres

#### Scenario: Nadie jugando
- **WHEN** un servidor online tiene 0 jugadores
- **THEN** la sección muestra "Nadie está jugando"

#### Scenario: Muestra parcial
- **WHEN** un servidor tiene 23 jugadores y comparte 5 nombres válidos
- **THEN** la sección muestra los 5 nombres y "5 de 23 jugadores"

#### Scenario: Lista oculta
- **WHEN** un servidor Bedrock tiene 4 de 10 jugadores
- **THEN** la sección muestra "Este servidor no comparte la lista de jugadores" y "4/10"

### Requirement: Servidor dormido en el detalle
Cuando un servidor está offline porque su proveedor respondió que está apagado (servidor dormido), el detalle SHALL indicar que el proveedor responde pero el servidor está apagado.

#### Scenario: Aternos apagado
- **WHEN** el detalle muestra un servidor de Aternos que está apagado
- **THEN** se ve el estado Offline y la explicación de que el servidor está apagado

### Requirement: Actualizar solo este servidor
El botón actualizar del detalle SHALL consultar solo el servidor abierto, sin esperar al siguiente ciclo y sin consultar los demás. Mientras la consulta está en curso, el botón SHALL mostrarse ocupado y deshabilitado. Al terminar, el detalle SHALL mostrar el resultado y el pie ("Actualizado hace…") SHALL conservar la hora del último ciclo completo. La consulta SHALL aplicar las mismas reglas de estados que un ciclo.

#### Scenario: Actualizar un servidor
- **WHEN** el detalle de "Survival" está abierto y el usuario pulsa actualizar
- **THEN** solo "Survival" se consulta, el botón se muestra ocupado hasta que llega el resultado y los demás servidores no cambian

#### Scenario: Servidor eliminado durante la consulta
- **WHEN** el servidor se elimina mientras su consulta está en curso
- **THEN** el resultado se descarta y el servidor no reaparece

### Requirement: Detalle en vivo
Mientras el detalle está abierto, cada ciclo de sondeo SHALL actualizar su estado, información y participantes sin cerrar la vista ni perder un renombrado o una confirmación en curso.

#### Scenario: Entra un jugador
- **WHEN** el detalle de un servidor está abierto y un ciclo trae un jugador nuevo en la lista completa
- **THEN** el nombre aparece en la sección de participantes sin que el usuario haga nada

#### Scenario: Ciclo durante el renombrado
- **WHEN** el usuario está escribiendo un nombre nuevo y termina un ciclo de sondeo
- **THEN** el campo conserva lo que el usuario escribió
