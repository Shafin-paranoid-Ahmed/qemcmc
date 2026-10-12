from __future__ import annotations

import argparse, csv, json, os, subprocess, sys, time
from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp, softmax

from common import RESULTS, ROOT, seed_all, write_json
from exact import all_spins, local_modes
from adaptive_controller import ARMS, ARM_VALUE_COLUMNS, AdaptiveController, ControllerArm
from qemcmc import ExactQuantumProposal, index_to_spins, planted_instance, spins_to_index

SAMPLERS = (
    "gibbs", "mh-local", "mh-uniform", "pcd", "pt", "qemcmc", "exact",
    "adaptive-qemcmc", "adaptive-qemcmc-p", "qemcmc-p",
    "adaptive-qemcmc-proxy", "adaptive-qemcmc-p-proxy",
)
STAGE1_20BIT_CODE_TAG = "stage1-20bit-g3-v2-gpu"
STAGE1_22BIT_CODE_TAG = "stage1-22bit-ladder22-v1-gpu"
STAGE1_24BIT_CODE_TAG = "stage1-24bit-ladder24-v1-gpu"
STAGE1_LEVEL_C_CODE_TAGS = {
    20: STAGE1_20BIT_CODE_TAG,
    22: STAGE1_22BIT_CODE_TAG,
    24: STAGE1_24BIT_CODE_TAG,
}


@dataclass(frozen=True)
class SamplerConfiguration:
    sampler_variant: str
    reward_signal: str
    persistence: bool
    adaptive: bool


def sampler_configuration(sampler: str) -> SamplerConfiguration:
    configurations = {
        "adaptive-qemcmc": ("exact", False, True),
        "adaptive-qemcmc-p": ("exact", True, True),
        "qemcmc-p": ("none", True, False),
        "adaptive-qemcmc-proxy": ("proxy", False, True),
        "adaptive-qemcmc-p-proxy": ("proxy", True, True),
    }
    reward_signal, persistence, adaptive = configurations.get(
        sampler, ("none", sampler == "pcd", False)
    )
    return SamplerConfiguration(sampler, reward_signal, persistence, adaptive)


class SharedIsingEBM:
    """Stage-1 subset of the registered shared joint Ising EBM."""

    def __init__(self, bits: int, classes: int, seed: int):
        rng = seed_all(seed)
        self.b = np.zeros(bits)
        self.j = rng.normal(0, 0.005, (bits, bits))
        self.j = np.triu(self.j, 1)
        self.j += self.j.T
        self.u = np.zeros((classes, bits))
        self.c = np.zeros(classes)

    def energy(self, s: np.ndarray, y: np.ndarray) -> np.ndarray:
        return (
            -(s @ self.b)
            - 0.5 * np.einsum("bi,ij,bj->b", s, self.j, s)
            - np.sum(self.u[y] * s, axis=1)
            - self.c[y]
        )

    def probabilities(self, s: np.ndarray) -> np.ndarray:
        return softmax(s @ self.u.T + self.c, axis=1)


