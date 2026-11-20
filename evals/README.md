# Evals

Cases for the eval harness of the `hardware-design` plugin
([claude-hardware-skills/evals](https://github.com/gabrielfrasantos/claude-hardware-skills/tree/main/evals)). The
harness is generic; what is specific to this board lives here.

| Case | Task | Anchors |
|---|---|---|
| `cases/placement.json` | place every non-anchor part on the board at the pinned commit | the connectors, the switch, the mounting and bracket holes, and the three vendor copies (D-037, D-039, D-040): this board locks nothing (D-045) |

The fixture is built from this repo's history at the case's commit (`git show`), so no board copies are committed.
The baseline is the owner's placement at that commit.

```bash
python3 <claude-hardware-skills>/evals/make_fixture.py evals/cases/placement.json    # fixture only, to open in KiCad
python3 <claude-hardware-skills>/evals/run.py evals --case placement --runs 1         # one run with, one without
```

Work directories go to `evals/work/` (gitignored); summaries to `evals/results/`.
