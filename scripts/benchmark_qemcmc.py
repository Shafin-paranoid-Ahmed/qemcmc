import argparse, csv, subprocess, sys, time

import numpy as np

from common import RESULTS, write_json, write_rows
from exact import all_spins
from gate_g1 import SharedIsingEBM
from qemcmc import ExactQuantumProposal, benchmark, planted_instance
from stage1_train import SAMPLERS, exact_stats, sample_negative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spins", type=int, default=12)
    parser.add_argument("--stage1-all-samplers", action="store_true")
    parser.add_argument("--stage1-full-updates", action="store_true")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.stage1_all_samplers:
        enum=all_spins(16); rows=[]
        for sampler in SAMPLERS:
            proposal_times=[]; fixed_times=[]; rebuild_times=[]
            for repeat in range(args.repeats):
                rng=np.random.default_rng(repeat); model=SharedIsingEBM(16,4,0); chain_s=rng.choice((-1.,1.),(1,16)); chain_y=rng.integers(4,size=1)
                started=time.perf_counter(); exact_stats(model,enum); exact_stats(model,enum); fixed_seconds=time.perf_counter()-started
                benchmark_events=2 if sampler=="pt" else 1
                if sampler=="exact": proposal=0.; rebuild=0.
                else:
                    started=time.perf_counter(); _,_,_,_,_,_,rebuild=sample_negative(model,sampler,chain_s,chain_y,benchmark_events,rng); proposal=time.perf_counter()-started
                proposal_times.append((proposal-rebuild)/benchmark_events); fixed_times.append(fixed_seconds); rebuild_times.append(rebuild)
            median_proposal=float(np.median(proposal_times)); median_rebuild=float(np.median(rebuild_times))
            rows.append({"sampler":sampler,"bits":16,"benchmark_chains":1,"benchmark_proposal_steps":2 if sampler=="pt" else 1,"seconds_per_proposal_excluding_rebuild":max(0.0,median_proposal),"fixed_exact_metrics_seconds_per_update":float(np.median(fixed_times)),"qemcmc_rebuild_seconds_per_update":median_rebuild})
        write_rows(RESULTS/"stage1_benchmark_level-b-easy_0_20260713.csv",rows); print(*rows,sep="\n")
    if args.stage1_full_updates:
        full_rows=[]; smoke_dir=RESULTS/"smoke_20260713"; smoke_dir.mkdir(exist_ok=True); run_tag=f"benchmark-script-{time.time_ns()}"
        trainer=RESULTS.parent/"scripts"/"stage1_train.py"
        for sampler in SAMPLERS:
            command=[sys.executable,str(trainer),"--level","b-easy","--sampler",sampler,"--seed","0","--updates","2","--chains","1","--proposal-steps","32","--tag",run_tag,"--max-updates-this-invocation","1"]
            started=time.perf_counter(); subprocess.run(command,check=True); wall=time.perf_counter()-started
            prefix=f"stage1_{sampler}_level-b-easy_0_{run_tag}"; history=RESULTS/f"{prefix}_history.csv"; state=RESULTS/f"{prefix}_state.json"
            with history.open(encoding="utf-8") as handle: row=next(csv.DictReader(handle))
            full_rows.append({"sampler":sampler,"level":"b-easy","seed":0,"chains":1,"proposal_steps":32,"proposal_events_per_update":32,"measured_update_body_seconds":float(row["elapsed_seconds"]),"measured_invocation_seconds":wall})
            history.replace(smoke_dir/history.name); state.replace(smoke_dir/state.name)
        write_rows(RESULTS/"stage1_full_update_benchmark_level-b-easy_0_20260713.csv",full_rows); print(*full_rows,sep="\n")
    if args.stage1_all_samplers or args.stage1_full_updates: return
    bias, coupling, _ = planted_instance(args.spins, 0)
    result = {"spins": args.spins, **benchmark(ExactQuantumProposal(bias, coupling))}
    write_json(RESULTS / f"qemcmc_exact_level-a_{args.spins}_timing.json", result)
    print(result)


if __name__ == "__main__":
    main()
