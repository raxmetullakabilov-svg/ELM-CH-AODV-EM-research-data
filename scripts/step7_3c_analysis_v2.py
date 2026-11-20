from pathlib import Path
import io, json, hashlib, zipfile, shutil
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

EXPECTED_INPUT_SHA256 = '87701620fcf8bb994c4fdd7850dc8f54b58145d1f673cb1fbb407358b4ba23ac'
SEEDS = [101,102,103,104,105,106,107,108,109,111,112,113]
PROTOCOLS = ['ELM_CH_AODV_EM','AODV','AODV_EM','AOMDV']
BASELINES = ['AODV','AODV_EM','AOMDV']
DVALS = [0.1,0.2,0.5,1.0]
SVALS = [0.01,0.025,0.05,0.1]
PRIMARY_D = 0.2
PRIMARY_S = 0.05
EXPECTED_ROWS_PER_RUN = 59810
EXPECTED_FLOWS = 10
EXPECTED_PAIRS_PER_RUN = 29900
EXPECTED_UNPAIRED_PER_RUN = 10
EXPECTED_PAYLOAD = 512
EXPECTED_PAIR_GAP_S = 0.05

EXPECTED_PRIMARY = {
    'ELM_CH_AODV_EM': (0.8191360089186176,0.027994180411723087),
    'AODV': (0.6236510590858417,0.12716828337799752),
    'AODV_EM': (0.5678929765886288,0.12684687766261182),
    'AOMDV': (0.7131326644370123,0.09981219745335773),
}
EXPECTED_FRIEDMAN = (31.400000000000006,7.001728218503788e-07,0.8722222222222223)


def sha256_file(path, chunk=1024*1024):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def holm_adjust(pvals):
    pvals = np.asarray(pvals, dtype=float)
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m-rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(running, 1.0)
    return adj


def rank_biserial_paired(diff):
    d = np.asarray(diff, dtype=float)
    d = d[np.isfinite(d) & (d != 0)]
    if len(d)==0:
        return 0.0
    ranks = stats.rankdata(np.abs(d), method='average')
    wpos = ranks[d>0].sum()
    wneg = ranks[d<0].sum()
    return float((wpos-wneg)/(wpos+wneg))


