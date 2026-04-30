## What to build

`eval/datasets/dev/` — 10 JSON manifests, each pinning a real SWE-bench Verified bug:

```json
{
  "instance_id": "<swebench-instance-id>",
  "repo_url": "https://github.com/...",
  "commit": "<40-char SHA>",
  "issue_url": "https://github.com/.../issues/<n>",
  "gold_test": "tests/path/to/test_file.py::test_function"
}
```

Commits must be pinned to the exact pre-fix state (reproducible). Stratify by difficulty: 3-4 easy, 3-4 medium, 2-3 hard.

## Acceptance criteria

- [ ] Exactly 10 manifest files under `eval/datasets/dev/`
- [ ] Each file validates against the schema above (all fields present, commit is 40-char hex)
- [ ] `repo_url` + `commit` can be cloned and checked out without error
- [ ] `gold_test` path exists in the repo at the pinned commit
- [ ] `eval/datasets/dev/README.md` lists instance IDs and difficulty tier

## Blocked by

None — can start immediately (requires human to select and verify bugs). **HITL.**
