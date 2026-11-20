#!/usr/bin/env python3
"""Verify the four frozen run-level datasets and regenerate descriptive means.
No simulation is run. Requires Python >=3.9 and pandas.
"""
from pathlib import Path
import pandas as pd
import hashlib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "data/H300_144_run_level.csv": 144,
    "data/H600_96_run_level.csv": 96,
    "data/STEP7A_60_ablation_run_level.csv": 60,
    "data/STEP7_3C_48_FRPDR_run_level.csv": 48,
}

def verify_checksums():
    manifest = ROOT / "SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        sha, rel = line.split("  ",1)
        p=ROOT/rel
        assert p.exists(), f"Missing {rel}"
        actual=hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha==actual, f"Hash mismatch: {rel}"
    print("CHECKSUMS PASS")

def verify():
    verify_checksums()
    for rel,n in EXPECTED.items():
        df = pd.read_csv(ROOT/rel)
        assert len(df)==n,(rel,len(df),n)
        print(f"{rel}: {len(df)} rows PASS")
    h3=pd.read_csv(ROOT/'data/H300_144_run_level.csv')
    h6=pd.read_csv(ROOT/'data/H600_96_run_level.csv')
    ab=pd.read_csv(ROOT/'data/STEP7A_60_ablation_run_level.csv')
    fr=pd.read_csv(ROOT/'data/STEP7_3C_48_FRPDR_run_level.csv')
    assert set(h3['Scenario'])=={'LOW','NOMINAL','STRESS'}
    assert h3.groupby(['Scenario','Protocol']).size().eq(12).all()
    assert h6.groupby(['Scenario','Protocol']).size().eq(12).all()
    assert ab.groupby('Variant').size().eq(12).all()
    assert fr.groupby('protocol').size().eq(12).all()
    assert h3[['PDR','meanE2EDelay_s','NRL_P','NRL_B','energyPerDeliveredBit_J']].notna().all().all()
    assert h6[['PDR','meanE2EDelay_s','NRL_P','NRL_B','energyPerDeliveredBit_J']].notna().all().all()
    assert abs(fr[fr.protocol=='ELM_CH_AODV_EM'].FRPDR.mean()-0.8191360089186176)<1e-12
    print("\nH300 mean PDR by scenario/protocol")
    print(h3.groupby(['Scenario','Protocol'])['PDR'].mean().round(6).to_string())
    print("\nH600 mean PDR by scenario/protocol")
    print(h6.groupby(['Scenario','Protocol'])['PDR'].mean().round(6).to_string())
    print("\nSTEP 7A STRESS mean PDR by variant")
    print(ab.groupby('Variant')['PDR'].mean().round(6).to_string())
    print("\nSTEP 7.3C mean FRPDR by protocol")
    print(fr.groupby('protocol')['FRPDR'].mean().round(6).to_string())
    print("\nFROZEN RUN-LEVEL DATA QA: PASS")

if __name__=='__main__':verify()
