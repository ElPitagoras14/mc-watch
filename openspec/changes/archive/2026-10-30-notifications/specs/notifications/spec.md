## ADDED Requirements

### Requirement: Eventos notificables
Con las notificaciones activadas, el sistema SHALL mostrar una notificación de Windows cuando, entre dos snapshots consecutivos, un servidor que estaba en ambos:
- pasa de online con 0 jugadores a online con 1 o más: "Alguien está jugando en <nombre>";
- tiene `players_mode == full` en ambos snapshots y aparecen nombres que no estaban: "<nombre del jugador> entró a <nombre>" (con varios nombres, todos en la misma notificación). En ese caso SHALL NOT emitirse además "Alguien está jugando";
- pasa de online a offline o error: "<nombre> se cayó";
- pasa de offline o error a online: "<nombre> volvió a estar online".

Un nombre que aparece mientras el modo es `partial` o `hidden`, o cuando el snapshot anterior no tenía modo `full`, SHALL NOT notificarse como "entró". La comparación de nombres SHALL ignorar mayúsculas.

#### Scenario: Alguien está jugando
- **WHEN** "Survival" está online con 0 jugadores en modo hidden y en el siguiente ciclo tiene 2
- **THEN** se muestra "Alguien está jugando en Survival"

#### Scenario: Jugador entró
- **WHEN** "Survival" está online en modo full con `["Ana"]` y en el siguiente ciclo tiene `["Ana", "Beto"]`
- **THEN** se muestra "Beto entró a Survival"

#### Scenario: De 0 a 1 con nombres
- **WHEN** "Survival" está online en modo full con 0 jugadores y en el siguiente ciclo tiene `["Ana"]`
- **THEN** se muestra solo "Ana entró a Survival"

#### Scenario: Muestra parcial
- **WHEN** un servidor en modo partial muestra en un ciclo nombres distintos a los del anterior
- **THEN** no se notifica ningún "entró"

#### Scenario: Caída
- **WHEN** un servidor online pasa a offline tras dos fallos seguidos
- **THEN** se muestra "<nombre> se cayó"

#### Scenario: Vuelve
- **WHEN** un servidor offline responde de nuevo
- **THEN** se muestra "<nombre> volvió a estar online"

### Requirement: Una sola vez y sin avalancha
Cada evento SHALL notificarse una sola vez: solo la transición entre dos snapshots lo genera, y mientras el estado no cambie SHALL NOT repetirse. Un servidor que pasa de Consultando a cualquier estado, un servidor recién agregado y el primer ciclo tras iniciar la app SHALL NOT generar notificaciones. Con las notificaciones desactivadas, SHALL NOT mostrarse nada; al activarlas, SHALL notificarse solo lo que ocurra desde ese momento.

#### Scenario: Inicio con jugadores
- **WHEN** la app inicia con las notificaciones activas y un servidor ya tiene jugadores
- **THEN** no se muestra ninguna notificación

#### Scenario: Sin cambios
- **WHEN** un servidor sigue con los mismos 3 jugadores en varios ciclos
- **THEN** no se muestra ninguna notificación después de la primera

#### Scenario: Desactivadas
- **WHEN** las notificaciones están desactivadas y alguien entra a un servidor
- **THEN** no se muestra nada

### Requirement: Agrupación
Si un mismo snapshot genera más de tres notificaciones, el sistema SHALL mostrar una sola notificación "mc-watch: N novedades" cuyo texto nombra los tres primeros servidores afectados.

#### Scenario: Cuatro eventos
- **WHEN** al volver la conexión cuatro servidores pasan de offline a online en el mismo ciclo
- **THEN** se muestra una sola notificación "mc-watch: 4 novedades"

### Requirement: Click en una notificación
El click en una notificación de un servidor SHALL mostrar el panel con el detalle de ese servidor. El click en la notificación agrupada SHALL mostrar el panel con la lista. Si el servidor ya no existe, SHALL mostrarse la lista.

#### Scenario: Abrir el detalle
- **WHEN** el usuario hace click en "Beto entró a Survival"
- **THEN** el panel aparece mostrando el detalle de "Survival"

### Requirement: Fallo al notificar
Si Windows no puede mostrar una notificación, el sistema SHALL registrarlo una vez en el log y SHALL NOT interrumpir el sondeo ni el panel.

#### Scenario: Notificaciones bloqueadas
- **WHEN** el sistema rechaza la notificación
- **THEN** el error queda en el log y la app sigue funcionando
