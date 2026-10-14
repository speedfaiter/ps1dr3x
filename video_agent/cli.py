"""Typer-based CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import config, logging_utils, renderer
from .agent import AgentError, run
from .probe import ProbeError, probe

app = typer.Typer(add_completion=False, help="AI-powered video editing agent driven by Claude.")
console = Console()


@app.command()
def edit(
    input: Path = typer.Argument(..., exists=True, readable=True, help="Input video file."),
    instruction: str = typer.Argument(..., help="Natural-language edit instruction."),
    output: Path = typer.Option(Path("out.mp4"), "--output", "-o", help="Output video path."),
    model: str = typer.Option(config.DEFAULT_MODEL, "--model", help="Claude model id."),
    resolution: str = typer.Option(
        "source", "--resolution", help="1080p | 720p | 480p | source"
    ),
    lang: str = typer.Option(None, "--lang", help="Interface language: he or en"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the ffmpeg command without rendering."),
) -> None:
    """Edit a video with a single natural-language instruction."""
    try:
        result = run(instruction, source=input, output_path=output, model=model, dry_run=dry_run)
    except (AgentError, ProbeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e

    out_path = result.rendered.get("output_path", str(output))
    size = result.rendered.get("size_mb", 0.0)
    logging_utils.say("render_done", logging_utils.resolve_lang(lang), path=out_path, size=size)
    if result.assistant_text:
        console.print(f"\n[dim]{result.assistant_text}[/dim]")


@app.command()
def interactive(
    input: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(Path("out.mp4"), "--output", "-o"),
    model: str = typer.Option(config.DEFAULT_MODEL, "--model"),
    lang: str = typer.Option(None, "--lang"),
) -> None:
    """Interactive REPL. Type instructions one at a time; type 'render' to finish."""
    console.print(
        "[bold]Interactive mode.[/bold] Type instructions. 'render' to finish, 'quit' to abort."
    )
    accumulated_instructions: list[str] = []
    while True:
        try:
            line = typer.prompt("> ", default="", show_default=False)
        except (KeyboardInterrupt, EOFError):
            console.print("\nAborted.")
            raise typer.Exit(code=1)
        line = line.strip()
        if not line:
            continue
        if line.lower() in ("quit", "exit"):
            raise typer.Exit(code=0)
        if line.lower() == "render":
            if not accumulated_instructions:
                console.print("[yellow]No instructions given yet.[/yellow]")
                continue
            joined = ". ".join(accumulated_instructions) + ". Now render."
            try:
                result = run(joined, source=input, output_path=output, model=model)
            except (AgentError, ProbeError) as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(code=1) from e
            logging_utils.say(
                "render_done",
                logging_utils.resolve_lang(lang),
                path=result.rendered.get("output_path", str(output)),
                size=result.rendered.get("size_mb", 0.0),
            )
            if result.assistant_text:
                console.print(f"\n[dim]{result.assistant_text}[/dim]")
            raise typer.Exit(code=0)
        accumulated_instructions.append(line)
        console.print(f"[dim]queued ({len(accumulated_instructions)}):[/dim] {line}")


@app.command("probe")
def probe_cmd(input: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Print a summary of a media file."""
    try:
        info = probe(input)
    except ProbeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e
    data = {
        "source": str(info.source),
        "duration_seconds": round(info.duration, 3),
        "resolution": f"{info.width}x{info.height}",
        "fps": round(info.fps, 3),
        "has_audio": info.has_audio,
    }
    console.print_json(data=data)


@app.command("list-filters")
def list_filters() -> None:
    """List the built-in filter presets."""
    table = Table(title="Filter presets")
    table.add_column("name", style="cyan")
    table.add_column("ffmpeg chain")
    for name, chain in renderer.FILTER_PRESETS.items():
        table.add_row(name, chain)
    console.print(table)


@app.command()
def selftest() -> None:
    """Run the end-to-end self-test (requires ffmpeg; API not needed)."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        sample = Path(tmpdir) / "sample.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-shortest", str(sample),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            console.print("[red]ffmpeg sample generation failed:[/red]")
            console.print(proc.stderr)
            raise typer.Exit(code=1)

        from .timeline import Op, Timeline
        from .renderer import render as render_fn

        info = probe(sample)
        tl = Timeline(clip=info)
        tl.add(Op(kind="trim", args={"start": 1.0, "end": 3.0}))
        tl.add(Op(kind="filter", args={"name": "bw"}))
        out = Path(tmpdir) / "out.mp4"
        result = render_fn(tl, out)
        out_info = probe(out)
        duration_ok = abs(out_info.duration - 2.0) < 0.2
        console.print_json(data={
            "sample": str(sample),
            "output": result,
            "output_duration": out_info.duration,
            "duration_matches": duration_ok,
        })
        if not duration_ok:
            raise typer.Exit(code=1)
    console.print("[green]Selftest passed.[/green]")


if __name__ == "__main__":
    app()
