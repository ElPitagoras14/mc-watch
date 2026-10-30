# server-probing Specification

## Purpose

Consultar periódicamente los servidores de Minecraft configurados y traducir cada respuesta a un estado estable (consultando, online, offline o error) y a un conteo de jugadores, evitando falsas caídas.

## Requirements

### Requirement: Sondeo de servidores Java
El sistema SHALL consultar cada servidor configurado mediante el Server List Ping de Minecraft Java Edition. Cuando la dirección no indique puerto, el sistema SHALL resolver el registro DNS SRV `_minecraft._tcp.<host>` y, si no existe, SHALL usar el puerto 25565. Cuando la dirección indique puerto, el sistema SHALL usar ese puerto.

#### Scenario: Servidor con puerto por defecto
- **WHEN** la dirección configurada es `play.example.com` sin registro SRV
- **THEN** el sistema consulta `play.example.com:25565`

#### Scenario: Servidor con registro SRV
- **WHEN** la dirección configurada es `example.com` y existe un registro SRV que apunta a `mc.example.com:25570`
- **THEN** el sistema consulta `mc.example.com:25570`

#### Scenario: Servidor con puerto explícito
- **WHEN** la dirección configurada es `example.com:25599`
- **THEN** el sistema consulta `example.com:25599` sin buscar registro SRV

### Requirement: Ciclo de sondeo periódico
El sistema SHALL consultar todos los servidores configurados en cada ciclo, de forma concurrente, y SHALL repetir el ciclo cada `poll_interval_secs` segundos. El primer ciclo SHALL comenzar al iniciar la app. Cada consulta individual SHALL abandonarse tras un timeout de 3 segundos, de modo que un servidor caído no retrase el resultado de los demás.

#### Scenario: Ciclo con un servidor lento
- **WHEN** un ciclo consulta tres servidores y uno no responde
- **THEN** los otros dos muestran su resultado sin esperar más de 3 segundos por el que no responde

#### Scenario: Intervalo configurado
- **WHEN** `poll_interval_secs` vale 90
- **THEN** un nuevo ciclo comienza 90 segundos después del inicio del anterior

### Requirement: Estados del servidor
El sistema SHALL asignar a cada servidor exactamente uno de cuatro estados:
- **consultando**: aún no hay un resultado concluyente desde que la app inició.
- **online**: la última consulta respondió.
- **offline**: las dos últimas consultas fallaron por timeout, conexión rechazada o respuesta inválida.
- **error**: el host no se pudo resolver por DNS.

Un único fallo SHALL NOT cambiar el estado de un servidor que estaba online; el servidor SHALL pasar a offline solo tras dos fallos consecutivos. Una respuesta exitosa SHALL poner el servidor en online de inmediato y SHALL reiniciar el conteo de fallos.

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

### Requirement: Conteo de jugadores
Para cada servidor online, el sistema SHALL exponer el número de jugadores conectados y el máximo de jugadores reportados por la última respuesta. Para servidores que no están online, el sistema SHALL NOT exponer un conteo.

#### Scenario: Servidor online con jugadores
- **WHEN** un servidor responde con 7 jugadores conectados de un máximo de 20
- **THEN** el conteo expuesto es 7 de 20

#### Scenario: Servidor offline
- **WHEN** un servidor está en estado offline
- **THEN** no se expone conteo de jugadores
