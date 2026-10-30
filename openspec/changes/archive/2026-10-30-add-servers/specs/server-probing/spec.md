## MODIFIED Requirements

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

## ADDED Requirements

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
