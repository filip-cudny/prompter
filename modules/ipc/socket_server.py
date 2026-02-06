"""Unix domain socket server for receiving IPC commands in the daemon process."""

import json
import logging
import os
import socket
import threading

from PySide6.QtCore import QObject, Signal

from modules.utils.paths import get_user_config_dir

logger = logging.getLogger(__name__)

SOCKET_PATH = get_user_config_dir() / "promptheus.sock"

SUPPORTED_ACTIONS = {
    "open_context_menu",
    "execute_active_prompt",
    "speech_to_text_toggle",
    "set_context_value",
    "append_context_value",
    "clear_context",
}


class IPCSignals(QObject):
    action_requested = Signal(str, int, int)  # action_name, cursor_x, cursor_y


class IPCSocketServer:
    def __init__(self):
        self.signals = IPCSignals()
        self._server_socket: socket.socket | None = None
        self._listener_thread: threading.Thread | None = None
        self._running = False

    def start(self):
        self._cleanup_stale_socket()
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(SOCKET_PATH))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        self._running = True

        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        logger.info(f"IPC server listening on {SOCKET_PATH}")

    def stop(self):
        self._running = False

        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._listener_thread:
            self._listener_thread.join(timeout=3)
            self._listener_thread = None

        self._cleanup_stale_socket()
        logger.info("IPC server stopped")

    def _cleanup_stale_socket(self):
        try:
            if SOCKET_PATH.exists():
                os.unlink(SOCKET_PATH)
        except OSError:
            pass

    def _listen_loop(self):
        while self._running:
            try:
                client, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("IPC server socket error", exc_info=True)
                break

            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket):
        try:
            client.settimeout(5.0)
            data = client.recv(4096)
            if not data:
                return

            command = json.loads(data.decode("utf-8"))
            response = self._process_command(command)
            client.sendall(json.dumps(response).encode("utf-8"))
        except json.JSONDecodeError:
            self._send_error(client, "Invalid JSON")
        except socket.timeout:
            self._send_error(client, "Timeout reading command")
        except Exception:
            logger.error("Error handling IPC client", exc_info=True)
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _process_command(self, command: dict) -> dict:
        action = command.get("action")
        if not action:
            return {"status": "error", "message": "Missing 'action' field"}
        if action not in SUPPORTED_ACTIONS:
            return {"status": "error", "message": f"Unknown action: {action}"}

        x = int(command.get("x", 0))
        y = int(command.get("y", 0))

        self.signals.action_requested.emit(action, x, y)
        return {"status": "ok"}

    def _send_error(self, client: socket.socket, message: str):
        try:
            client.sendall(json.dumps({"status": "error", "message": message}).encode("utf-8"))
        except OSError:
            pass
