"""
Main optimization loop.

Usage:
  uv run python orchestrator.py \\
    --rulebook ~/Downloads/f1_2026_technical_regs.pdf \\
    --base-model ~/Downloads/f1_2026_car.obj \\
    --hours 12

Before running:
  1. Blender must be open with the base model loaded and MCP server started
  2. Run setup_model.py once to name the wing/diffuser objects
  3. Google Drive for Desktop must be running and synced
  4. Start the Colab and Kaggle CFD worker notebooks
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

import rule_checker
from blender_bridge import BlenderBridge
from drive_sync import DriveSync
from llm_agent import DesignAgent
from scorer import format_results

console = Console()
OUTPUT_DIR = Path("output")


def make_job_id(iteration: int, variant: str) -> str:
    short = uuid.uuid4().hex[:6]
    return f"iter{iteration:04d}_{variant}_{short}"


def print_scoreboard(history: list) -> None:
    if not history:
        return
    table = Table(title="Design History", show_lines=True)
    table.add_column("Iter", justify="right")
    table.add_column("Var")
    table.add_column("Score", justify="right")
    table.add_column("CL", justify="right")
    table.add_column("CD", justify="right")
    table.add_column("Note")
    for h in history[-15:]:
        note = "[bold green]BEST[/]" if h.get("is_best") else ""
        table.add_row(
            str(h["iteration"]),
            h["variant"],
            f"{h['score']:.3f}",
            f"{h['results']['cl']:.4f}",
            f"{h['results']['cd']:.4f}",
            note,
        )
    console.print(table)


@click.command()
@click.option("--rulebook", required=True, type=click.Path(exists=True, path_type=Path), help="Path to F1 2026 technical regulations PDF")
@click.option("--base-model", required=True, type=click.Path(exists=True, path_type=Path), help="Path to base F1 car .obj/.fbx/.blend")
@click.option("--hours", default=12.0, show_default=True, help="How long to run the optimization loop")
@click.option("--cfd-timeout", default=1200, show_default=True, help="Seconds to wait for CFD results before skipping")
def main(rulebook: Path, base_model: Path, hours: float, cfd_timeout: int):
    OUTPUT_DIR.mkdir(exist_ok=True)

    console.rule("[bold]F1 Aero Optimization Loop[/]")
    console.print(f"Rulebook:   {rulebook}")
    console.print(f"Base model: {base_model}")
    console.print(f"Duration:   {hours} hours")
    console.print(f"CFD timeout: {cfd_timeout}s per job\n")

    # ── Init components ──────────────────────────────────────────────
    console.print("[bold cyan]Connecting to Blender...[/]")
    blender = BlenderBridge()
    if not blender.ping():
        console.print("[bold red]Cannot reach Blender MCP server. Aborting.[/]")
        raise SystemExit(1)

    console.print("[bold cyan]Loading model into Blender...[/]")
    blender.load_model(base_model)

    console.print("[bold cyan]Connecting to Google Drive...[/]")
    drive = DriveSync()

    console.print("[bold cyan]Loading LLM agent...[/]")
    agent = DesignAgent(rulebook)

    # ── Main loop ────────────────────────────────────────────────────
    current_params = dict(rule_checker.DEFAULT_PARAMS)
    best_score = -float("inf")
    best_params = None
    history: list[dict] = []
    end_time = datetime.now() + timedelta(hours=hours)
    iteration = 0

    console.print("\n[bold green]Starting optimization loop...[/]")
    console.print(f"Will run until: {end_time.strftime('%H:%M:%S')}\n")

    while datetime.now() < end_time:
        iteration += 1
        remaining = end_time - datetime.now()
        console.rule(f"[bold]Iteration {iteration}[/]  ({str(remaining).split('.')[0]} remaining)")

        # ── Ask LLM for proposals ─────────────────────────────────
        console.print("[cyan]Asking LLM for design proposals...[/]")
        try:
            proposals = agent.propose(current_params, history)
        except Exception as e:
            console.print(f"[red]LLM error: {e}. Skipping iteration.[/]")
            time.sleep(30)
            continue

        jobs = [
            ("A", proposals["variant_a"]),
            ("B", proposals["variant_b"]),
        ]

        submitted: list[tuple[str, str, dict]] = []  # (variant, job_id, proposal)

        for variant, proposal in jobs:
            params = proposal["parameters"]
            console.print(f"\n  Variant {variant}: {proposal.get('reasoning', '')[:120]}")

            # Rule check
            violations = rule_checker.check(params)
            if violations:
                console.print(f"  [yellow]Rule violations — clamping:[/]")
                for v in violations:
                    console.print(f"    {v.message}")
                params = rule_checker.clamp_to_legal(params)

            # Apply in Blender and export
            try:
                blender.reset_to_base()
                blender.apply_params(params)
                job_id = make_job_id(iteration, variant)
                mesh_path = blender.export_stl(job_id, OUTPUT_DIR)
                console.print(f"  Exported mesh: {mesh_path.name} ({mesh_path.stat().st_size // 1024} KB)")
            except Exception as e:
                console.print(f"  [red]Blender error: {e}[/]")
                continue

            # Submit to Drive
            drive.submit_job(mesh_path, params, job_id)
            console.print(f"  Submitted job {job_id} to Drive queue")
            submitted.append((variant, job_id, proposal, params))

        # ── Wait for CFD results ──────────────────────────────────
        for variant, job_id, proposal, params in submitted:
            console.print(f"\n  Waiting for CFD results: {job_id}...")
            results = drive.wait_for_result(job_id, timeout=cfd_timeout)

            if results is None:
                console.print(f"  [red]Timeout waiting for {job_id}. CFD worker may be disconnected.[/]")
                continue

            score = results.get("score", 0.0)
            is_best = score > best_score

            entry = {
                "iteration": iteration,
                "variant": variant,
                "job_id": job_id,
                "params": params,
                "proposal": proposal,
                "results": results,
                "score": score,
                "is_best": is_best,
                "timestamp": datetime.now().isoformat(),
            }
            history.append(entry)

            console.print(f"  Result: {format_results(results)}")

            if is_best:
                best_score = score
                best_params = params
                drive.save_best(OUTPUT_DIR / f"{job_id}.stl", params, results)
                console.print(f"  [bold green]NEW BEST! Score={score:.3f}[/]")
                # Update current_params to the best found so far
                current_params = dict(params)

        # Save history after each iteration
        drive.save_history(history)
        print_scoreboard(history)

    # ── Final report ─────────────────────────────────────────────────
    console.rule("[bold green]Optimization Complete[/]")
    console.print(f"Iterations completed: {iteration}")
    console.print(f"Best score (CL/CD): {best_score:.3f}")
    if best_params:
        console.print(f"Best parameters:\n{json.dumps(best_params, indent=2)}")
    console.print(f"\nBest design saved to: {drive.best}/best_design.stl")
    console.print(f"Full history: {drive.history_file}")


if __name__ == "__main__":
    main()
