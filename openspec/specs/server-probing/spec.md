# server-probing Specification

## Purpose

Consultar periódicamente los servidores de Minecraft configurados y traducir cada respuesta a un estado estable (consultando, online, offline o error) y a un conteo de jugadores, evitando falsas caídas.

## Requirements

### Requirement: Sondeo de servidores Java
El sistema SHALL consultar cada servidor de edición Java mediante el Server List Ping de Minecraft Java Edition. Cuando la dirección no indique puerto, el sistema SHALL resolver el registro DNS SRV `_minecraft._tcp.<host>` y, si no existe, SHALL usar el puerto 25565. Cuando la dirección indique puerto, el sistema SHALL usar ese puerto.

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

### Requirement: Conteo de jugadores
Para cada servidor online, el sistema SHALL exponer el número de jugadores conectados y el máximo de jugadores reportados por la última respuesta. Para servidores que no están online, el sistema SHALL NOT exponer un conteo.

#### Scenario: Servidor online con jugadores
- **WHEN** un servidor responde con 7 jugadores conectados de un máximo de 20
- **THEN** el conteo expuesto es 7 de 20

#### Scenario: Servidor offline
- **WHEN** un servidor está en estado offline
- **THEN** no se expone conteo de jugadores

### Requirement: Sondeo de servidores Bedrock
El sistema SHALL consultar cada servidor de edición Bedrock mediante el ping de estado de Minecraft Bedrock Edition sobre UDP. Cuando la dirección no indique puerto, el sistema SHALL usar el puerto 19132; cuando lo indique, SHALL usar ese puerto. Un servidor Bedrock SHALL seguir las mismas reglas de estados, timeout y conteo de jugadores que uno Java.

#### Scenario: Bedrock con puerto por defecto
- **WHEN** la dirección de un servidor Bedrock es `bedrock.example.com`
- **THEN** el sistema consulta `bedrock.example.com:19132` por UDP

#### Scenario: Bedrock online
- **WHEN** un servidor Bedrock responde con 3 jugadores de un máximo de 10
- **THEN** el servidor está online con un conteo de 3 de 10

#### Scenario: Bedrock sin respuesta
- **WHEN** un servidor Bedrock no responde dos consultas seguidas
- **THEN** pasa a estado offline

### Requirement: Autodetección de la edición
Para un servidor de edición desconocida, cada consulta SHALL intentar Java y Bedrock sobre la misma dirección. Si Java responde, el servidor SHALL tomarse como Java aunque Bedrock también responda. Si solo Bedrock responde, SHALL tomarse como Bedrock. En ambos casos la edición del servidor SHALL quedar fijada y las consultas siguientes SHALL usar solo ese protocolo. Si ninguno responde, el servidor SHALL seguir como desconocido, la consulta SHALL contar como un fallo según las reglas de estados y la detección SHALL repetirse en el ciclo siguiente. La consulta de un servidor desconocido SHALL respetar el mismo timeout de 3 segundos por protocolo y SHALL NOT tardar más que la suma de ambos.

#### Scenario: Detectado como Java
- **WHEN** un servidor desconocido responde al Server List Ping
- **THEN** pasa a edición Java y queda online

#### Scenario: Servidor con ambos protocolos
- **WHEN** un servidor desconocido responde tanto a Java como a Bedrock
- **THEN** se toma como Java

#### Scenario: Sin respuesta
- **WHEN** un servidor desconocido no responde a ninguno de los dos protocolos en dos ciclos seguidos
- **THEN** sigue con edición desconocida, pasa a offline y se vuelve a intentar la detección en el ciclo siguiente

#### Scenario: Host inexistente
- **WHEN** el host de un servidor desconocido no resuelve por DNS
- **THEN** el servidor pasa a estado error, igual que uno Java

### Requirement: Sondeo a demanda
El sistema SHALL poder ejecutar un ciclo de sondeo fuera de calendario cuando el usuario lo pide. Un pedido que llega mientras un ciclo está en curso SHALL ignorarse. El ciclo a demanda SHALL consultar los mismos servidores y aplicar las mismas reglas de estados que uno periódico, y el siguiente ciclo periódico SHALL comenzar `poll_interval_secs` segundos después del inicio del ciclo a demanda.

#### Scenario: Ciclo a demanda
- **WHEN** faltan 50 segundos para el siguiente ciclo y el usuario pide actualizar
- **THEN** el sistema consulta todos los servidores de inmediato y el siguiente ciclo periódico comienza `poll_interval_secs` segundos después

#### Scenario: Pedido durante un ciclo
- **WHEN** el usuario pide actualizar mientras hay un ciclo en curso
- **THEN** no se inicia un ciclo adicional

### Requirement: Servidores dormidos
Una respuesta Java SHALL considerarse de un servidor dormido cuando se cumple cualquiera de estas condiciones:
- Su número de protocolo es `-1` y el nombre de versión, sin códigos de formato `§`, contiene "offline" o "sleeping", sin distinguir mayúsculas (proxies como Aternos).
- Su MOTD, sin códigos de formato `§`, contiene "server is sleeping", "server is starting" o "server going to sleep", sin distinguir mayúsculas (textos por defecto de lazymc), con cualquier número de protocolo.

Esa respuesta SHALL contar como respuesta Java a efectos de la autodetección de la edición. Cualquier otra respuesta exitosa SHALL considerarse un servidor online.

#### Scenario: Aternos apagado
- **WHEN** un servidor responde con protocolo `-1`, versión "§c● Offline" y 0 de 20 jugadores
- **THEN** el servidor queda offline y marcado como dormido

#### Scenario: Protocolo -1 sin la palabra clave
- **WHEN** un servidor responde con protocolo `-1` y versión "Mantenimiento"
- **THEN** el servidor queda online

#### Scenario: lazymc dormido
- **WHEN** un servidor responde con protocolo 777, versión "26.3", 0 de 0 jugadores y MOTD "☠ Server is sleeping\n§2☻ Join to start it up"
- **THEN** el servidor queda offline y marcado como dormido

#### Scenario: lazymc arrancando
- **WHEN** un servidor responde con el MOTD "§2☻ Server is starting...\n§7⌛ Please wait..."
- **THEN** el servidor queda offline y marcado como dormido

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
