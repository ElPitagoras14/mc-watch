# Monitor de servidores de Minecraft: viabilidad y nombre

Notas sobre qué información se puede obtener solo con la IP de un servidor, cómo implementarlo y opciones de nombre para el proyecto.

## Qué se puede obtener solo con la IP

Sí, casi todo se puede obtener solo con la IP o el host. La excepción es la lista de participantes.

Los servidores de Minecraft Java responden al **Server List Ping**, el mismo protocolo que usa el juego para llenar su lista de servidores. Es una conexión TCP al puerto 25565, o al que indique el registro DNS SRV `_minecraft._tcp.<host>` si el host lo define.

| Dato de tu diseño | ¿Disponible solo con la IP? |
| --- | --- |
| Status (online/offline) | Sí: si responde, está online. |
| Jugadores X/Y | Sí: online y máximo. |
| Versión, MOTD, icono | Sí. |
| Latencia | Sí: se mide con el propio ping. |
| Listado de participantes | Solo parcial (ver la siguiente sección). |

## El límite: la lista de jugadores

El Server List Ping devuelve solo una **muestra** de nombres, normalmente hasta 12. Muchos servidores la ocultan o la dejan vacía, y los grandes casi nunca la exponen.

Para la lista completa existen dos vías, pero ninguna sirve con solo la IP:

- **Query (UDP):** da la lista completa, pero el dueño del servidor debe activar `enable-query=true` y abrir el puerto UDP.
- **RCON:** exige contraseña de administrador, así que no es una opción para un monitor público.

Si el servidor es **Bedrock**, el protocolo es otro (RakNet sobre UDP, puerto 19132). Da jugadores X/Y y MOTD, pero no nombres.

## Qué implica para la pantalla de detalle

El dialog de "Participantes" debe tener tres estados:

- Lista de nombres, cuando el servidor los comparte.
- Muestra parcial, por ejemplo "5 de 23 jugadores".
- "Este servidor no comparte la lista de jugadores", cuando solo hay X/Y.

Si además tienes acceso a servidores con Query activado, puedes intentarlo primero y usar el Server List Ping como respaldo.

## Implementación

Como pr-watch está en Python, encaja la librería **`mcstatus`**. Hace el ping Java y Bedrock, resuelve los registros SRV y soporta Query, así que no hay que implementar el protocolo a mano.

Se puede reutilizar la arquitectura de pr-watch: bandeja del sistema, ventana con la UI en HTML/CSS y polling cada 30 s o más. Conviene poner timeouts cortos y distinguir "consultando" de "offline" para no mostrar falsas caídas.

## Nombres

Ideas siguiendo la línea de pr-watch y mr-watch:

- **`mc-watch`**: consistente con los otros proyectos, corto y claro.
- **Atalaya**: una atalaya es una torre de vigilancia, y suena bien en español.
- **Creeper-watch**: con guiño al juego.
- **Pingcraft**: refleja que usa ping.
- **Lobbywatch**: el lobby es donde se juntan los jugadores.

Recomendación: `mc-watch` por coherencia con los otros proyectos, o `Atalaya` si se busca algo con más personalidad.

Antes de decidir, revisar que el nombre esté libre en PyPI y GitHub. También conviene mirar las guías de marca de Mojang, que restringen usar "Minecraft" dentro del nombre de un producto; por eso las opciones evitan esa palabra.

## Siguientes pasos posibles

- Armar el esqueleto del cliente de consulta (ping, SRV y estados).
- Construir la UI de las dos pantallas: panel principal y detalle del servidor.
