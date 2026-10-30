## MODIFIED Requirements

### Requirement: Menú del icono
El click derecho sobre el icono SHALL abrir un menú con las entradas "Abrir mc-watch", "Actualizar ahora", un separador, "Arrancar con la sesión" (marcable), otro separador y "Salir". "Actualizar ahora" SHALL sondear todos los servidores sin esperar al siguiente ciclo. "Salir" SHALL terminar la app por completo, incluido el sondeo. El menú SHALL resaltar la opción bajo el puntero y responder a los clics también cuando la app se lanzó con doble clic desde el Explorador.

#### Scenario: Actualizar ahora
- **WHEN** el usuario elige "Actualizar ahora"
- **THEN** los servidores se sondean enseguida y el panel muestra "Actualizado hace…" reciente

#### Scenario: Salir
- **WHEN** el usuario elige "Salir"
- **THEN** el icono desaparece y el proceso termina

#### Scenario: Lanzada desde el Explorador
- **WHEN** el usuario lanzó `mc-watch.exe` con doble clic y hace click derecho en el icono
- **THEN** la opción bajo el puntero se resalta y elegir "Abrir mc-watch" abre el panel

## ADDED Requirements

### Requirement: Una sola instancia
Para una misma carpeta de configuración SHALL correr una sola instancia de la app. Si el usuario la lanza de nuevo mientras otra corre, la nueva SHALL mostrar el panel de la existente y terminar sin crear otro icono. Instancias con carpetas de configuración distintas SHALL poder convivir.

#### Scenario: Lanzar dos veces
- **WHEN** `mc-watch` ya está en la bandeja y el usuario vuelve a hacer doble clic en `mc-watch.exe`
- **THEN** se abre el panel de la instancia existente y no aparece un segundo icono

#### Scenario: Otra carpeta de configuración
- **WHEN** corre la instancia normal y el desarrollador lanza otra con `MC_WATCH_CONFIG_DIR` apuntando a otra carpeta
- **THEN** ambas corren, cada una con su icono
