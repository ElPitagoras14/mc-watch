## MODIFIED Requirements

### Requirement: Estados del servidor
El sistema SHALL asignar a cada servidor exactamente uno de cuatro estados:
- **consultando**: aún no hay un resultado concluyente desde que la app inició.
- **online**: la última consulta respondió y el servidor no está dormido.
- **offline**: las dos últimas consultas fallaron por timeout, conexión rechazada o respuesta inválida, o la última respuesta indica un servidor dormido.
- **error**: el host no se pudo resolver por DNS.

Un único fallo SHALL NOT cambiar el estado de un servidor que estaba online. El servidor SHALL pasar a offline solo tras dos fallos consecutivos. Una respuesta de servidor dormido SHALL poner el servidor en offline de inmediato, porque es una respuesta concluyente y no un fallo. Una respuesta exitosa SHALL poner el servidor en online de inmediato y SHALL reiniciar el conteo de fallos.

#### Scenario: Inicio de la app
- **WHEN** la app acaba de iniciar y el primer ciclo no ha terminado
- **THEN** todos los servidores están en estado consultando

#### Scenario: Fallo aislado
- **WHEN** un servidor online falla una consulta
- **THEN** sigue en estado online

#### Scenario: Dos fallos seguidos
- **WHEN** un servidor falla dos consultas consecutivas
- **THEN** pasa a estado offline

#### Scenario: Primer ciclo fallido
- **WHEN** un servidor falla la primera consulta tras iniciar la app
- **THEN** sigue en estado consultando hasta el resultado de la siguiente consulta

#### Scenario: Recuperación
- **WHEN** un servidor offline responde una consulta
- **THEN** pasa a estado online en ese mismo ciclo

#### Scenario: Host inexistente
- **WHEN** el host configurado no resuelve por DNS
- **THEN** el servidor pasa a estado error sin esperar un segundo fallo

#### Scenario: Servidor dormido
- **WHEN** un servidor online responde como dormido
- **THEN** pasa a estado offline en ese mismo ciclo, sin conteo de jugadores

## ADDED Requirements

### Requirement: Servidores dormidos
Una respuesta Java SHALL considerarse de un servidor dormido cuando su número de protocolo es `-1` y el nombre de versión, sin códigos de formato `§`, contiene "offline" o "sleeping", sin distinguir mayúsculas. Esa respuesta SHALL contar como respuesta Java a efectos de la autodetección de la edición. Cualquier otra respuesta exitosa SHALL considerarse un servidor online.

#### Scenario: Aternos apagado
- **WHEN** un servidor responde con protocolo `-1`, versión "§c● Offline" y 0 de 20 jugadores
- **THEN** el servidor queda offline y marcado como dormido

#### Scenario: Protocolo -1 sin la palabra clave
- **WHEN** un servidor responde con protocolo `-1` y versión "Mantenimiento"
- **THEN** el servidor queda online

#### Scenario: Dormido durante la detección
- **WHEN** un servidor de edición desconocida responde como dormido
- **THEN** su edición queda fijada como Java y el servidor queda offline

### Requirement: Información del servidor
Para cada servidor online, el sistema SHALL exponer el MOTD como una secuencia de segmentos de texto con su color y estilos (negrita, cursiva, subrayado y tachado), el nombre de versión sin códigos de formato `§`, la latencia en milisegundos de la última respuesta y, para Java, el icono cuando el servidor lo envía como PNG. Un icono en otro formato SHALL descartarse. Para servidores que no están online, el sistema SHALL NOT exponer esta información.

#### Scenario: MOTD con colores
- **WHEN** un servidor Java responde con el MOTD `§aHola §lmundo`
- **THEN** el MOTD expuesto es "Hola " en verde y "mundo" en verde y negrita

#### Scenario: Icono inválido
- **WHEN** un servidor envía un icono que no es `data:image/png;base64,…`
- **THEN** no se expone icono para ese servidor

### Requirement: Lista de jugadores
Para cada servidor Java online, el sistema SHALL intentar obtener la lista de jugadores por Query (UDP, en el mismo puerto que el ping), en paralelo con el ping y con el mismo timeout. El sistema SHALL recordar en memoria si cada servidor respondió a Query:
- Mientras no se sepa, o después de un éxito, SHALL intentarlo en cada ciclo.
- Tras un fallo, SHALL reintentarlo cada 10 ciclos en los que el servidor esté online.

Un fallo de Query SHALL NOT afectar el estado del servidor. Sin Query, el sistema SHALL usar la muestra de jugadores del ping, descartando las entradas con UUID nulo (`00000000-0000-0000-0000-000000000000`), las que contienen `§` y las cuyo nombre no cumple `[A-Za-z0-9_]{3,16}`, y quitando los nombres repetidos.

El sistema SHALL exponer un modo de jugadores y los nombres conocidos:
- **full**: Query respondió, la cantidad de nombres válidos de la muestra es igual al número de jugadores conectados o hay 0 jugadores conectados.
- **partial**: hay al menos un nombre válido, pero menos que los jugadores conectados.
- **hidden**: hay jugadores conectados y ningún nombre válido, o el servidor es Bedrock.

#### Scenario: Query disponible
- **WHEN** un servidor Java responde a Query con los jugadores "Steve" y "Alex"
- **THEN** el modo es full con los nombres "Steve" y "Alex"

#### Scenario: Query no disponible, muestra completa
- **WHEN** un servidor no responde a Query, tiene 2 jugadores y la muestra trae "Steve" y "Alex"
- **THEN** el modo es full con esos dos nombres y el servidor sigue online

#### Scenario: Muestra parcial
- **WHEN** un servidor sin Query tiene 23 jugadores y la muestra trae 12 nombres válidos
- **THEN** el modo es partial con esos 12 nombres

#### Scenario: Muestra decorativa
- **WHEN** la muestra de un servidor con 40000 jugadores solo trae entradas con códigos `§` o UUID nulo
- **THEN** el modo es hidden

#### Scenario: Servidor vacío
- **WHEN** un servidor online tiene 0 jugadores
- **THEN** el modo es full sin nombres

#### Scenario: Bedrock
- **WHEN** un servidor Bedrock tiene 4 jugadores
- **THEN** el modo es hidden

#### Scenario: Reintento de Query
- **WHEN** un servidor falló Query y luego estuvo online 9 ciclos seguidos
- **THEN** en esos 9 ciclos no se consulta Query y en el décimo se vuelve a intentar
