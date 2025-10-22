from __future__ import annotations
import json, os, sys, time, uuid
import typer
from rich import print
from rich.table import Table
from pathlib import Path
from .runner import run_job
from .oracle.update import update_oracle_if_needed, load_routing_table
from .ledger import Receipts

app = typer.Typer(add_completion=False)

@app.command()
def run(
    goal: str = typer.Option(..., "--goal", help="Unstructured task goal"),
    project: str = typer.Option("default", "--project"),
    context: str | None = typer.Option(None, "--context", help="Path to file/folder"),
    schema: str | None = typer.Option(None, "--schema", help="JSON schema path"),
    budget_cents: int = typer.Option(0, "--budget-cents", min=0),
):
    """Run a single job under Suit Mode or with pennies if allowed."""
    update_oracle_if_needed()
    job_id = str(uuid.uuid4())[:8]
    outdir = Path("out") / project / job_id
    outdir.mkdir(parents=True, exist_ok=True)

    policy_path = Path(__file__).parent / "policy.yaml"
    policy = policy_path.read_text()

    result = run_job(
        goal=goal,
        project=project,
        context_path=context,
        schema_path=schema,
        budget_cents=budget_cents,
        outdir=outdir,
        policy_yaml=policy,
    )
    print(f"[bold green]Result:[/bold green] {result['summary']}")
    print(f"[dim]Artifact:[/dim] {result['artifact_path']}")
    print(f"[dim]Receipt:[/dim]  {result['receipt_path']}")

@app.command()
def receipts(project: str = typer.Option("default", "--project")):
    """Show last receipts for a project."""
    r = Receipts(project)
    rows = r.tail(50)
    table = Table(title=f"Receipts: {project}")
    for col in ["when","job_id","cost_cents","latency_s","tier","model_path","why"]:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(row.get(k,"")) for k in ["when","job_id","cost_cents","latency_s","tier","model_path","why"]])
    print(table)

@app.command()
def oracle(show: bool = typer.Option(False, "--show"), free: bool = typer.Option(False, "--free")):
    """Update or show oracle routing table."""
    if show:
        tbl = load_routing_table()
        keep = [m for m in tbl.get("models",[]) if (free and m.get("price_in")==0) or (not free)]
        print(json.dumps({"models": keep}, indent=2))
    else:
        update_oracle_if_needed(force=True)
        print("[green]Oracle refreshed.[/green]")

if __name__ == "__main__":
    app()
