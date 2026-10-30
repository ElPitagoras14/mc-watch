## MODIFIED Requirements

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
