## MODIFIED Requirements

### Requirement: Escritura de la configuración
Al escribir `config.toml`, el sistema SHALL conservar los comentarios, el orden y el formato de lo que ya había en el archivo, y SHALL cambiar solo lo necesario:
- agregar la entrada nueva al final;
- actualizar el `edition` o el `name` de una entrada existente;
- quitar una entrada completa.

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

#### Scenario: Quitar una entrada
- **WHEN** el usuario elimina el segundo de tres servidores
- **THEN** el archivo conserva la primera y la tercera entrada con sus comentarios, y la segunda desaparece por completo
