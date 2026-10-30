## Context

Ver `proposal.md` (Why). El payload ya trae `edition` (`java`, `bedrock` o `unknown`) en cada servidor (`view.py`). La UI lo usa en dos sitios de `mc_watch/ui/app.js`:

- La fila, en el render de la lista: añade un `<span class="edition …">` junto a la dirección solo para `bedrock` y `unknown`. `styles.css` ya da a `.edition` el color atenuado y a `.edition.unknown` el ámbar.
- El detalle: `dFacts` junta con " · " la versión, la latencia y, solo si es Bedrock, "Bedrock".

El preview ya incluye servidores de las tres ediciones.

## Goals / Non-Goals

**Goals:**

- Que la edición se vea siempre, con el mismo formato en la fila y en el detalle.

**Non-Goals:**

- Cambios en Python o en el payload.

## Decisions

### D1 - Una sola función de etiqueta de edición

En `app.js` una función pequeña `editionLabel(edition)` devuelve "Java", "Bedrock" o "edición desconocida", y la usan la fila y el detalle. Así el texto no queda duplicado y un cuarto valor futuro se agrega en un solo sitio.

Alternativa descartada: mostrar solo la edición que no es la "normal" (el comportamiento actual). Es justo lo que impide confirmar que un servidor Java se detectó como Java.

### D2 - Fila: siempre el `<span>`, con la clase de la edición

La fila agrega siempre el `<span class="edition <edición>">` con " · " y la etiqueta. Java y Bedrock heredan el color atenuado de `.edition`; `unknown` conserva el ámbar. No se toca el CSS.

### D3 - Detalle: la edición va al final de `dFacts`, también offline

Se agrega la etiqueta como último elemento de `facts`, sin condición de estado: versión y latencia siguen apareciendo solo online, la edición siempre (como ya ocurría con "Bedrock"). Para `unknown` el detalle dice "edición desconocida" con el mismo texto que la fila.

## Risks / Trade-offs

- [Un poco más de ruido en cada fila, que antes quedaba limpia para Java] → Es texto atenuado en la misma línea que la dirección; si el ancho no alcanza, la dirección ya se recorta y su `title` conserva el texto completo.
