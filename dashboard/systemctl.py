import shlex
import subprocess
from dataclasses import dataclass

from .config import SSH_USER


LOCAL_HOSTS = {"localhost", "", "127.0.0.1"}
DEFAULT_TIMEOUT = 10


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _mock_backend():
    """Lazy import to avoid a circular reference at module load."""
    from . import mock

    if mock.mock_enabled():
        return mock.get_systemctl_backend()
    return None


def _build_command(host: str, systemctl_args: list[str]) -> list[str]:
    """Wrap a systemctl invocation for local or ssh execution."""
    if host in LOCAL_HOSTS:
        return systemctl_args

    remote = " ".join(shlex.quote(a) for a in systemctl_args)
    # Set XDG_RUNTIME_DIR so ``systemctl --user`` can find the user's dbus socket
    remote_cmd = f'XDG_RUNTIME_DIR="/run/user/$(id -u)" {remote}'
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{SSH_USER}@{host}",
        remote_cmd,
    ]


def _run(host: str, systemctl_args: list[str], timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
    cmd = _build_command(host, systemctl_args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            returncode=124,
            stdout=exc.stdout.decode() if exc.stdout else "",
            stderr=f"timeout after {timeout}s",
        )
    except FileNotFoundError as exc:
        return CommandResult(returncode=127, stdout="", stderr=str(exc))


def is_active(host: str, unit: str) -> str:
    """Return the ActiveState string (``active``, ``inactive``, ``failed``, ...)."""
    backend = _mock_backend()
    if backend is not None:
        return backend.is_active(host, unit)
    result = _run(host, ["systemctl", "--user", "--no-pager", "is-active", unit])
    # is-active returns non-zero when inactive/failed but still prints the state.
    return (result.stdout or result.stderr).strip() or "unknown"


def status_summary(host: str, unit: str) -> dict[str, str]:
    """Return a small dict of key properties for a unit."""
    backend = _mock_backend()
    if backend is not None:
        return backend.status_summary(host, unit)
    props = "ActiveState,SubState,LoadState,UnitFileState,ExecMainPID,ExecMainStartTimestamp"
    result = _run(
        host,
        ["systemctl", "--user", "--no-pager", "show", unit, f"--property={props}"],
    )
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            parsed[k] = v
    if not parsed and result.stderr:
        parsed["error"] = result.stderr.strip()
    return parsed

def systemctl(host: str, verb: str, unit: str) -> CommandResult:
    backend = _mock_backend()
    if backend is not None:
        return backend.systemctl(host, verb, unit)
    return _run(host, ["systemctl" "--user", "--no-pager", verb, unit])


def start(host: str, unit: str) -> CommandResult:
    return systemctl(host, "start", unit)


def stop(host: str, unit: str) -> CommandResult:
    return systemctl(host, "stop", unit)


def restart(host: str, unit: str) -> CommandResult:
    return systemctl(host, "restart", unit)


def tail_logs(host: str, unit: str, lines: int = 200) -> str:
    """Return the last ``lines`` of journal output for the unit."""
    backend = _mock_backend()
    if backend is not None:
        return backend.tail_logs(host, unit, lines=lines)
    result = _run(
        host,
        [
            "journalctl",
            "--user",
            "--no-pager",
            "--output=short-iso",
            "-u", unit,
            "-n", str(lines),
        ],
        timeout=15,
    )
    if result.ok:
        return result.stdout
    return f"[error {result.returncode}] {result.stderr or result.stdout}"