def classification_metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict:
    """Delegate to the unchanged registered metrics code in the CPU stack."""
    cpu_python = os.environ.get("QEMCMC_METRICS_PYTHON", sys.executable)
    bridge = ROOT / "scripts" / "metrics_bridge.py"
    payload = json.dumps({
        "probabilities": np.asarray(probabilities, float).tolist(),
        "labels": np.asarray(labels, int).tolist(),
    })
    completed = subprocess.run(
        [str(cpu_python), str(bridge)],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def read_dataset(level: str, seed: int, bits: int):
    suffix = f"_{STAGE1_LEVEL_C_CODE_TAGS[bits]}" if bits in STAGE1_LEVEL_C_CODE_TAGS else ""
    if level == "c":
        legacy = "_stage1-16bit" if bits == 16 else suffix
        path = RESULTS / f"codes_frozenresnet_level-c_{seed}{legacy}_codes.csv"
    elif level in ("b-easy", "b-hard"):
        path = RESULTS / f"codes_planted_level-{level}_{seed}{suffix}_codes.csv"
    else:
        bias,coupling,beta=planted_instance(bits,seed); enum=all_spins(bits); energies=-(enum@bias)-.5*np.einsum("bi,ij,bj->b",enum,coupling,enum); probability=np.exp(-beta*(energies-energies.min())); probability/=probability.sum(); modes=local_modes(energies,bits); anchors=modes[np.argsort(energies[modes])[:4]]; rng=np.random.default_rng(20_000+seed); counts=(2000,500,500); sampled=np.concatenate([rng.choice(len(enum),size=n,p=probability) for n in counts]); codes=((enum[sampled]+1)/2).astype(np.int8); anchor_bits=((enum[anchors]+1)/2).astype(np.int8); labels=np.argmin(np.count_nonzero(codes[:,None,:]!=anchor_bits[None,:,:],axis=2),axis=1); partitions=np.repeat(["train","val","test"],counts); return codes,labels,partitions
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    bits = [name for name in data.dtype.names if name.startswith("bit_")]
    return np.column_stack([data[name] for name in bits]).astype(np.int8), data["label"].astype(int), data["partition"]


def model_arrays(model): return {k: getattr(model, k).copy() for k in ("b", "j", "u", "c")}
def set_arrays(model, arrays):
    for key, value in arrays.items(): setattr(model, key, np.asarray(value, float))


def exact_distribution(model, states):
    base = states @ model.b + 0.5 * np.einsum("bi,ij,bj->b", states, model.j, states)
    logits = base[:, None] + states @ model.u.T + model.c
    log_z = float(logsumexp(logits))
    return np.exp(logits - log_z), log_z


def stats(states, labels, classes, weights=None):
    weights = np.ones(len(states)) / len(states) if weights is None else np.asarray(weights)
    out = {"b": weights @ states, "j": np.einsum("n,ni,nj->ij", weights, states, states),
           "u": np.zeros((classes, states.shape[1])), "c": np.zeros(classes)}
    np.fill_diagonal(out["j"], 0.0)
    for y in range(classes):
        mask = labels == y; out["c"][y] = weights[mask].sum()
        if mask.any(): out["u"][y] = weights[mask] @ states[mask]
    return out


def exact_stats(model, enum):
    probability, log_z = exact_distribution(model, enum)
    labels = np.tile(np.arange(model.u.shape[0]), len(enum)); states = np.repeat(enum, model.u.shape[0], axis=0)
    return stats(states, labels, model.u.shape[0], probability.ravel()), probability, log_z


def vector_norm(delta): return float(np.sqrt(sum(np.sum(value * value) for value in delta.values())))


def iat(values):
    x = np.asarray(values, float); x -= x.mean(); var = np.mean(x*x)
    if var < 1e-15: return float(len(x))
    total = 1.0
    for lag in range(1, max(2, len(x)//4)):
        rho = np.mean(x[:-lag]*x[lag:]) / var
        if rho <= 0: break
        total += 2*rho
    return float(total)


def aggregate_iat(values):
    traces = np.asarray(values, float)
    if traces.ndim == 1: traces = traces[:, None]
    return float(np.median([iat(traces[:, chain]) for chain in range(traces.shape[1])]))


def states_to_exact_indices(states):
    states = np.asarray(states)
    return (((states > 0).astype(np.uint64)) * (1 << np.arange(states.shape[1],dtype=np.uint64))).sum(1).astype(int)


def gibbs_label(model, state, rng, beta=1.0): return int(rng.choice(len(model.c), p=softmax(beta*(model.u @ state + model.c))))


def _quantum_propose(proposal, state, rng, backend, controller_arm):
    if controller_arm is None:
        return proposal.propose(state, rng)[0]
    evolution_time, gamma = controller_arm.draw_parameters(rng)
    if backend == "gpu":
        probability = proposal.distribution(spins_to_index(state), evolution_time, gamma)
    else:
        probability = proposal.distribution(state, evolution_time, gamma)
    index = int(rng.choice(len(probability), p=probability))
    return index_to_spins(index, len(state))


def sample_negative(
    model, sampler, chain_s, chain_y, steps, rng, backend="cpu",
    controller_arm: ControllerArm | None = None, return_diagnostics=False,
):
    chains, bits = chain_s.shape; trace_e=[]; trace_m=[]; visited=[]; visited_y=[]
    proposals = None
    rebuild_seconds = 0.0
    accepted_hamming_total = 0.0
    adaptive = sampler.startswith("adaptive-qemcmc")
    if adaptive and controller_arm is None:
        raise ValueError("adaptive QeMCMC requires one controller arm per update")
    uses_quantum_proposal = sampler in ("qemcmc", "qemcmc-p") or (
        adaptive and not controller_arm.classical
    )
    if uses_quantum_proposal:
        if backend == "gpu":
            from gpu_bench.gpu_proposal import GPUExactQuantumProposal

            proposal_type = lambda field, coupling: GPUExactQuantumProposal(coupling, field)
        else:
            proposal_type = lambda field, coupling: ExactQuantumProposal(field, coupling)
        started=time.perf_counter(); proposals=[proposal_type(model.b + model.u[y], model.j) for y in range(len(model.c))]; rebuild_seconds=time.perf_counter()-started
    if sampler == "pt":
        # Match gate_g2.py: one counted PT event is either one randomly chosen
        # replica move or one randomly chosen adjacent exchange. There are no
        # hidden replica sweeps outside the shared chains*steps event budget.
        replicas=rng.choice((-1.,1.),(chains,8,bits)); replicas[:,0]=chain_s
        labels=rng.integers(len(model.c),size=(chains,8)); labels[:,0]=chain_y
        betas=1/np.geomspace(1,8,8)
    for step in range(steps):
        for n in range(chains):
            if sampler == "pt":
                if step%2==0:
                    r=int(rng.integers(8)); state=replicas[n,r]; y=labels[n,r]; proposal=state.copy(); proposal[rng.integers(bits)]*=-1
                    delta=model.energy(proposal[None],np.array([y]))[0]-model.energy(state[None],np.array([y]))[0]
                    if rng.random()<np.exp(min(0,-betas[r]*delta)): replicas[n,r]=proposal
                    labels[n,r]=gibbs_label(model,replicas[n,r],rng,betas[r])
                else:
                    r=int(rng.integers(7))
                    e0=model.energy(replicas[n,r][None],np.array([labels[n,r]]))[0]; e1=model.energy(replicas[n,r+1][None],np.array([labels[n,r+1]]))[0]
                    if np.log(rng.random())<min(0,(betas[r]-betas[r+1])*(e0-e1)):
                        replicas[n,[r,r+1]]=replicas[n,[r+1,r]]; labels[n,[r,r+1]]=labels[n,[r+1,r]]
                chain_s[n],chain_y[n]=replicas[n,0],labels[n,0]
            else:
                state=chain_s[n]; y=chain_y[n]
                if sampler=="gibbs":
                    bit=rng.integers(bits); a=state.copy(); b=state.copy(); a[bit]=-1; b[bit]=1
                    ea=model.energy(a[None],np.array([y]))[0]; eb=model.energy(b[None],np.array([y]))[0]
                    chain_s[n]=b if rng.random()<1/(1+np.exp(eb-ea)) else a
                else:
                    if sampler in ("mh-local","pcd") or (adaptive and controller_arm.classical): proposal=state.copy(); proposal[rng.integers(bits)]*=-1
                    elif sampler=="mh-uniform": proposal=rng.choice((-1.,1.),bits)
                    elif uses_quantum_proposal: proposal=_quantum_propose(proposals[y],state,rng,backend,controller_arm if adaptive else None)
                    delta=model.energy(proposal[None],np.array([y]))[0]-model.energy(state[None],np.array([y]))[0]
                    accepted=rng.random()<np.exp(min(0,-delta))
                    if accepted:
                        accepted_hamming_total += float(np.count_nonzero(proposal != state))
                        chain_s[n]=proposal
                chain_y[n]=gibbs_label(model,chain_s[n],rng)
        trace_e.append(model.energy(chain_s,chain_y).copy()); trace_m.append(chain_s.mean(1).copy())
        visited.extend(states_to_exact_indices(chain_s).tolist())
        visited_y.extend(chain_y.astype(int).tolist())
    result=(chain_s,chain_y,np.asarray(trace_e),np.asarray(trace_m),visited,visited_y,rebuild_seconds)
    if return_diagnostics:
        return (*result, accepted_hamming_total / (chains * steps))
    return result


def adam_step(model, gradient, moment, variance, update, lr=0.01):
    for key in gradient:
        moment[key]=0.9*moment[key]+0.1*gradient[key]; variance[key]=0.999*variance[key]+0.001*gradient[key]**2
        value=getattr(model,key)+lr*(moment[key]/(1-0.9**update))/(np.sqrt(variance[key]/(1-0.999**update))+1e-8)
        if key=="j": value=np.triu(value,1); value=value+value.T
        setattr(model,key,value)


def append_row(path, row):
    exists=path.exists();
    with path.open("a",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(row));
        if not exists: writer.writeheader()
        writer.writerow(row)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--level",choices=("a","b-easy","b-hard","c"),required=True); parser.add_argument("--sampler",choices=SAMPLERS,required=True)
    parser.add_argument("--seed",type=int,required=True); parser.add_argument("--updates",type=int,required=True); parser.add_argument("--chains",type=int,required=True); parser.add_argument("--proposal-steps",type=int,required=True); parser.add_argument("--tag",required=True)
    parser.add_argument("--backend",choices=("cpu","gpu"),default="cpu")
    parser.add_argument("--bits",type=int,choices=(12,16,20,22,24),default=16)
    parser.add_argument("--max-updates-this-invocation",type=int,default=None,help="Engineering/resume test control; does not change the registered run budget.")
    args=parser.parse_args(); configuration=sampler_configuration(args.sampler)
    budget={k:getattr(args,k) for k in ("level","sampler","seed","updates","chains","proposal_steps","tag","backend","bits")}
    budget.update({"sampler_variant":configuration.sampler_variant,"reward_signal":configuration.reward_signal,"persistence":configuration.persistence})
    bits=args.bits
    if min(args.updates,args.chains,args.proposal_steps) < 1: raise ValueError("updates, chains, and proposal-steps must all be positive")
    if args.max_updates_this_invocation is not None and args.max_updates_this_invocation < 1: raise ValueError("max-updates-this-invocation must be positive")
    prefix=f"stage1_{args.sampler}_level-{args.level}_{args.seed}_{args.tag}"; history=RESULTS/f"{prefix}_history.csv"; state_path=RESULTS/f"{prefix}_state.json"; final_path=RESULTS/f"{prefix}_metadata.json"
    if final_path.exists():
        finished=json.loads(final_path.read_text())
        if finished["budget"]!=budget: raise RuntimeError(f"resume budget mismatch: existing={finished['budget']} requested={budget}")
        print(f"already complete: {final_path}"); return
    saved=None
    if state_path.exists():
        saved=json.loads(state_path.read_text())
        if saved["budget"]!=budget: raise RuntimeError(f"resume budget mismatch: existing={saved['budget']} requested={budget}")
        if saved.get("final_evaluation_started"):
            if saved.get("final_test_metrics"):
                write_json(final_path,{"budget":budget,"backend":args.backend,"bit_width":bits,"completed":True,"best_val_exact_nll":saved["best_val_nll"],"test_metrics":saved["final_test_metrics"],"shared_energy_model":True,"test_touched_once":True,"history":str(history)})
                print(f"recovered committed final test metrics: {final_path}"); return
            raise RuntimeError("final test evaluation previously started but metrics were not committed; refusing to touch the test split again")
    elif history.exists(): raise RuntimeError("history exists without resume state")
    x,y,partition=read_dataset(args.level,args.seed,bits); s=2*x.astype(float)-1; train=partition=="train"; val=partition=="val"; test=partition=="test"; classes=int(y.max()+1); enum=all_spins(bits); rng=np.random.default_rng(args.seed)
    if x.shape[1] != bits: raise RuntimeError(f"expected {bits}-bit codes, found {x.shape[1]}")
    model=SharedIsingEBM(bits,classes,args.seed); chain_s=rng.choice((-1.,1.),(args.chains,bits)); chain_y=rng.integers(classes,size=args.chains); positive=stats(s[train],y[train],classes)
    exact_reference=None
    if args.backend=="gpu":
        from gpu_bench.gpu_exact import GPUExactReference

        exact_reference=GPUExactReference(enum)
    moment={k:np.zeros_like(v) for k,v in model_arrays(model).items()}; variance={k:np.zeros_like(v) for k,v in model_arrays(model).items()}; start_update=0; best_val=float("inf"); best=model_arrays(model); elapsed_before=0.0
    controller=AdaptiveController() if configuration.adaptive else None
    if saved is not None:
        start_update=saved["completed_updates"]; set_arrays(model,saved["model"]); chain_s=np.asarray(saved["chain_s"]); chain_y=np.asarray(saved["chain_y"]); moment={k:np.asarray(v) for k,v in saved["moment"].items()}; variance={k:np.asarray(v) for k,v in saved["variance"].items()}; best_val=saved["best_val_nll"]; best={k:np.asarray(v) for k,v in saved["best_model"].items()}; rng.bit_generator.state=saved["rng_state"]; elapsed_before=float(saved.get("elapsed_seconds",0.0))
        if configuration.adaptive:
            if "controller" not in saved: raise RuntimeError("adaptive resume state is missing controller state")
            controller=AdaptiveController.from_state(saved["controller"])
            if controller.rounds != start_update: raise RuntimeError(f"controller/state update mismatch: controller={controller.rounds}, state={start_update}")
        history_rows=list(csv.DictReader(history.open(encoding="utf-8"))) if history.exists() else []
        history_update=int(history_rows[-1]["update"]) if history_rows else 0
        if history_update == start_update-1 and saved.get("last_row"): append_row(history,saved["last_row"]); history_update=start_update
        if history_update != start_update: raise RuntimeError(f"resume history/state mismatch: history update={history_update}, state update={start_update}")
    started=time.perf_counter()
    invocation_end=args.updates if args.max_updates_this_invocation is None else min(args.updates,start_update+args.max_updates_this_invocation)
    for update in range(start_update+1,invocation_end+1):
        exact,prob,log_z=exact_reference.stats(model) if exact_reference else exact_stats(model,enum)
        controller_arm=controller.select_arm() if controller else None
        if args.sampler=="exact": sampled=exact; trace_e=np.zeros((1,1)); trace_m=np.zeros((1,1)); visited=list(range(len(enum))); visited_y=[]; rebuild=0.; empirical=prob; accepted_hamming_jump=0.0
        else:
            if not configuration.persistence: chain_s=rng.choice((-1.,1.),(args.chains,bits)); chain_y=rng.integers(classes,size=args.chains)
            chain_s,chain_y,trace_e,trace_m,visited,visited_y,rebuild,accepted_hamming_jump=sample_negative(model,args.sampler,chain_s,chain_y,args.proposal_steps,rng,args.backend,controller_arm,True); sampled=stats(enum[np.asarray(visited)],np.asarray(visited_y),classes)
            empirical=np.zeros_like(prob); counts=np.zeros(prob.size); np.add.at(counts,np.asarray(visited)*classes+np.asarray(visited_y),1); empirical=(counts.reshape(prob.shape)+1e-12); empirical/=empirical.sum()
        gradient={k:positive[k]-sampled[k] for k in positive}; error=vector_norm({k:sampled[k]-exact[k] for k in exact})
        raw_reward=None; standardized_reward=None
        if controller:
            raw_reward=-error if configuration.reward_signal=="exact" else accepted_hamming_jump
            standardized_reward=controller.observe(controller_arm.index,raw_reward)
        adam_step(model,gradient,moment,variance,update)
        new_log_z=exact_reference.log_partition(model) if exact_reference else exact_stats(model,enum)[2]; train_nll=float(np.mean(model.energy(s[train],y[train])+new_log_z)); val_nll=float(np.mean(model.energy(s[val],y[val])+new_log_z))
        if val_nll<best_val: best_val=val_nll; best=model_arrays(model)
        marginal=-logsumexp(np.log(prob+1e-300),axis=1); modes=local_modes(marginal,bits); visited_set=set(visited)
        energy_iat=aggregate_iat(trace_e); magnetization_iat=aggregate_iat(trace_m); event_count=int(trace_e.size)
        controller_values=controller.value_estimates if controller else np.full(len(ARMS),np.nan)
        controller_columns={ARM_VALUE_COLUMNS[arm.index]:float(controller_values[arm.index]) if controller else "" for arm in ARMS}
        row={**budget,"bit_width":bits,"update":update,"chosen_arm":controller_arm.name if controller_arm else "","raw_reward":raw_reward if raw_reward is not None else "","standardized_reward":standardized_reward if standardized_reward is not None else "",**controller_columns,"gradient_error":error,"energy_iat":energy_iat,"energy_ess":0.0 if args.sampler=="exact" else event_count/energy_iat,"energy_ess_per_proposal":0.0 if args.sampler=="exact" else 1.0/energy_iat,"magnetization_iat":magnetization_iat,"magnetization_ess":0.0 if args.sampler=="exact" else event_count/magnetization_iat,"magnetization_ess_per_proposal":0.0 if args.sampler=="exact" else 1.0/magnetization_iat,"tv":float(.5*np.abs(empirical-prob).sum()),"kl_sample_exact":float(np.sum(empirical*np.log(empirical/(prob+1e-300)))),"mode_coverage":float(len(set(modes)&visited_set)/max(1,len(modes))),"train_exact_nll":train_nll,"val_exact_nll":val_nll,"qemcmc_rebuild_seconds":rebuild,"elapsed_seconds":elapsed_before+time.perf_counter()-started}
        state={"budget":budget,"completed_updates":update,"model":{k:v.tolist() for k,v in model_arrays(model).items()},"chain_s":chain_s.tolist(),"chain_y":chain_y.tolist(),"moment":{k:v.tolist() for k,v in moment.items()},"variance":{k:v.tolist() for k,v in variance.items()},"best_val_nll":best_val,"best_model":{k:v.tolist() for k,v in best.items()},"rng_state":rng.bit_generator.state,"elapsed_seconds":row["elapsed_seconds"],"last_row":row}
        if controller: state["controller"]=controller.to_state()
        write_json(state_path,state); append_row(history,row); print(f"{prefix} update {update}/{args.updates} error={error:.4f} elapsed={row['elapsed_seconds']:.1f}s",flush=True)
    if invocation_end < args.updates:
        print(f"paused after update {invocation_end}/{args.updates}; rerun the identical budget flags to resume",flush=True)
        return
    state=json.loads(state_path.read_text(encoding="utf-8")); state["final_evaluation_started"]=True; write_json(state_path,state)
    set_arrays(model,best); log_z=exact_reference.log_partition(model) if exact_reference else exact_stats(model,enum)[2]; probabilities=model.probabilities(s[test]); metrics=classification_metrics(probabilities,y[test]); metrics["heldout_joint_exact_nll"]=float(np.mean(model.energy(s[test],y[test])+log_z))
    state["final_test_metrics"]=metrics; write_json(state_path,state)
    write_json(final_path,{"budget":budget,"backend":args.backend,"bit_width":bits,"completed":True,"best_val_exact_nll":best_val,"test_metrics":metrics,"shared_energy_model":True,"test_touched_once":True,"history":str(history)}); print(final_path)


if __name__=="__main__": main()
