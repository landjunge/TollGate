"""Exercise shipped Swift receipt/IPC/origin code, never a Python reimplementation."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native/macos"


@pytest.fixture(scope="module")
def native_fixture(tmp_path_factory):
    if not shutil.which("swiftc"):
        if sys.platform == "darwin":
            pytest.fail("macOS acceptance requires swiftc")
        pytest.skip("Swift fixture needs swiftc; Cocoa host is macOS-only")
    binary = tmp_path_factory.mktemp("native-fixture") / "fixture"
    sources = [
        NATIVE / "FamilySwitch.swift",
        ROOT / "tests/fixtures/native_family/Fixture.swift",
    ]
    if sys.platform == "darwin":
        sources.append(NATIVE / "NativeBackend.swift")
    result = subprocess.run(
        ["swiftc", *map(str, sources), "-o", str(binary)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return binary


def invoke(binary, *arguments, data=b""):
    return (
        subprocess.run(
            [str(binary), *map(str, arguments)],
            input=data,
            capture_output=True,
            check=True,
            timeout=15,
        )
        .stdout.decode()
        .strip()
    )


GOOD = {
    "success": True,
    "active_product": "threaddesk",
    "visible_family_windows": 1,
    "actual_outer_bounds": {"x": -10, "y": 0, "width": 1360, "height": 780},
}


@pytest.mark.parametrize(
    "change,status,expected",
    [
        ({}, 0, "focused"),
        ({}, 2, "uncertain"),
        ({"success": 1}, 0, "uncertain"),
        ({"success": "true"}, 0, "uncertain"),
        ({"active_product": "tollgate"}, 0, "uncertain"),
        ({"execution_outcome_unknown": True}, 0, "uncertain"),
        ({"execution_outcome_unknown": 0}, 0, "uncertain"),
        ({"error": {"code": "busy"}}, 0, "uncertain"),
        ({"visible_family_windows": True}, 0, "uncertain"),
        ({"visible_family_windows": 2}, 0, "uncertain"),
        ({"visible_family_windows": 1.0}, 0, "uncertain"),
        ({"actual_outer_bounds": {}}, 0, "uncertain"),
        (
            {"actual_outer_bounds": {"x": True, "y": 0, "width": 1, "height": 1}},
            0,
            "uncertain",
        ),
        (
            {"actual_outer_bounds": {"x": 0, "y": 0, "width": 0, "height": 1}},
            0,
            "uncertain",
        ),
        (
            {
                "success": False,
                "execution_outcome_unknown": False,
                "error": {"code": "denied"},
            },
            2,
            "failed",
        ),
        ({"success": False, "execution_outcome_unknown": False}, 2, "uncertain"),
        (
            {
                "success": False,
                "execution_outcome_unknown": False,
                "error": {"code": "denied"},
            },
            0,
            "uncertain",
        ),
        (
            {
                "success": False,
                "execution_outcome_unknown": True,
                "error": {"code": "denied"},
            },
            3,
            "uncertain",
        ),
    ],
)
def test_real_swift_receipt(native_fixture, change, status, expected):
    assert (
        invoke(
            native_fixture,
            "receipt",
            "threaddesk",
            status,
            data=json.dumps({**GOOD, **change}).encode(),
        )
        == expected
    )


@pytest.mark.parametrize("data", [b"[]", b"not json", b"{}", b"{" + b"x" * 65536])
def test_malformed_receipts_remain_unknown(native_fixture, data):
    assert invoke(native_fixture, "receipt", "threaddesk", 0, data=data) == "uncertain"


def test_native_ipc_drains_both_pipes_and_preserves_result(native_fixture):
    code = "import os; os.write(2,b'e'*50000); os.write(1,b'x'*50000)"
    value = json.loads(invoke(native_fixture, "ipc", 3, sys.executable, "-c", code))
    assert value == {"confirmed": True, "status": 0, "text": "x" * 50000}


def test_native_ipc_bounds_output_and_timeout_without_replay(native_fixture):
    for code, timeout in [
        ("import os; os.write(1,b'x'*100000)", 2),
        ("import os,time; print(os.getpid(),flush=True); time.sleep(10)", 1),
        (
            "import os,time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(10)",
            1,
        ),
    ]:
        value = json.loads(
            invoke(native_fixture, "ipc", timeout, sys.executable, "-c", code)
        )
        assert value["confirmed"] is False
        if value["text"].strip().isdigit():
            with pytest.raises(ProcessLookupError):
                os.kill(int(value["text"].strip()), 0)


def test_native_ipc_does_not_wait_for_descendant_pipe_eof(
    native_fixture, tmp_path, capsys
):
    # Keep the existing 1s IPC deadline and 2s pipe holder. The child publishes
    # readiness before the leader writes a real receipt and exits. Thus UNKNOWN
    # cannot be justified by failing to start the interpreter or losing output.
    ready = tmp_path / "holder.json"
    code = """import os,time,json,pathlib,sys
leader=os.getpid()
pid=os.fork()
if pid==0:
    marker=pathlib.Path(sys.argv[1]); pending=marker.with_suffix('.pending')
    pending.write_text(json.dumps({'leader':leader,'holder':os.getpid()})); pending.replace(marker)
    time.sleep(2); os._exit(0)
