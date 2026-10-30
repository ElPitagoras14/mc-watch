## Purpose

Definir cómo se empaqueta `mc-watch` como ejecutable portable de Windows y cómo se publica cada versión como release de GitHub.

## ADDED Requirements

### Requirement: Ejecutable portable
El proyecto SHALL poder generar, con un solo comando, un ejecutable de Windows de un único archivo que no requiere Python ni instalador. El ejecutable SHALL abrirse sin ventana de consola, llevar un icono propio y declarar en sus propiedades el nombre del producto y la versión del proyecto. La interfaz del panel SHALL viajar dentro del ejecutable.

#### Scenario: Construir
- **WHEN** el desarrollador ejecuta `uv run build.py` en Windows
- **THEN** se genera `dist/mc-watch.exe` y el comando informa su ruta y tamaño

#### Scenario: Ejecutar en una máquina sin Python
- **WHEN** el usuario hace doble clic en `mc-watch.exe` en un Windows sin Python
- **THEN** aparece el icono en la bandeja, sin consola, y el panel abre con la lista de servidores

#### Scenario: Propiedades del archivo
- **WHEN** el usuario abre Propiedades → Detalles de `mc-watch.exe`
- **THEN** ve "mc-watch" como producto y la versión del proyecto

### Requirement: Versión única
La versión SHALL declararse en `pyproject.toml` y en el paquete, y ambas SHALL coincidir con la forma `MAJOR.MINOR.PATCH`. El pipeline de release SHALL fallar sin publicar nada si no coinciden o no tienen esa forma.

#### Scenario: Versiones distintas
- **WHEN** `pyproject.toml` dice `0.2.0` y el paquete dice `0.1.0`
- **THEN** el pipeline falla en su primer paso con un mensaje que nombra ambas versiones

### Requirement: Release automático
En cada push a `main`, el pipeline SHALL publicar un release solo si todavía no existe el tag `v<versión>`. Antes de publicar SHALL pasar los tests, el lint y el chequeo de tipos. El release SHALL crear el tag `v<versión>` y adjuntar `mc-watch-<versión>-windows.exe`, con notas que listan los commits desde el tag anterior. Si el tag ya existe, el pipeline SHALL terminar sin construir ni publicar.

#### Scenario: Versión nueva
- **WHEN** se fusiona en `main` un commit con una versión sin tag
- **THEN** aparece el release `v<versión>` con `mc-watch-<versión>-windows.exe` adjunto

#### Scenario: Versión ya publicada
- **WHEN** se fusiona en `main` un commit sin subir la versión
- **THEN** el pipeline termina tras comprobar la versión y no publica nada

#### Scenario: Tests en rojo
- **WHEN** hay una versión nueva pero un test falla
- **THEN** no se crea el tag ni el release
