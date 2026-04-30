import subprocess

import pytest

from swe_harness.docker_manager import CommandError, DockerManager


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


def _head_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()


DOCKER_AVAILABLE = _docker_available()
skip_no_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker unavailable")

# Integration tests clone from GitHub; they skip if Docker is unavailable
# but will also fail silently if the machine has no outbound HTTPS.
REPO_URL = "https://github.com/chiajung-wang/swe-harness"


@skip_no_docker
def test_start_exec_stop() -> None:
    manager = DockerManager()
    commit = _head_commit()

    container_id = manager.start(REPO_URL, commit)
    assert container_id  # non-empty string

    stdout, stderr = manager.exec("python --version")
    assert "3.11" in stdout or "3.11" in stderr

    manager.stop()


@skip_no_docker
def test_exec_raises_on_nonzero() -> None:
    manager = DockerManager()
    commit = _head_commit()
    manager.start(REPO_URL, commit)
    try:
        with pytest.raises(CommandError) as exc_info:
            manager.exec("exit 42")
        assert exc_info.value.exit_code == 42
    finally:
        manager.stop()


@skip_no_docker
def test_stop_is_idempotent() -> None:
    manager = DockerManager()
    commit = _head_commit()
    manager.start(REPO_URL, commit)
    manager.stop()
    manager.stop()  # must not raise


def test_exec_before_start_raises() -> None:
    manager = DockerManager()
    with pytest.raises(RuntimeError, match="call start\\(\\) first"):
        manager.exec("echo hi")


def test_stop_before_start_is_noop() -> None:
    manager = DockerManager()
    manager.stop()  # must not raise