while not pathlib.Path(sys.argv[1]).exists(): time.sleep(.001)
print(sys.argv[2],flush=True)
os._exit(0)
"""
    start = time.monotonic()
    value = json.loads(
        invoke(
            native_fixture,
            "ipc-diagnostic",
            1,
            sys.executable,
            "-c",
            code,
            ready,
            json.dumps(GOOD),
        )
    )
    diagnostic = {
        "platform": sys.platform,
        "receipt": value,
        "wall_ms": (time.monotonic() - start) * 1000,
    }
    assert ready.is_file(), diagnostic
    # Observe only this fresh fixture leader, never argv, stores or other agents.
    if sys.platform == "linux":
        leader = json.loads(ready.read_text())["leader"]
        try:
            state = next(
                line
                for line in Path(f"/proc/{leader}/status").read_text().splitlines()
                if line.startswith("State:")
            )
        except FileNotFoundError:
            state = "absent"
        diagnostic["leader_kernel_state"] = state
        assert state == "absent" or state.split()[1] in {"Z", "X"}, diagnostic
    # Emit the full synthetic receipt even when pytest captures passing tests.
    with capsys.disabled():
        print(
            "Native EOF diagnostic: " + json.dumps(diagnostic, sort_keys=True),
            flush=True,
        )
    assert json.loads(value["text"]) == GOOD, diagnostic
    # Native completion must occur while the holder still retains its pipe.
    assert value["elapsed_ms"] < 2000, diagnostic
    if sys.platform == "linux" and value["confirmed"] is False:
        # corelibs Foundation may keep isRunning true until descendant EOF.
        # A deadline without confirmed exit is UNKNOWN, never a focused result.
        assert 1000 <= value["elapsed_ms"] < 2000, diagnostic
        assert value["status"] in {-999, 0}, diagnostic
    else:
        # macOS MUST still confirm the positive EOF case. No skip or relaxation.
        assert value["confirmed"] is True and value["status"] == 0, diagnostic


def test_main_actor_remains_responsive_and_unknown_stays_blocked(native_fixture):
    assert (
        invoke(native_fixture, "responsive", sys.executable)
        == "responsive late_receipt next_user_switch unknown_no_replay"
    )


def test_native_origin_callback_and_fixed_arguments(native_fixture):
    assert invoke(native_fixture, "origin") == "origin frame port callback argv"


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin listener handoff")
def test_actual_foundation_listener_handoff(native_fixture):
    assert (
        invoke(native_fixture, "listener", sys.executable) == "inherited_owned_listener"
    )


def test_runtime_preflight_does_not_start_product_or_write_state(tmp_path):
    state = tmp_path / "unused-state"
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(NATIVE / "backend_host.py"), "--check"],
        env={**os.environ, "TOLLGATE_HOME": str(state)},
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert set(json.loads(result.stdout)["dependencies"]) == {
        "fastapi",
        "uvicorn",
        "pydantic",
    }
    assert not state.exists()


def test_builder_preserves_existing_candidate_and_refuses_production_paths(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "build_candidate", NATIVE / "build_candidate.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    old = tmp_path / "TollGate.app"
    old.mkdir()
    marker = old / "keep"
    marker.write_text("original candidate")
    with pytest.raises(ValueError, match="Refusing to replace"):
        builder.output_paths(old, tmp_path / "proof.json")
    assert marker.read_text() == "original candidate"
    with pytest.raises(ValueError, match="Production Applications"):
        builder.output_paths(
            Path("/Applications/TollGate.app"), tmp_path / "proof.json"
        )


def test_backend_bootstrap_passes_its_listener_and_preserves_asgi(monkeypatch):
    """Run the bootstrap's real serve wiring with fake ASGI/server, no product start."""
    import asyncio
    import socket
    import types

    import uvicorn

    spec = importlib.util.spec_from_file_location(
        "backend_host", NATIVE / "backend_host.py"
    )
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        address = held.getsockname()
        fromfd = socket.fromfd

        def inherited(fd, family, kind):
            assert fd == 0 and family == socket.AF_INET and kind == socket.SOCK_STREAM
            return fromfd(held.fileno(), family, kind)

        delegated = []

        async def app(scope, receive, send):
            delegated.append(scope["path"])

        class Server:
            def __init__(self, config):
                self.config = config

            def run(self, *, sockets):
                assert len(sockets) == 1 and sockets[0].getsockname() == address
                assert self.config.host == address[0] and self.config.port == address[1]
                messages = []

                async def send(message):
                    messages.append(message)

                async def probe():
                    await self.config.app(
                        {"type": "http", "path": "/_native/ready"}, None, send
                    )
                    await self.config.app(
                        {"type": "http", "path": "/dashboard"}, None, send
                    )

                asyncio.run(probe())
                assert messages[0]["status"] == 200
                assert json.loads(messages[1]["body"]) == {
                    "nonce": "fresh-fixture",
                    "pid": os.getpid(),
                }

        monkeypatch.setattr(socket, "fromfd", inherited)
        monkeypatch.setattr(uvicorn, "Server", Server)
        monkeypatch.setitem(
            sys.modules, "tollgate.server_v1", types.SimpleNamespace(app=app)
        )
        monkeypatch.setattr(sys, "argv", ["backend_host.py", "--serve-inherited"])
        monkeypatch.setattr(sys, "path", list(sys.path))
        monkeypatch.setenv("TOLLGATE_NATIVE_NONCE", "fresh-fixture")
        bootstrap.main()
        assert delegated == ["/dashboard"]
