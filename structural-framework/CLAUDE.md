# Project rules for Claude Code

- `SPEC.md` is the source of truth. Propose spec changes before implementing behavior that differs from it.
  Where the spec is silent and a default had to be chosen, it is listed in `docs/spec_gaps.md`. Add new ones there.
- Never use data unavailable at the scoring date. Every ingest function returns a `published` date for each
  observation (see `src/sf/ingest/base.py`).
- No hard-coded parameters. Everything lives in `config/` and is validated by pydantic (`src/sf/config.py`).
- Every config change and every judgment score gets an entry in `config/changelog.yaml`.
- Snapshots are append-only. Never rewrite history. `sf.snapshot.write_snapshot` refuses to overwrite.
- Every new metric needs: a source, a construction, a direction, a test, and an IC report before it gets a
  nonzero weight. Metrics added beyond SPEC.md §4 start with `weight: 0` until their IC report passes (§9.1).
- Prefer simple, readable code over cleverness. Explain results in plain English.

## Commands

```bash
pip install -e ".[dashboard]"         # from structural-framework/
python -m pytest -q                   # offline tests on toy data
python -m sf ingest                   # FRED + prices -> data/raw, data/processed
python -m sf run --date 2026-10-08    # score one date, write snapshots/2026-10-08.json
python -m sf history --start 2005-01-31   # monthly score history -> data/processed/history.parquet
python -m sf backtest                 # IC, regime and portfolio reports -> reports/
streamlit run src/sf/dashboard/app.py
```
