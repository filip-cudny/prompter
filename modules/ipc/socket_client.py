"""Unix domain socket client for sending IPC commands to the running daemon."""

import json
import socket
import sys

from modules.utils.paths import get_user_config_dir

SOCKET_PATH = get_user_config_dir() / "promptheus.sock"
TIMEOUT_SECONDS = 2


def send_ipc_command(action: str, cursor_pos: tuple[int, int] | None = None) -> bool:
    command = {"action": action}
    if cursor_pos:
        command["x"] = cursor_pos[0]
        command["y"] = cursor_pos[1]

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(TIMEOUT_SECONDS)
        client.connect(str(SOCKET_PATH))
        client.sendall(json.dumps(command).encode("utf-8"))

        data = client.recv(4096)
        response = json.loads(data.decode("utf-8"))

        if response.get("status") == "ok":
            return True

        print(f"Error: {response.get('message', 'Unknown error')}", file=sys.stderr)
        return False

    except FileNotFoundError:
        print(
            "Promptheus is not running. Start it first, then use CLI commands.",
            file=sys.stderr,
        )
        return False
    except ConnectionRefusedError:
        print(
            "Promptheus is not responding. Try restarting it.",
            file=sys.stderr,
        )
        return False
    except socket.timeout:
        print("Timed out waiting for Promptheus to respond.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"IPC error: {e}", file=sys.stderr)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass
