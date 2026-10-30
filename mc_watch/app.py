"""Wires config, poller, tray and panel together."""

import logging
import threading
from pathlib import Path

import webview

from mc_watch import __version__
from mc_watch.autostart import Autostart
from mc_watch.config import Config, config_dir, config_path, load_config
from mc_watch.log import setup_logging
from mc_watch.models import Snapshot
from mc_watch.notify import Notifications
from mc_watch.poller import Poller
from mc_watch.servers import ServerManager
from mc_watch.settings import SettingsManager
from mc_watch.single_instance import Guard
from mc_watch.tray import Tray
from mc_watch.view import snapshot_payload
from mc_watch.window import Panel, Payload

log = logging.getLogger(__name__)


class App:
    def __init__(self, directory: Path | None = None, guard: Guard | None = None) -> None:
        self._guard = guard
        self.directory = directory or config_dir()
        setup_logging(self.directory)
        log.info("mc-watch %s", __version__)

        self.config: Config = load_config(self.directory)
        self._config_path = str(config_path(self.directory))
        self.poller = Poller(self.config.servers, self.config.poll_interval_secs)
        self.servers = ServerManager(self.directory, self.config, self.poller)
        self.notifications = Notifications(self.config.notifications, self._open_server)
        self.settings = SettingsManager(
            self.directory,
            self.config,
            self.poller,
            self.notifications,
            on_change=lambda: self.panel.push(self._payload(self.poller.snapshot())),
        )
        self.panel = Panel(
            lambda: self._payload(self.poller.snapshot()),
            add_server=self.servers.add_server,
            refresh=self.poller.refresh,
            rename_server=self.servers.rename_server,
            change_address=self.servers.change_address,
            remove_server=self.servers.remove_server,
            refresh_server=self.poller.refresh_server,
            save_settings=self.settings.save,
        )
        self.autostart = Autostart()
        self.tray = Tray(
            on_toggle=self.panel.toggle,
            on_open=self.panel.show,
            on_refresh=self.poller.refresh,
            on_quit=self.quit,
            on_autostart=self.toggle_autostart,
            autostart_on=self.autostart.is_enabled,
            autostart_available=self.autostart.available,
        )
        self.poller.subscribe(self.servers.on_snapshot)
        self.poller.subscribe(self._on_snapshot)
        self.poller.subscribe(self.notifications.on_snapshot)
        self._quit_lock = threading.Lock()
        self._quitting = False

    def _payload(self, snapshot: Snapshot) -> Payload:
        return snapshot_payload(
            snapshot,
            config_path=self._config_path,
            version=__version__,
            config_error=self.config.error,
            settings=self.settings.current,
        )

    def toggle_autostart(self) -> None:
        """Tray menu click. The registry is the truth: the menu re-reads it when it opens."""
        wanted = not self.autostart.is_enabled()
        try:
            self.autostart.set_enabled(wanted)
            log.info("Autostart %s", "activado" if wanted else "desactivado")
        except OSError as error:
            log.warning("No se pudo cambiar el autostart: %s", error)

    def _open_server(self, address: str | None) -> None:
        """Click on a notification. Runs on the notifications thread."""
        self.panel.open_server(address)

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        self.tray.update(snapshot)
        self.panel.push(self._payload(snapshot))

    def run(self) -> int:
        """Block until the app quits."""
        self.panel.create()
        try:
            # The GUI loop owns the main thread; `_start_background` runs once it is up.
            webview.start(self._start_background)
        finally:
            self.quit()
        log.info("mc-watch terminó")
        return 0

    def _start_background(self) -> None:
        self.tray.start()
        self.tray.update(self.poller.snapshot())
        self.poller.start()
        if self._guard is not None:
            self._guard.serve(self.panel.show)
        try:
            if self.autostart.refresh():
                log.info("Autostart actualizado a la ruta actual")
        except OSError as error:
            log.warning("No se pudo actualizar el autostart: %s", error)

    def quit(self) -> None:
        """Stop everything. Safe to call from any thread, more than once."""
        with self._quit_lock:
            if self._quitting:
                return
            self._quitting = True
        log.info("Saliendo")
        self.poller.stop()
        self.tray.stop()
        self.panel.destroy()
        if self._guard is not None:
            self._guard.close()
