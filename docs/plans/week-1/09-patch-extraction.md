# Patch Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the Generator succeeds, run `git diff HEAD` inside the Docker container and write the output to `runs/<run_id>/patch.diff`.

**Architecture:** Add a `_extract_patch()` helper to `orchestrator.py` that calls `docker.exec("git diff HEAD")` and writes stdout to `run_dir / "patch.diff"`. Call it in `run()` immediately after `generator.run()` returns without exception. Extraction failure must never change a passing verdict — log and continue.

**Tech Stack:** Python stdlib (`pathlib`), existing `DockerManager.exec()`, `CommandError`.

---

### Task 1: Test and implement `_extract_patch()`

**Files:**
- Modify: `src/swe_harness/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test — patch written on success**

Add to `tests/test_orchestrator.py`:

```python
def test_run_writes_patch_diff_on_pass(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    mock_generator.run.return_value = None
    mock_docker.exec.return_value = ("--- a/src/swe_harness/budget.py\n+++ b\n@@ -38 +38 @@\n-    if self._spent > self.limit_usd:\n+    if self._spent >= self.limit_usd:\n", "")

    orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    patch_files = list(tmp_path.glob("*/patch.diff"))
    assert len(patch_files) == 1
    assert ">=" in patch_files[0].read_text()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_orchestrator.py::test_run_writes_patch_diff_on_pass -v
```

Expected: `FAILED` — no `patch.diff` written yet.

- [ ] **Step 3: Write the failing test — patch NOT written on fail**

Add to `tests/test_orchestrator.py`:

```python
def test_run_no_patch_diff_on_fail(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    from swe_harness.agents.generator import StallDetected
    mock_generator.run.side_effect = StallDetected("no progress")

    orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    patch_files = list(tmp_path.glob("*/patch.diff"))
    assert len(patch_files) == 0
```

- [ ] **Step 4: Run both new tests to verify both fail**

```
uv run pytest tests/test_orchestrator.py::test_run_writes_patch_diff_on_pass tests/test_orchestrator.py::test_run_no_patch_diff_on_fail -v
```

Expected: both `FAILED`.

- [ ] **Step 5: Implement `_extract_patch()` in `orchestrator.py`**

Add after the `_repo_url_from_issue` function:

```python
def _extract_patch(docker: DockerManager, run_dir: Path) -> None:
    try:
        diff, _ = docker.exec("git diff HEAD")
    except Exception:
        logger.warning("run_dir=%s failed to extract patch", run_dir.name)
        return
    if not diff.strip():
        logger.warning("run_dir=%s patch is empty after pass", run_dir.name)
        return
    (run_dir / "patch.diff").write_text(diff, encoding="utf-8")
```

- [ ] **Step 6: Call `_extract_patch()` on pass in `run()`**

In `orchestrator.py`, change the success block from:

```python
            generator.run()
            verdict = "pass"
            reporter("◆ Repro passed — done")
```

to:

```python
            generator.run()
            verdict = "pass"
            _extract_patch(docker, run_dir)
            reporter("◆ Repro passed — done")
```

- [ ] **Step 7: Run all new tests to verify both pass**

```
uv run pytest tests/test_orchestrator.py::test_run_writes_patch_diff_on_pass tests/test_orchestrator.py::test_run_no_patch_diff_on_fail -v
```

Expected: both `PASSED`.

- [ ] **Step 8: Run full test suite**

```
uv run pytest
```

Expected: all green. Fix any regressions before continuing.

- [ ] **Step 9: Commit**

```bash
git add src/swe_harness/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): extract and save patch.diff on generator pass"
```
