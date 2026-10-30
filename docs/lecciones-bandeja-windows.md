# Lecciones de la bandeja de Windows

Problemas de pystray y pywebview en Windows que ya se resolvieron en proyectos hermanos. Están documentados aquí para no redescubrirlos. Nada de esto está aplicado en `mc-watch` salvo que se indique.

## Menú del clic derecho sin resaltado (pr-watch v0.1.4, PR #15)

**Estado en mc-watch:** aplicado en el change `distribution`. `mc_watch/tray.py` sobrescribe `_on_notify` (`_WindowsIcon`) y fuerza el primer plano sobre `_menu_hwnd`, igual que pr-watch.

### Síntoma

El menú del clic derecho de la bandeja se dibuja, pero la opción bajo el ratón no se resalta y a veces el menú no responde a los clics. Solo pasa con el `.exe` lanzado con doble clic desde el Explorador. Desde una terminal funciona bien.

### Causa

Windows exige que la ventana dueña del menú (la que se pasa a `TrackPopupMenuEx`) sea la ventana de primer plano. Fallan tres cosas encadenadas:

1. pystray hace `SetForegroundWindow(_hwnd)`, pero abre el menú con `_menu_hwnd` como dueña (`pystray/_win32.py`, hacia las líneas 206 y 221). Son ventanas distintas.
2. `SetForegroundWindow` falla en silencio si el proceso no recibió la última entrada del usuario. Eso depende de cómo se lanzó la app: desde una terminal funciona, desde el Explorador no.
3. Aun forzándolo, el cambio de primer plano es **asíncrono**. Si el menú se abre antes de que la ventana sea realmente la activa, se dibuja sin resaltado. Un log de diagnóstico que agregaba unos milisegundos hacía que "funcionara", y eso delató la carrera.

### Solución

En `pr_watch/tray.py`, función `_force_foreground`, se sobrescribe `Icon._on_notify` (clase `WindowsIcon`) para hacer lo siguiente:

1. `AttachThreadInput(hilo_actual, hilo_del_primer_plano, True)`, para que el proceso pueda cambiar el primer plano.
2. `SetForegroundWindow(hwnd_del_menu)`, sobre `_menu_hwnd` y no sobre `_hwnd`.
3. Esperar en bucle, como máximo 0,5 s en pasos de 10 ms, hasta que `GetForegroundWindow() == hwnd_del_menu`.
4. Desenganchar con `AttachThreadInput(..., False)` en un `finally`.
5. Solo entonces llamar a `TrackPopupMenuEx(..., TPM_RETURNCMD)` y luego a `PostMessage(WM_NULL)` (KB135788).

El usuario lo verificó con el binario descargado del release v0.1.4 de pr-watch.

### Cómo depurarlo

- Registrar en el log `fg_antes`, `fg_despues` y `menu_hwnd` comparándolos con `GetForegroundWindow()`.
- Probar siempre lanzando la app con doble clic desde el Explorador, no desde una terminal.
- Si el primer plano es correcto y el menú sigue sin resaltar, el culpable es el DPI (sección siguiente).

## DPI alto: Per-Monitor-V2 (aplicado en mc-watch)

**Estado en mc-watch:** aplicado en el change `distribution` (`winutil.enable_per_monitor_dpi()`, llamado al inicio de `__main__.main()`). Con la escala al 125 % el primer plano ya era correcto (`fg_after == menu_hwnd`) y aun así el menú no resaltaba; activar este modo lo resolvió, y el panel siguió bien colocado.

El repositorio `jens-duttke/usage-monitor-for-claude` activa el modo Per-Monitor-V2 (`SetProcessDpiAwarenessContext(-4)`) antes de que pywebview llame a `SetProcessDPIAware()`. Esa llamada heredada rompe el resaltado nativo de los menús con DPI alto. En pr-watch no hizo falta.

Cambiar el modo de DPI altera cómo se interpretan las coordenadas, así que tras activarlo hay que comprobar la colocación del panel (`window.panel_geometry` y `winutil.dpi_scale`).
