# PROTOTYPE: simulation domains

Throwaway notebooks for the decision ticket [Which geological units does the model distinguish?](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/5). They exist to *look at* the options before deciding. They are not the workflow itself.

| Notebook | What it does |
|---|---|
| `01_get_data.py` | Downloads GeoTOP (`strat`, `lithok`) for the model extent via `bromodels`, and the BRO CPTs via the BRO REST API, into `data/`. Reuses XMLs from a local `bedrock-experiments` checkout when it finds them. |
| `02_simulation_domains.py` | Groups GeoTOP voxels into simulation domains under five schemes (A: every unit · B: thin units pooled · C: B with the Eem cut at the CPT base · D: unit × lithology · E: lithology only). Shows CPT coverage per domain, a cross-section with qc traces, and qc/Rf distributions per domain. |

Run them from this folder. Each notebook declares its own dependencies, so the first command must run on a machine that can reach dinodata.nl and publiek.broservices.nl:

```sh
uvx marimo edit --sandbox 01_get_data.py
uvx marimo edit --sandbox 02_simulation_domains.py
```

Things to look at in 02:
- The **GeoTOP x/y convention** toggle. bromodels returns x/y as-is, but nlmod says they are cell corners. Watch whether the qc traces line up with the unit boundaries better with or without the 50 m shift.
- **Thin units** (NAWOVE, BX, NIBA, ANAWA) in scheme A. Check whether their CPT stats look like their own soil or like their neighbours', since a 0.5 m unit can easily be mis-sampled.
