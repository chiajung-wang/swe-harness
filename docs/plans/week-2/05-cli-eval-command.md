## What to build

Add `swe-harness eval dev` subcommand to `src/swe_harness/cli.py`:

- Reads all manifests from `eval/datasets/dev/`
- Calls `orchestrator.run(issue_url, config=config)` per instance
- Sets `eval_set="dev"` and `instance_id` on each `RunRecord`
- Aggregates results into `eval/results/dev-<ts>.json`:
  ```json
  { "config": "two_agent", "n": 10, "pass_at_1": 0.4, "runs": [...] }
  ```
- Rich progress bar (one row per instance, live status)

## Acceptance criteria

- [ ] `swe-harness eval dev` runs all 10 instances sequentially
- [ ] `--config` flag accepted (default `"two_agent"`); passes through to orchestrator
- [ ] Results file written to `eval/results/dev-<ts>.json` with `pass_at_1` field
- [ ] Each failed instance logged with reason (exception type, `budget_exceeded`, `stalled`)
- [ ] `pytest` passes (fixture mocking `orchestrator.run`)

## Blocked by

- 02-orchestrator-two-agent
- 03-dev-dataset
- 04-db-eval-columns
