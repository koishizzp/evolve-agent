# EvolvePro Param Profiles

These profiles match the `scripts/exp/*.py` layout you listed under your EvolvePro checkout.

Usage:

```bash
python main.py evolvepro examples/example_input.fasta \
  --task "optimize with EvolvePro" \
  --activity-csv /path/to/activity.csv \
  --params-json @examples/evolvepro_params/bxb1.json
```

For the `bxb1.py` / `mlv.py` / `t7_pol.py` experiment scripts you provided, `assay_name` is not required.
