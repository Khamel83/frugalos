from __future__ import annotations
import json, os, sys, time, uuid
import typer
from rich import print
from rich.table import Table
from pathlib import Path
from .runner import run_job
from .oracle.update import update_oracle_if_needed, load_routing_table
from .ledger import Receipts
from .prompts.optimizer import create_optimizer

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

@app.command()
def optimize_prompts(
    project: str = typer.Option("default", "--project", help="Project to optimize"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze failures only, don't generate improvements"),
    hours: int = typer.Option(24, "--hours", help="Hours to look back for failures")
):
    """Analyze prompt failures and generate optimized templates."""
    print(f"[bold blue]Prompt Optimization:[/bold blue] {project}")

    try:
        policy_path = Path(__file__).parent / "policy.yaml"
        optimizer = create_optimizer(project, str(policy_path))

        if dry_run:
            # Just analyze failures
            analysis = optimizer.analyze_failures(hours)
            print(f"\n[green]Failure Analysis (last {hours} hours):[/green]")

            if analysis["total_patterns"] == 0:
                print("[dim]No failure patterns found.[/dim]")
                return

            # Show template performance
            print("\n[bold]Template Performance:[/bold]")
            table = Table()
            table.add_column("Template")
            table.add_column("Failures")
            table.add_column("Types")

            for template, perf in analysis["template_performance"].items():
                table.add_row(
                    template,
                    str(perf["total_failures"]),
                    ", ".join(perf["failure_types"])
                )
            print(table)

            # Show optimization opportunities
            if analysis["optimization_opportunities"]:
                print("\n[bold]Optimization Opportunities:[/bold]")
                for opp in analysis["optimization_opportunities"]:
                    print(f"  • {opp['template_version']}: {opp['failure_type']} ({opp['count']} times)")
                    print(f"    → {opp['suggestion']}")
        else:
            # Run full optimization cycle
            result = optimizer.run_optimization_cycle()

            print(f"\n[bold]Optimization Result:[/bold] {result['status']}")

            if result["status"] == "success":
                print(f"[green]✓ Created new template:[/green] {result['new_template']}")
                print(f"[dim]   Based on:[/dim] {result['original_template']}")
                print(f"[dim]   Analyzed:[/dim] {result['failures_analyzed']} failure patterns")
                if result.get("improvement_reason"):
                    print(f"[dim]   Reason:[/dim] {result['improvement_reason']}")

                # Show template performance comparison
                performance = optimizer.get_template_performance()
                if result["original_template"] in performance and result["new_template"] in performance:
                    orig = performance[result["original_template"]]
                    new = performance[result["new_template"]]
                    print(f"\n[bold]Performance Comparison:[/bold]")
                    table = Table()
                    table.add_column("Template")
                    table.add_column("Success Rate")
                    table.add_column("Retry Rate")
                    table.add_column("Avg Latency")

                    table.add_row(
                        result["original_template"],
                        f"{orig['success_rate']:.1%}",
                        f"{orig['retry_rate']:.1%}",
                        f"{orig['avg_latency']:.1f}s"
                    )
                    table.add_row(
                        result["new_template"],
                        f"{new['success_rate']:.1%}",
                        f"{new['retry_rate']:.1%}",
                        f"{new['avg_latency']:.1f}s"
                    )
                    print(table)
            else:
                print(f"[red]✗ {result.get('message', 'Optimization failed')}[/red]")

    except Exception as e:
        print(f"[red]Error during optimization: {e}[/red]")
        print("[dim]Check that Ollama is running and models are available.[/dim]")

if __name__ == "__main__":
    app()
