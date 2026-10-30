# autostart Specification

## Purpose

Permitir que `mc-watch` arranque solo al iniciar la sesión de Windows, a elección del usuario y sin tocar nada fuera de su perfil.

## Requirements

### Requirement: Arrancar con la sesión desde la bandeja
El menú de la bandeja SHALL ofrecer la entrada marcable "Arrancar con la sesión". Activarla SHALL registrar el ejecutable para que arranque al iniciar la sesión del usuario actual, sin permisos de administrador. Desactivarla SHALL quitar ese registro. El autostart SHALL venir desactivado: la app nunca lo activa por su cuenta.

#### Scenario: Activar
- **WHEN** el autostart está desactivado y el usuario elige "Arrancar con la sesión"
- **THEN** la entrada queda marcada y, al reiniciar la sesión, `mc-watch` arranca solo

#### Scenario: Desactivar
- **WHEN** el autostart está activado y el usuario elige "Arrancar con la sesión"
- **THEN** la entrada queda sin marcar y al reiniciar la sesión `mc-watch` no arranca

#### Scenario: Primer arranque
- **WHEN** el usuario ejecuta `mc-watch` por primera vez
- **THEN** "Arrancar con la sesión" aparece sin marcar y no hay nada registrado

### Requirement: Solo en el ejecutable
Cuando la app corre desde el código fuente, "Arrancar con la sesión" SHALL mostrarse deshabilitada, porque registraría un intérprete y un directorio de desarrollo.

#### Scenario: Desde el código fuente
- **WHEN** la app se lanzó con `uv run python -m mc_watch`
- **THEN** "Arrancar con la sesión" aparece deshabilitada y elegirla no es posible

### Requirement: El registro es la fuente de verdad
La marca de "Arrancar con la sesión" SHALL reflejar lo que hay registrado en Windows en el momento de abrir el menú, también si el usuario lo cambió por fuera de la app. Si cambiar el autostart falla, la app SHALL registrar el error en el log, seguir funcionando y mostrar la marca según el estado real.

#### Scenario: Borrado a mano
- **WHEN** el autostart estaba activado y el usuario lo quita desde el Administrador de tareas
- **THEN** al abrir el menú "Arrancar con la sesión" aparece sin marcar

#### Scenario: Fallo al escribir
- **WHEN** Windows rechaza el cambio
- **THEN** la app sigue funcionando y la marca muestra el estado que realmente hay registrado

### Requirement: Ruta actualizada al moverse
Al iniciar desde el ejecutable, si el autostart está activado y apunta a otra ruta, la app SHALL actualizarlo a la ruta actual. Si el autostart está desactivado, iniciar SHALL NOT crearlo.

#### Scenario: El ejecutable se movió
- **WHEN** el autostart estaba activado y el usuario movió `mc-watch.exe` a otra carpeta y lo lanzó desde ahí
- **THEN** el autostart queda apuntando a la nueva ruta, sin entradas duplicadas
