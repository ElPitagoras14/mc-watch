## MODIFIED Requirements

### Requirement: Lista de servidores
El panel SHALL mostrar una fila por servidor configurado con su nombre, su dirección tal como está en la configuración, su estado (Consultando, Online, Offline o Error) con un indicador de color, y sus jugadores en formato `X/Y`. Cuando el servidor no está online, la columna de jugadores SHALL mostrar `—`. Junto a la dirección, la fila SHALL indicar la edición del servidor: "Java", "Bedrock" o, si no se ha detectado, el aviso "edición desconocida". Cada fila SHALL ser interactiva: SHALL mostrar un estado al pasar el puntero y al recibir el foco del teclado, y SHALL abrir el detalle del servidor.

#### Scenario: Servidor online
- **WHEN** el servidor "Survival" en `play.example.com` está online con 3 de 20 jugadores
- **THEN** su fila muestra "Survival", "play.example.com", "Java", estado Online y "3/20"

#### Scenario: Servidor offline
- **WHEN** un servidor está offline
- **THEN** su fila muestra estado Offline y "—" en jugadores

#### Scenario: Estado distinguible
- **WHEN** hay servidores en los cuatro estados
- **THEN** cada estado se muestra con su propio texto y color de indicador

#### Scenario: Servidor Java
- **WHEN** un servidor es de edición Java, esté online o no
- **THEN** su fila muestra "Java" junto a la dirección

#### Scenario: Servidor Bedrock
- **WHEN** un servidor es de edición Bedrock
- **THEN** su fila muestra "Bedrock" junto a la dirección

#### Scenario: Edición desconocida
- **WHEN** un servidor es de edición desconocida
- **THEN** su fila muestra el aviso "edición desconocida" junto a la dirección, y el aviso desaparece cuando la edición se detecta

#### Scenario: Fila interactiva
- **WHEN** el usuario pasa el puntero sobre una fila
- **THEN** la fila se resalta y un click abre su detalle
