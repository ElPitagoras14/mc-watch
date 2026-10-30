## MODIFIED Requirements

### Requirement: Escritura de la configuración
Al escribir `config.toml`, el sistema SHALL conservar los comentarios, el orden y el formato de lo que ya había en el archivo, y SHALL cambiar solo lo necesario:
- agregar la entrada nueva al final;
- actualizar el `edition`, el `name` o el `address` de una entrada existente;
- quitar una entrada completa;
- actualizar o agregar las claves `notifications`, `poll_interval_secs` y `max_visible_servers`, en la parte superior del archivo, antes de las entradas `[[servers]]`.

Las entradas existentes SHALL identificarse por su `address`, sin distinguir mayúsculas de minúsculas. Si hay más de una con la misma dirección, SHALL modificarse la primera. El sistema SHALL partir del contenido actual del archivo en disco, de modo que no se pierdan cambios hechos a mano desde que la app inició. Si en ese momento el archivo tiene un error de sintaxis, el sistema SHALL abortar la escritura sin tocarlo. La escritura SHALL ser atómica: ante un fallo, el archivo SHALL quedar como estaba.

#### Scenario: Comentarios conservados
- **WHEN** el archivo tiene comentarios escritos a mano y el usuario agrega un servidor
- **THEN** el archivo resultante conserva esos comentarios y tiene la entrada nueva al final

#### Scenario: Archivo roto después de iniciar
- **WHEN** la app inició con un archivo válido, el usuario lo rompe a mano y luego agrega un servidor desde el panel
- **THEN** la app no escribe el archivo y el formulario informa el error

#### Scenario: Renombrar conserva el resto
- **WHEN** el usuario renombra el segundo de tres servidores
- **THEN** solo cambia el `name` de esa entrada y el resto del archivo, incluidos los comentarios, queda igual

#### Scenario: Cambiar la dirección conserva el resto
- **WHEN** el usuario cambia la dirección del segundo de tres servidores
- **THEN** solo cambian el `address` y el `edition` de esa entrada (y el `name`, si era igual a la dirección anterior), y el resto del archivo, incluidos los comentarios y el orden, queda igual

#### Scenario: Quitar una entrada
- **WHEN** el usuario elimina el segundo de tres servidores
- **THEN** el archivo conserva la primera y la tercera entrada con sus comentarios, y la segunda desaparece por completo

#### Scenario: Guardar ajustes en un archivo con servidores
- **WHEN** el archivo solo tiene entradas `[[servers]]` y el usuario guarda los ajustes
- **THEN** las tres claves quedan antes de la primera entrada `[[servers]]` y las entradas no cambian
