"""Bundled sources + explicit existing Python prerequisite, NOT a bundled runtime.

--check imports only dependency modules; it never imports/starts TollGate or reads
its state. Serving is used only by the native host, on its inherited listener.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import socket
import sys
from pathlib import Path


def check_runtime():
    if sys.version_info < (3, 11):  # noqa: UP036 - external runtime prerequisite
        raise RuntimeError("Python 3.11+ is required")
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
    import uvicorn  # noqa: F401

    return {
        "python": sys.version.split()[0],
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("fastapi", "uvicorn", "pydantic")
        },
    }


def main():
    prerequisites = check_runtime()
    if sys.argv[1:] == ["--check"]:
        print(json.dumps(prerequisites, sort_keys=True))
        return
    if sys.argv[1:] != ["--serve-inherited"]:
        raise SystemExit("Expected --check or --serve-inherited")
    # Do not take any browser-supplied path/port/command. fd 0 belongs to this
    # exact native Process invocation; verify it before importing the product.
    listener = socket.fromfd(0, socket.AF_INET, socket.SOCK_STREAM)
    host, port = listener.getsockname()
    if (
        host != "127.0.0.1"
        or port <= 0
        or listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM
    ):
        listener.close()
        raise RuntimeError("Native loopback listener required")
    # SO_ACCEPTCONN is not available via getsockopt on macOS. listen is
    # idempotent for the inherited TCP listener and never releases/rebinds it.
    listener.listen(128)
    nonce = os.environ["TOLLGATE_NATIVE_NONCE"]
    os.environ["HOST"], os.environ["PORT"] = host, str(port)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    import uvicorn

    from tollgate.server_v1 import app

    async def native_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/_native/ready":
            payload = json.dumps({"nonce": nonce, "pid": os.getpid()}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": payload})
        else:
            await app(scope, receive, send)

    config = uvicorn.Config(native_app, host=host, port=port, log_level="warning")
    try:
        uvicorn.Server(config).run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