def make_pairs(df):
    chunks=[]
    gap_values=[]
    unpaired=0
    for flow_id,g in df.groupby('flow_id',sort=True):
        g=g.sort_values(['gen_time_s','packet_id'],kind='mergesort').reset_index(drop=True)
        n=(len(g)//2)*2
        unpaired += len(g)-n
        a=g.iloc[:n:2].reset_index(drop=True)
        b=g.iloc[1:n:2].reset_index(drop=True)
        gaps=(b['gen_time_s']-a['gen_time_s']).to_numpy(float)
        gap_values.append(gaps)
        q=pd.DataFrame({
            'flow_id': int(flow_id),
            'rgb_packet_id': a.packet_id.to_numpy(),
            'thermal_packet_id': b.packet_id.to_numpy(),
            'rgb_gen_time_s': a.gen_time_s.to_numpy(),
            'thermal_gen_time_s': b.gen_time_s.to_numpy(),
            'rgb_outcome': a.outcome.to_numpy(),
            'thermal_outcome': b.outcome.to_numpy(),
            'rgb_delay_s': a.delay_s.to_numpy(),
            'thermal_delay_s': b.delay_s.to_numpy(),
        })
        chunks.append(q)
    pairs=pd.concat(chunks,ignore_index=True)
    gaps=np.concatenate(gap_values) if gap_values else np.array([])
    pairs['both_delivered']=(pairs.rgb_outcome=='DELIVERED')&(pairs.thermal_outcome=='DELIVERED')
    pairs['pair_transport_latency_s']=np.where(
        pairs.both_delivered,
        np.maximum(pairs.rgb_delay_s,pairs.thermal_delay_s), np.nan)
    pairs['network_delay_skew_s']=np.where(
        pairs.both_delivered,
        np.abs(pairs.rgb_delay_s-pairs.thermal_delay_s), np.nan)
    return pairs, unpaired, gaps


def _trace_names(z):
    names=[]
    for n in z.namelist():
        if not (n.endswith('.csv.gz') and '_H300.csv.gz' in n and '/STRESS/' in n):
            continue
        if n.startswith('outputs/traces/pilot/') or n.startswith('outputs/traces/campaign/'):
            names.append(n)
    return sorted(names)


def analyze(input_zip, outdir, verbose=True):
    input_zip=Path(input_zip)
    outdir=Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    figdir=outdir/'figures'; figdir.mkdir(exist_ok=True)

    observed_sha=sha256_file(input_zip)
    if observed_sha != EXPECTED_INPUT_SHA256:
        raise RuntimeError(f'Frozen input SHA-256 mismatch: {observed_sha}')

    run_rows=[]
    sens_rows=[]
    trace_audit=[]
    drop_rows=[]

    with zipfile.ZipFile(input_zip) as z:
        traces=_trace_names(z)
        if len(traces)!=48:
            raise RuntimeError(f'Expected 48 final H300 traces, found {len(traces)}')
        seen=set()
        for idx,n in enumerate(traces,1):
            df=pd.read_csv(io.BytesIO(z.read(n)),compression='gzip')
            required={'run_id','scenario','protocol','seed','packet_id','flow_id','src','dst','gen_time_s','payload_bytes','outcome','delay_s','drop_reason'}
            missing=required-set(df.columns)
            if missing:
                raise RuntimeError(f'{n}: missing columns {sorted(missing)}')
            scenario=str(df.scenario.iloc[0]); protocol=str(df.protocol.iloc[0]); seed=int(df.seed.iloc[0])
            if scenario!='STRESS' or protocol not in PROTOCOLS or seed not in SEEDS:
                raise RuntimeError(f'{n}: unexpected cohort identity')
            key=(protocol,seed)
            if key in seen:
                raise RuntimeError(f'Duplicate protocol/seed trace: {key}')
            seen.add(key)
            if len(df)!=EXPECTED_ROWS_PER_RUN:
                raise RuntimeError(f'{n}: expected {EXPECTED_ROWS_PER_RUN} packets, found {len(df)}')
            if not df.packet_id.is_unique:
                raise RuntimeError(f'{n}: packet_id is not unique')
            if df.flow_id.nunique()!=EXPECTED_FLOWS:
                raise RuntimeError(f'{n}: expected {EXPECTED_FLOWS} flows')
            if set(df.payload_bytes.unique())!={EXPECTED_PAYLOAD}:
                raise RuntimeError(f'{n}: payload bytes mismatch')
            if df.run_id.nunique()!=1 or df.protocol.nunique()!=1 or df.seed.nunique()!=1:
                raise RuntimeError(f'{n}: mixed run identity')

            pairs,unpaired,gaps=make_pairs(df)
            if len(pairs)!=EXPECTED_PAIRS_PER_RUN or unpaired!=EXPECTED_UNPAIRED_PER_RUN:
                raise RuntimeError(f'{n}: pair count mismatch pairs={len(pairs)}, unpaired={unpaired}')
            gap_max_abs=float(np.max(np.abs(gaps-EXPECTED_PAIR_GAP_S)))
            if gap_max_abs>1e-10:
                raise RuntimeError(f'{n}: within-pair generation gap mismatch max_abs={gap_max_abs}')

            both=pairs.both_delivered
            lat=pairs.pair_transport_latency_s
            skew=pairs.network_delay_skew_s
            ready=both & (lat<=PRIMARY_D) & (skew<=PRIMARY_S)
            deadline_violation=both & (lat>PRIMARY_D)
            skew_violation=both & (skew>PRIMARY_S)
            temporal_violation=both & ((lat>PRIMARY_D)|(skew>PRIMARY_S))

            generated_pairs=len(pairs)
            both_n=int(both.sum())
            ready_n=int(ready.sum())
            delivered_packets=int((df.outcome=='DELIVERED').sum())
            pdr_trace=delivered_packets/len(df)

            run_rows.append({
                'scenario':scenario,'protocol':protocol,'seed':seed,
                'generated_packets':len(df),
                'generated_complete_pairs':generated_pairs,
                'unpaired_packets':unpaired,
                'generation_gap_mean_s':float(gaps.mean()),
                'generation_gap_max_abs_error_s':gap_max_abs,
                'delivered_packets':delivered_packets,
                'trace_PDR':pdr_trace,
                'both_delivered_pairs':both_n,
                'pair_delivery_rate':both_n/generated_pairs,
                'fusion_ready_pairs':ready_n,
                'FRPDR':ready_n/generated_pairs,
                'pair_latency_p50_s':float(lat[both].quantile(.50)),
                'pair_latency_p95_s':float(lat[both].quantile(.95)),
                'network_skew_p50_s':float(skew[both].quantile(.50)),
                'network_skew_p95_s':float(skew[both].quantile(.95)),
                'modality_loss_rate':1-(both_n/generated_pairs),
                'deadline_violation_rate_allpairs':int(deadline_violation.sum())/generated_pairs,
                'skew_violation_rate_allpairs':int(skew_violation.sum())/generated_pairs,
                'temporal_violation_rate_allpairs':int(temporal_violation.sum())/generated_pairs,
            })
            for D in DVALS:
                for S in SVALS:
                    rr=both & (lat<=D) & (skew<=S)
                    sens_rows.append({'protocol':protocol,'seed':seed,'Dmax_s':D,'delta_max_s':S,'FRPDR':float(rr.mean())})

            for reason,count in df.loc[df.outcome!='DELIVERED','drop_reason'].fillna('UNSPECIFIED').value_counts().items():
                drop_rows.append({'protocol':protocol,'seed':seed,'drop_reason':reason,'count':int(count)})

            trace_audit.append({
                'trace':n,'protocol':protocol,'seed':seed,'rows':len(df),
                'flows':df.flow_id.nunique(),'payload_bytes':EXPECTED_PAYLOAD,
                'pairs':generated_pairs,'unpaired':unpaired,'gap_max_abs_error_s':gap_max_abs,
                'status':'PASS'
            })
            if verbose and (idx%8==0 or idx==48):
                print(f'Processed {idx}/48 traces')

    expected_set={(p,s) for p in PROTOCOLS for s in SEEDS}
    if seen != expected_set:
        raise RuntimeError(f'Final cohort mismatch: missing={sorted(expected_set-seen)}, extra={sorted(seen-expected_set)}')

    run=pd.DataFrame(run_rows).sort_values(['seed','protocol']).reset_index(drop=True)
    sensitivity=pd.DataFrame(sens_rows)
    trace_audit_df=pd.DataFrame(trace_audit).sort_values(['seed','protocol']).reset_index(drop=True)
    drop=pd.DataFrame(drop_rows)

    summary=run.groupby('protocol').agg(
        n=('seed','size'),
        trace_PDR_mean=('trace_PDR','mean'),
        trace_PDR_sd=('trace_PDR','std'),
        pair_delivery_mean=('pair_delivery_rate','mean'),
        pair_delivery_sd=('pair_delivery_rate','std'),
        FRPDR_mean=('FRPDR','mean'),
        FRPDR_sd=('FRPDR','std'),
        pair_latency_p95_mean_s=('pair_latency_p95_s','mean'),
        network_skew_p95_mean_s=('network_skew_p95_s','mean'),
    ).reindex(PROTOCOLS).reset_index()

    sens_summary=(sensitivity.groupby(['protocol','Dmax_s','delta_max_s']).FRPDR
                  .agg(FRPDR_mean='mean',FRPDR_sd='std').reset_index())

    pivot=run.pivot(index='seed',columns='protocol',values='FRPDR').reindex(index=SEEDS,columns=PROTOCOLS)
    chi2,p=stats.friedmanchisquare(*[pivot[pname].values for pname in PROTOCOLS])
    W=chi2/(len(SEEDS)*(len(PROTOCOLS)-1))
    friedman=pd.DataFrame([{'metric':'FRPDR_primary','n_seeds':len(SEEDS),'k_protocols':len(PROTOCOLS),
                            'friedman_chi2':chi2,'p_value':p,'kendalls_W':W}])

    pair_rows=[]
    raw=[]
    for base in BASELINES:
        d=(pivot['ELM_CH_AODV_EM']-pivot[base]).values
        res=stats.wilcoxon(pivot['ELM_CH_AODV_EM'].values,pivot[base].values,alternative='two-sided',zero_method='wilcox',mode='auto')
        rbc=rank_biserial_paired(d)
        mean_diff=float(np.mean(d)); med_diff=float(np.median(d))
        rel=100*mean_diff/float(pivot[base].mean())
        raw.append(float(res.pvalue))
        pair_rows.append({'comparison':f'ELM_CH_AODV_EM vs {base}','W_statistic':float(res.statistic),
                          'p_raw':float(res.pvalue),'rank_biserial':rbc,'mean_difference':mean_diff,
                          'median_difference':med_diff,'relative_gain_percent':rel})
    adj=holm_adjust(raw)
    for r,a in zip(pair_rows,adj):
        r['p_holm']=float(a); r['holm_significant_0_05']=bool(a<0.05)
    pairwise=pd.DataFrame(pair_rows)

    if drop.empty:
        drop_summary=pd.DataFrame(columns=['protocol','drop_reason','count'])
    else:
        drop_summary=drop.groupby(['protocol','drop_reason'],as_index=False)['count'].sum().sort_values(['protocol','count'],ascending=[True,False])

    # QA against frozen expected results
    qa_primary={}
    for proto,(exp_mean,exp_sd) in EXPECTED_PRIMARY.items():
        row=summary.loc[summary.protocol==proto].iloc[0]
        dm=abs(float(row.FRPDR_mean)-exp_mean); ds=abs(float(row.FRPDR_sd)-exp_sd)
        if dm>1e-12 or ds>1e-12:
            raise RuntimeError(f'{proto}: primary result mismatch mean_err={dm}, sd_err={ds}')
        qa_primary[proto]={'mean':float(row.FRPDR_mean),'sd':float(row.FRPDR_sd)}
    ec,ep,ew=EXPECTED_FRIEDMAN
    if max(abs(chi2-ec),abs(p-ep),abs(W-ew))>1e-12:
        raise RuntimeError('Friedman result mismatch against frozen QA')

    # ELM must be highest at every one of the 16 threshold points
    winners=[]
    for (D,S),g in sens_summary.groupby(['Dmax_s','delta_max_s']):
        g=g.sort_values('FRPDR_mean',ascending=False)
        winners.append({'Dmax_s':D,'delta_max_s':S,'winner':g.iloc[0].protocol,'winner_mean':g.iloc[0].FRPDR_mean})
    winners_df=pd.DataFrame(winners)
    elm_all=bool((winners_df.winner=='ELM_CH_AODV_EM').all())
    if not elm_all:
        raise RuntimeError('ELM is not highest mean FRPDR at all 16 sensitivity points')

    # save tables
    run.to_csv(outdir/'run_level_primary.csv',index=False)
    summary.to_csv(outdir/'primary_summary.csv',index=False)
    sensitivity.to_csv(outdir/'sensitivity_run_level.csv',index=False)
    sens_summary.to_csv(outdir/'sensitivity_summary.csv',index=False)
    friedman.to_csv(outdir/'primary_friedman.csv',index=False)
    pairwise.to_csv(outdir/'primary_pairwise_stats.csv',index=False)
    trace_audit_df.to_csv(outdir/'trace_audit.csv',index=False)
    drop_summary.to_csv(outdir/'drop_reason_summary.csv',index=False)
    winners_df.to_csv(outdir/'sensitivity_winners.csv',index=False)

    # Figure 1: paired FRPDR across protocols by seed
    x=np.arange(len(PROTOCOLS))
    fig,ax=plt.subplots(figsize=(8.5,5.2))
    for seed in SEEDS:
        vals=pivot.loc[seed,PROTOCOLS].values
        ax.plot(x,vals,marker='o',linewidth=0.9,alpha=0.55)
    means=pivot.mean(axis=0).values
    ax.plot(x,means,marker='D',linewidth=2.6,label='Mean')
    ax.set_xticks(x,PROTOCOLS,rotation=15)
    ax.set_ylabel('Fusion-ready pair delivery ratio (FRPDR)')
    ax.set_title('Primary fusion-readiness comparison (Dmax = 200 ms, delta = 50 ms)')
    ax.set_ylim(0,1.02); ax.grid(axis='y',alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(figdir/'Fig_STEP7_3C_primary_paired_FRPDR.png',dpi=300,bbox_inches='tight'); plt.close(fig)

    # Figure 2: deadline sensitivity at delta 50 ms
    fig,ax=plt.subplots(figsize=(8.2,5.0))
    for proto in PROTOCOLS:
        g=sens_summary[(sens_summary.protocol==proto)&(sens_summary.delta_max_s==0.05)].sort_values('Dmax_s')
        ax.errorbar(g.Dmax_s*1000,g.FRPDR_mean,yerr=g.FRPDR_sd,marker='o',capsize=3,label=proto)
    ax.set_xlabel('Dmax (ms)'); ax.set_ylabel('Mean FRPDR'); ax.set_title('Deadline sensitivity (delta = 50 ms)')
    ax.set_ylim(0,1.02); ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(figdir/'Fig_STEP7_3C_deadline_sensitivity.png',dpi=300,bbox_inches='tight'); plt.close(fig)

    # Figure 3: skew sensitivity at Dmax 200 ms
    fig,ax=plt.subplots(figsize=(8.2,5.0))
    for proto in PROTOCOLS:
        g=sens_summary[(sens_summary.protocol==proto)&(sens_summary.Dmax_s==0.2)].sort_values('delta_max_s')
        ax.errorbar(g.delta_max_s*1000,g.FRPDR_mean,yerr=g.FRPDR_sd,marker='o',capsize=3,label=proto)
    ax.set_xlabel('delta (ms)'); ax.set_ylabel('Mean FRPDR'); ax.set_title('Network-delay-skew sensitivity (Dmax = 200 ms)')
    ax.set_ylim(0,1.02); ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(figdir/'Fig_STEP7_3C_skew_sensitivity.png',dpi=300,bbox_inches='tight'); plt.close(fig)

    qa={
        'schemaVersion':'STEP7_3C_QA_V2',
        'status':'PASS',
        'input_sha256':observed_sha,
        'final_h300_runs':48,
        'protocols':PROTOCOLS,'seeds':SEEDS,
        'primary_thresholds':{'Dmax_s':PRIMARY_D,'delta_s':PRIMARY_S},
        'pairing':{'generated_complete_pairs_per_run':EXPECTED_PAIRS_PER_RUN,
                   'unpaired_packets_per_run':EXPECTED_UNPAIRED_PER_RUN,
                   'within_pair_generation_gap_s':EXPECTED_PAIR_GAP_S,
                   'interpretation':'first packet=RGB edge-preprocessed observation unit; second packet=thermal edge-preprocessed observation unit'},
        'primary_FRPDR':qa_primary,
        'friedman':{'chi2':float(chi2),'p':float(p),'kendalls_W':float(W)},
        'ELM_highest_mean_FRPDR_all_16_sensitivity_points':elm_all,
        'claim_boundary':'Network-conditioned fusion-readiness surrogate only; no raw-image transport, physical sensor synchronization, fusion-algorithm, or detector-accuracy claim.'
    }
    (outdir/'QA_SUMMARY.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')

    # Manuscript-ready summary
    sm={r.protocol:r for _,r in summary.iterrows()}
    pw={r.comparison:r for _,r in pairwise.iterrows()}
    lines=[
        '# STEP 7.3C — Manuscript-ready results',
        '',
        f'Frozen input SHA-256: `{observed_sha}`',
        '',
        'Primary operational thresholds: Dmax = 200 ms and delta = 50 ms.',
        '',
        '## Primary FRPDR',
    ]
    for proto in PROTOCOLS:
        r=sm[proto]
        lines.append(f'- {proto}: {r.FRPDR_mean:.6f} ± {r.FRPDR_sd:.6f}; pair-delivery mean {r.pair_delivery_mean:.6f}.')
    lines += [
        '', '## Omnibus paired comparison',
        f'- Friedman chi-square = {chi2:.4f}, p = {p:.6g}, Kendall W = {W:.6f}.',
        '', '## ELM_CH_AODV_EM paired comparisons',
    ]
    for base in BASELINES:
        r=pw[f'ELM_CH_AODV_EM vs {base}']
        lines.append(f'- vs {base}: mean difference = {r.mean_difference:.6f}; relative gain = {r.relative_gain_percent:.2f}%; raw p = {r.p_raw:.6g}; Holm p = {r.p_holm:.6g}; rank-biserial = {r.rank_biserial:.6f}.')
    lines += [
        '',
        f'- ELM_CH_AODV_EM has the highest mean FRPDR at all {len(DVALS)*len(SVALS)} threshold combinations in the 4x4 sensitivity grid: {elm_all}.',
        '',
        '## Scientific boundary',
        'The analysis quantifies network-conditioned fusion readiness. The paired 512-byte packets represent edge-preprocessed observation units, not raw RGB or thermal images. Consecutive packet pairing is an operational surrogate; the 50-ms generation separation is inherited from the frozen CBR traffic and does not represent physical sensor synchronization. No fusion-algorithm or detector-accuracy claim is made.',
    ]
    (outdir/'MANUSCRIPT_READY_RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')

    # zip results
    result_zip=outdir.parent/'STEP7_3C_RESULTS.zip'
    if result_zip.exists(): result_zip.unlink()
    with zipfile.ZipFile(result_zip,'w',zipfile.ZIP_DEFLATED) as zz:
        for pth in sorted(outdir.rglob('*')):
            if pth.is_file():
                zz.write(pth,pth.relative_to(outdir.parent))

    return {'summary':summary,'friedman':friedman,'pairwise':pairwise,'qa':qa,'results_zip':str(result_zip)}

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('input_zip')
    ap.add_argument('outdir')
    args=ap.parse_args()
    res=analyze(args.input_zip,args.outdir,verbose=True)
    print('\nPRIMARY SUMMARY')
    print(res['summary'].to_string(index=False))
    print('\nFRIEDMAN')
    print(res['friedman'].to_string(index=False))
    print('\nPAIRWISE')
    print(res['pairwise'].to_string(index=False))
    print('\nQA: PASS')
    print('Results ZIP:',res['results_zip'])
