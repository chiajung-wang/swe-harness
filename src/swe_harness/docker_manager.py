from __future__ import annotations

import docker
import docker.errors
from docker.models.containers import Container

_IMAGE = "python:3.11-slim"


class CommandError(Exception):
    """Raised when a container command exits with non-zero status."""

    def __init__(self, cmd: str, exit_code: int, stdout: str, stderr: str) -> None:
        self.cmd = cmd
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command exited {exit_code}: {cmd!r}\nstderr: {stderr}")


class DockerManager:
    """Manages a single Docker container for sandboxed code execution.

    The container is started once via start() and reused across exec() calls.
    Teardown is the caller's responsibility — call stop() when done.
    Network isolation beyond default bridge (full internet) is a future
    enhancement; proper PyPI-only enforcement requires custom iptables rules.
    """

    def __init__(self) -> None:
        # Client connected lazily in start() so instantiation doesn't
        # require a running daemon (enables unit tests without Docker).
        self._client: docker.DockerClient | None = None
        self._container: Container | None = None

    def start(self, repo_url: str, commit: str) -> str:
        """Start a container, install tooling, clone repo at commit.

        Returns the container ID. The container runs with a 4 GB RAM limit
        and keeps alive via `tail -f /dev/null` so exec() calls can follow.
        """
        self._client = docker.from_env()
        container: Container = self._client.containers.run(
            _IMAGE,
            command="tail -f /dev/null",
            detach=True,
            mem_limit="4g",
        )
        self._container = container

        # Split apt-get update and install into separate exec_run calls to
        # avoid shell metacharacters — setup args are lists, not shell strings.
        self._exec_setup(["apt-get", "update", "-qq"])
        self._exec_setup(["apt-get", "install", "-y", "git", "--quiet"])
        self._exec_setup(["pip", "install", "pytest", "tox", "--quiet"])

        # repo_url and commit are passed as list args — never interpolated
        # into a shell string — to prevent injection via crafted values.
        self._exec_setup(["git", "clone", "--quiet", repo_url, "/repo"])
        self._exec_setup(["git", "-C", "/repo", "checkout", commit])

        return str(container.id)

    def exec(self, cmd: str) -> tuple[str, str]:
        """Run a shell command inside /repo. Returns (stdout, stderr).

        Raises CommandError on non-zero exit code.
        The command is passed to bash -c, so normal shell syntax applies.
        """
        return self._exec_impl(["bash", "-c", cmd], workdir="/repo")

    def stop(self) -> None:
        """Stop and remove the container. Idempotent if already stopped."""
        if self._container is not None:
            try:
                self._container.stop(timeout=10)
                self._container.remove()
            except docker.errors.NotFound:
                pass  # Container already removed; treat as success
            self._container = None
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_container(self) -> Container:
        if self._container is None:
            raise RuntimeError("Container not started; call start() first")
        return self._container

    def _exec_setup(self, args: list[str]) -> None:
        """Run a command during start() setup — args list, no shell, no workdir."""
        self._exec_impl(args, workdir=None)

    def _exec_impl(self, args: list[str], workdir: str | None) -> tuple[str, str]:
        container = self._require_container()
        result = container.exec_run(args, workdir=workdir, demux=True)

        # exec_run with demux=True returns Tuple[bytes|None, bytes|None];
        # isinstance guards satisfy mypy's union type for the output field.
        output = result.output
        if isinstance(output, tuple):
            stdout = (output[0] or b"").decode()
            stderr = (output[1] or b"").decode()
        elif isinstance(output, bytes):
            stdout = output.decode()
            stderr = ""
        else:
            stdout = ""
            stderr = ""

        # exit_code is typed as int|None by the docker SDK stubs
        exit_code: int = result.exit_code if result.exit_code is not None else -1
        if exit_code != 0:
            raise CommandError(cmd=" ".join(args), exit_code=exit_code, stdout=stdout, stderr=stderr)
        return stdout, stderr
