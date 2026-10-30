## Context

`probe._java` decide si una respuesta es de un servidor dormido con `_is_asleep(protocol, version_name)`, que solo mira el protocolo `-1` y la versión (la señal de Aternos). lazymc, mientras el servidor real está apagado, responde el status él mismo con la versión y el protocolo configurados (o los que cacheó del servidor), 0 jugadores y uno de sus MOTD por defecto:

- `sleeping`: "☠ Server is sleeping\n§2☻ Join to start it up"
- `starting`: "§2☻ Server is starting...\n§7⌛ Please wait..."
- `stopping`: "☠ Server going to sleep...\n⌛ Please wait..."

Cuando el servidor real está encendido, lazymc reenvía el status del servidor, así que la respuesta es la normal. Comprobado contra `192.168.1.100:25555`: protocolo 777, versión "26.3", 0/0 y el MOTD `sleeping`.

## Goals / Non-Goals

**Goals:**
- Que un lazymc dormido, arrancando o apagándose produzca `ProbeAsleep`, sin tocar la regla de Aternos.

**Non-Goals:**
- Detectar lazymc por otra vía (puerto, latencia, jugadores máximos en 0).

## Decisions

### D1 - Detectar por el texto plano del MOTD

`_is_asleep` recibe también el MOTD y busca las tres frases en el texto plano (`casefold`, sin códigos `§`). El texto plano se obtiene uniendo el texto de los segmentos de `_motd_segments`, o con `Motd.to_plain()` de mcstatus; se usa el que ya deja fuera colores y formato, sea JSON o con `§`.

Alternativas descartadas:
- **Jugadores máximos en 0**: lazymc pone el máximo cacheado del servidor si lo conoce, y un servidor real puede anunciar 0.
- **Solo "sleeping" en el MOTD**: dejaría el estado "arrancando" como online durante el minuto que tarda el servidor en subir, y daría falsos positivos con MOTD como "Sleeping Dragon SMP". Las frases completas de lazymc son más específicas.

### D2 - "Arrancando" y "apagándose" cuentan como dormido

En los dos el servidor real no acepta jugadores todavía (o ya no). Un estado propio añadiría UI y payload para una ventana de segundos; dormido → online en cuanto el servidor real responde es suficiente.

## Risks / Trade-offs

- [lazymc con MOTD personalizado o `from_server = true` no se detecta y sigue saliendo online] → Documentado como non-goal; el usuario puede dejar los MOTD por defecto.
- [Un servidor real cuyo MOTD contenga literalmente "server is starting"] → Improbable; se acepta. Mostrarlo como dormido es reversible en el siguiente ciclo en que el MOTD cambie.
