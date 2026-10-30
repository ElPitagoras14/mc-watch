## ADDED Requirements

### Requirement: Ajustes de notificaciones y lista
La configuración SHALL admitir una clave opcional `notifications` (booleano, `false` por defecto) y una clave opcional `max_visible_servers` (entero, 8 por defecto). Un `notifications` que no es booleano SHALL tratarse como `false`. Un `max_visible_servers` que no es entero SHALL tratarse como 8, y uno fuera de 3–20 SHALL llevarse al límite más cercano. Cada valor corregido SHALL registrarse como advertencia en el log.

#### Scenario: Sin ajustes
- **WHEN** el archivo no define `notifications` ni `max_visible_servers`
- **THEN** las notificaciones están desactivadas y la lista muestra hasta 8 servidores antes de hacer scroll

#### Scenario: Valor fuera de rango
- **WHEN** `max_visible_servers` vale 50
- **THEN** el valor efectivo es 20

## MODIFIED Requirements

### Requirement: Intervalo de sondeo
`poll_interval_secs` SHALL valer 60 por defecto. Un valor menor a 30 SHALL tratarse como 30 y uno mayor a 3600 SHALL tratarse como 3600.

#### Scenario: Sin intervalo configurado
- **WHEN** el archivo no define `poll_interval_secs`
- **THEN** el intervalo efectivo es 60 segundos

#### Scenario: Intervalo demasiado bajo
- **WHEN** `poll_interval_secs` vale 5
- **THEN** el intervalo efectivo es 30 segundos

#### Scenario: Intervalo demasiado alto
- **WHEN** `poll_interval_secs` vale 86400
- **THEN** el intervalo efectivo es 3600 segundos

### Requirement: Escritura de la configuración
Al escribir `config.toml`, el sistema SHALL conservar los comentarios, el orden y el formato de lo que ya había en el archivo, y SHALL cambiar solo lo necesario:
- agregar la entrada nueva al final;
- actualizar el `edition` o el `name` de una entrada existente;
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

#### Scenario: Quitar una entrada
- **WHEN** el usuario elimina el segundo de tres servidores
- **THEN** el archivo conserva la primera y la tercera entrada con sus comentarios, y la segunda desaparece por completo

#### Scenario: Guardar ajustes en un archivo con servidores
- **WHEN** el archivo solo tiene entradas `[[servers]]` y el usuario guarda los ajustes
- **THEN** las tres claves quedan antes de la primera entrada `[[servers]]` y las entradas no cambian
