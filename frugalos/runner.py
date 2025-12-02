from __future__ import annotations
import json, os, time, hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
from .local.ollama_adapter import generate_once
from .validators.schema import is_schema_valid, try_parse_json
from .validators.consensus import majority_vote
from .oracle.update import load_routing_table
from .ledger import Receipts
from .prompts import create_template_manager_from_config

def _hash_sig(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def k_sample(prompt: str, model_cfg: dict, k: int) -> list[str]:
    outs = []
    for _ in range(k):
        outs.append(generate_once(model_cfg["name"], prompt, temp=model_cfg.get("temp",0.2)))
    return outs

def run_job(goal: str, project: str, context_path: Optional[str], schema_path: Optional[str],
            budget_cents: int, outdir: Path, policy_yaml: str) -> dict:
    start = time.time()
    policy = yaml.safe_load(policy_yaml)
    route_cfg = policy["routing"]
    k = int(route_cfg.get("k_samples", 3))
    threshold = float(route_cfg.get("consensus_threshold", 0.67))

    # Load schema if provided
    schema = None
    if schema_path:
        with open(schema_path, "r") as f:
            schema = json.load(f)

    # Create template manager
    template_manager = create_template_manager_from_config(policy_yaml)

    # Load context using template manager
    ctx = template_manager.load_context_from_path(context_path)

    # Build prompt using template system (with schema embedding)
    # Note: examples will be added in Phase 4
    prompt, template_version = template_manager.build_prompt(
        goal=goal,
        context=ctx,
        schema=schema,
        examples=None,  # Will be added in Phase 4
        use_cache=True   # Enable prompt caching (Phase 2)
    )

    # T1 local path
    m1 = policy["models"]["T1_text"]
    outs = k_sample(prompt, m1, k)
    winner, agree = majority_vote(outs, threshold=threshold)

    # Track validation details for optimization
    validation_errors = []
    consensus_votes = json.dumps([outs.count(winner)] + [outs.count(x) for x in set(outs) if x != winner])

    if schema:
        if not is_schema_valid(winner, schema):
            validation_errors.append("schema_invalid")
    if agree < threshold:
        validation_errors.append("low_consensus")

    if not validation_errors:
        artifact_path = outdir / "result.txt"
        artifact_path.write_text(winner)
        cost = 0
        rec = Receipts(project)
        rec.save(job_id=outdir.name, cost_cents=cost, latency_s=round(time.time()-start,2),
                 tier="T1", model_path=m1["name"], why="ok_local",
                 template_version=template_version, validation_errors="", consensus_votes=consensus_votes)
        receipt_path = outdir / "receipt.json"
        receipt_path.write_text(json.dumps(rec.last(), indent=2))
        return {"summary":"local success","artifact_path":str(artifact_path),"receipt_path":str(receipt_path)}

    # Local retry once (semantic compression will be added in Phase 5)
    prompt2 = prompt[:3000]  # Simple truncation for now
    outs2 = k_sample(prompt2, m1, k)
    winner2, agree2 = majority_vote(outs2, threshold=threshold)

    # Track retry validation details
    retry_validation_errors = []
    retry_consensus_votes = json.dumps([outs2.count(winner2)] + [outs2.count(x) for x in set(outs2) if x != winner2])

    if schema:
        if not is_schema_valid(winner2, schema):
            retry_validation_errors.append("schema_invalid")
    if agree2 < threshold:
        retry_validation_errors.append("low_consensus")

    if (not schema or is_schema_valid(winner2, schema)) and agree2 >= threshold:
        artifact_path = outdir / "result.txt"
        artifact_path.write_text(winner2)
        rec = Receipts(project)
        rec.save(job_id=outdir.name, cost_cents=0, latency_s=round(time.time()-start,2),
                 tier="T1", model_path=m1["name"], why="retry_ok",
                 template_version=template_version, validation_errors=",".join(retry_validation_errors),
                 consensus_votes=retry_consensus_votes)
        receipt_path = outdir / "receipt.json"
        receipt_path.write_text(json.dumps(rec.last(), indent=2))

        # Save successful example for few-shot learning (Phase 4)
        quality_score = agree2  # Use consensus agreement as quality metric
        rec.save_successful_example(
            job_id=outdir.name,
            goal=goal,
            context=ctx,
            output=winner2,
            schema_path=schema_path or "",
            quality_score=quality_score,
            consensus_agreement=agree2
        )

        return {"summary":"local retry success","artifact_path":str(artifact_path),"receipt_path":str(receipt_path)}

    # Consider remote escalation only if budget > 0 and allowed
    if int(budget_cents) > 0 and os.getenv("FRUGAL_ALLOW_REMOTE","0") == "1":
        tbl = load_routing_table()
        # naive pick: first model with price_in/out within budget
        for m in tbl.get("models", []):
            if m.get("price_in", 0) == 0 and m.get("privacy","P2") in ("P0","P1"):
                # TODO: call remote adapter; here we just mark as suggestion
                suggestion = f"TRY_FREE:{m['id']}"
                break
        else:
            suggestion = "NEED_PAID"
        artifact_path = outdir / "result.txt"
        artifact_path.write_text(winner2 if winner2 else outs2[0])
        rec = Receipts(project)
        rec.save(job_id=outdir.name, cost_cents=0, latency_s=round(time.time()-start,2),
                 tier="T1→T2?", model_path=suggestion, why="escalation_suggested")
        receipt_path = outdir / "receipt.json"
        receipt_path.write_text(json.dumps(rec.last(), indent=2))
        return {"summary":"suggest escalation", "artifact_path":str(artifact_path), "receipt_path":str(receipt_path)}

    # Otherwise return best local attempt with explicit failure reasons
    artifact_path = outdir / "result.txt"
    artifact_path.write_text(winner2 if winner2 else outs2[0])
    rec = Receipts(project)
    rec.save(job_id=outdir.name, cost_cents=0, latency_s=round(time.time()-start,2),
             tier="T1", model_path=m1["name"], why="local_limit:" + ",".join(reasons))
    receipt_path = outdir / "receipt.json"
    receipt_path.write_text(json.dumps(rec.last(), indent=2))
    return {"summary":"local limit reached", "artifact_path":str(artifact_path), "receipt_path":str(receipt_path)}
