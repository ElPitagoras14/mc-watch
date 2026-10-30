# server-config Specification

## Purpose

Definir dónde vive y qué formato tiene la configuración de `mc-watch` (lista de servidores e intervalo de sondeo), y cómo se comporta la app cuando el archivo falta o es inválido.

## Requirements

### Requirement: Ubicación del archivo de configuración
El sistema SHALL leer la configuración desde `config.toml` dentro de `%APPDATA%\mc-watch`. Cuando la variable de entorno `MC_WATCH_CONFIG_DIR` esté definida, el sistema SHALL buscar `config.toml` en ese directorio en su lugar. En este change el sistema SHALL NOT escribir ni crear el archivo.

#### Scenario: Ubicación por defecto
- **WHEN** `MC_WATCH_CONFIG_DIR` no está definida
- **THEN** el sistema lee `%APPDATA%\mc-watch\config.toml`

#### Scenario: Directorio sobrescrito
- **WHEN** `MC_WATCH_CONFIG_DIR` vale `D:\tmp\mcw`
- **THEN** el sistema lee `D:\tmp\mcw\config.toml`

### Requirement: Formato de la configuración
La configuración SHALL admitir una clave opcional `poll_interval_secs` y una lista `[[servers]]`, donde cada servidor tiene `name` (texto visible) y `address` (`host` o `host:puerto`). El sistema SHALL mostrar los servidores en el mismo orden en que aparecen en el archivo.

#### Scenario: Archivo válido
- **WHEN** el archivo contiene dos entradas `[[servers]]` con `name` y `address`
- **THEN** el panel muestra ambos servidores en ese orden

### Requirement: Intervalo de sondeo
`poll_interval_secs` SHALL valer 60 por defecto. Un valor menor a 30 SHALL tratarse como 30.

#### Scenario: Sin intervalo configurado
- **WHEN** el archivo no define `poll_interval_secs`
- **THEN** el intervalo efectivo es 60 segundos

#### Scenario: Intervalo demasiado bajo
- **WHEN** `poll_interval_secs` vale 5
- **THEN** el intervalo efectivo es 30 segundos

### Requirement: Configuración ausente o inválida
Si el archivo no existe, el sistema SHALL iniciar sin servidores. Si el archivo tiene un error de sintaxis TOML, el sistema SHALL iniciar sin servidores y con valores por defecto, y SHALL NOT modificar el archivo. Una entrada de servidor sin `name` o sin `address`, o con un puerto fuera de 1–65535, SHALL ignorarse sin afectar a las demás entradas.

#### Scenario: Archivo inexistente
- **WHEN** no existe `config.toml`
- **THEN** la app inicia y el panel muestra el estado vacío

#### Scenario: Error de sintaxis
- **WHEN** `config.toml` contiene TOML inválido
- **THEN** la app inicia sin servidores y el archivo queda intacto

#### Scenario: Entrada incompleta
- **WHEN** una de tres entradas `[[servers]]` no tiene `address`
- **THEN** el panel muestra solo las otras dos
