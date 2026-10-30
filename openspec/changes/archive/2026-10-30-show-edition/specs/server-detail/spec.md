## MODIFIED Requirements

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
