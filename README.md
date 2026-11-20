# ELM-CH-AODV-EM — minimal research data release (v1.0)

Companion data to *Communication-Robust Multi-Sensor UAV Remote Sensing in Complex Environments: The ELM-CH-AODV-EM Hierarchical Routing Framework*.

## Scope

The **four** frozen analysis units are supplied as fully populated run-level CSV files. All numerical values are copied from previously audited archives, not regenerated or simulated for this release.

|Evidence block|File|Unit|Rows|
|-|-|-|-:|
|H300 primary, LOW/NOMINAL/STRESS|`data/H300\_144\_run\_level.csv`|scenario × seed × protocol|144|
|H600 robustness, LOW/NOMINAL|`data/H600\_96\_run\_level.csv`|scenario × seed × protocol|96|
|STEP 7A STRESS mechanism ablation|`data/STEP7A\_60\_ablation\_run\_level.csv`|seed × FULL/4 ablations|60|
|STEP 7.3C packet-pair observational replay|`data/STEP7\_3C\_48\_FRPDR\_run\_level.csv`|seed × protocol|48|

`statistics/` contains the corresponding previously frozen test-output CSVs. `metadata/` includes the H600 fingerprint-exception record, exploratory n=10 sensitivity, and the STEP 7.3C freeze/QA declarations. `scripts/verify\_minimal\_release.py` independently checks the main datasets and descriptive PDR/FRPDR summaries; it does **not** re-run MATLAB simulations.

## Recheck

Python 3.9+ with pandas is sufficient for verification:

```bash
python -m pip install -r requirements.txt
python scripts/verify\_minimal\_release.py
```

## Optional packet-trace reanalysis

The core package includes the STEP 7.3C derived run-level outputs and analysis code **but not the underlying 48 raw packet traces**. If the optional trace add-on is published in this same repository, follow `raw\_traces/README.md`, reconstruct the exact frozen `STEP7\_3C\_frozen\_input.zip`, and run:

```bash
python scripts/step7\_3c\_analysis\_v2.py raw\_traces/STEP7\_3C\_frozen\_input.zip results\_recomputed
```

The original archive SHA-256 is recorded in `metadata/STEP7\_3C\_freeze\_config.json`. An exact archive (not a repack) is needed because the analysis script enforces that digest. The optional traces consist of 48 paired H300 STRESS runs and auxiliary smoke/checkpoint artifacts; no raw optical or thermal images are present.

## Scientific boundaries and provenance

* H300: Twelve seed identifiers per scenario were used for four protocols. STRESS uses seeds 101–109 and 111–113; seed 110 was excluded, not relabeled. Two scenarioFingerprint exceptions were identified under STRESS: AODV at seed 107 and AOMDV at seed 111. Their fingerprints differ from those of the other protocols at the corresponding seeds. The exact identity of the paired stochastic inputs for these cases has not been independently established.
* H600: 72 scientifically reused rows (ELM-CH-AODV-EM/AODV/AODV-EM) and 24 current-native AOMDV rows. Their source identities differ. Two NOMINAL fingerprint exceptions (seed 102 AOMDV, seed 103 ELM) are explained by a controlled thread-sensitive checksum experiment on regenerated arrays, but historical bitwise input equality is **not independently established**. The exploratory n=10 analysis does not replace the frozen n=12 inference.
* STEP 7A: 12 frozen FULL rows + 48 ablation runs. NO\_DGPS was endpoint-identical to FULL, despite separate runtime evidence that gateway-scoring was executed.
* STEP 7.3C: paired 512-byte packets represent **network-conditioned edge-preprocessed RGB/thermal observation units**, not actual RGB/thermal images. FRPDR evaluates network-delay skew; it is **not** an image alignment or detector-accuracy metric.
* Full historical H600 MATLAB checkpoint collections, immutable scenario arrays, all STEP 7A MAT checkpoints and the complete MATLAB DES source/execution environment are **not included** in this minimal repository. Thus this repository does not substantiate full simulator-level reproducibility.
* MATLAB version reported in the article: R2022a. The protocol simulator and its baselines must be licensed/cleared for release separately, and are not implicitly distributed by this minimal data package.

## Publication details

Repository URL, exact release tag/commit and any DOI must be entered by the authors **after publication of this repository**. Confirm the right to release each dataset and specify an appropriate data/code license before changing this repository from private to public. Keep numerical data and their reported provenance unchanged.

