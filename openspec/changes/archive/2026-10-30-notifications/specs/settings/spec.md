## ADDED Requirements

### Requirement: Diálogo de ajustes
El botón de ajustes (engranaje) de la cabecera SHALL abrir un diálogo modal dentro del panel, sobre la lista, con título "Ajustes" y estos campos con los valores vigentes:
- "Notificaciones": un interruptor.
- "Segundos entre consultas": un número entero entre 30 y 3600.
- "Servidores visibles": un número entero entre 3 y 20.

El diálogo SHALL tener los botones Cancelar y Guardar. Cancelar, y Escape, SHALL cerrarlo sin cambiar nada. Mientras el diálogo está abierto, el resto del panel SHALL NOT ser interactivo. El panel SHALL tener al menos el alto necesario para mostrar el diálogo completo.

#### Scenario: Abrir
- **WHEN** las notificaciones están desactivadas, el intervalo es 60 y el usuario hace click en el engranaje
- **THEN** el diálogo muestra el interruptor apagado, "60" y los servidores visibles vigentes

#### Scenario: Cancelar
- **WHEN** el usuario cambia el intervalo a 120 y presiona Cancelar
- **THEN** el diálogo se cierra, el intervalo sigue en 60 y al reabrirlo muestra 60

### Requirement: Guardar ajustes
Guardar SHALL validar los valores; un valor fuera de rango o no entero SHALL mostrar un error junto a su campo sin guardar nada. Con valores válidos, el sistema SHALL escribir los tres ajustes en `config.toml`, cerrar el diálogo y aplicarlos sin reiniciar:
- las notificaciones se activan o desactivan desde ese momento;
- el próximo ciclo se programa con el intervalo nuevo, contado desde el inicio del ciclo anterior;
- la lista ajusta su alto a los servidores visibles.

Si la configuración no se puede escribir (archivo con error de sintaxis o error al guardar), el diálogo SHALL mostrar el error y SHALL NOT aplicar ningún ajuste. Si el archivo tenía un error de sintaxis al iniciar, el diálogo SHALL avisarlo al abrirse y Guardar SHALL estar deshabilitado.

#### Scenario: Activar notificaciones
- **WHEN** el usuario activa Notificaciones y guarda
- **THEN** `config.toml` tiene `notifications = true` y el próximo evento se notifica

#### Scenario: Intervalo inválido
- **WHEN** el usuario escribe 10 en "Segundos entre consultas" y guarda
- **THEN** el campo muestra "Entre 30 y 3600" y nada se guarda

#### Scenario: Acortar el intervalo
- **WHEN** el intervalo era 300, el último ciclo empezó hace 40 s y el usuario guarda 30
- **THEN** el siguiente ciclo empieza de inmediato y los posteriores cada 30 s

#### Scenario: Archivo roto
- **WHEN** `config.toml` tiene un error de sintaxis y el usuario abre el diálogo
- **THEN** el diálogo avisa del error con la ruta del archivo y Guardar está deshabilitado
