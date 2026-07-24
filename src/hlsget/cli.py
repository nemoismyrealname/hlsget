from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .downloader import DownloadError, HLSDownloader

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Concurrent HLS downloader. Use only with content you may download.",
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"hlsget {__version__}")
        raise typer.Exit()


def parse_headers(values: list[str], referer: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        name, separator, header_value = value.partition(":")
        if not separator or not name.strip() or not header_value.strip():
            raise typer.BadParameter(
                f"Invalid header {value!r}; expected 'Name: value'.",
                param_hint="--header",
            )
        headers[name.strip()] = header_value.strip()
    if referer:
        headers["Referer"] = referer
    return headers


@app.command()
def download(
    url: Annotated[str, typer.Argument(help="Direct master or media .m3u8 URL")],
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output .mp4 or .mkv file"),
    ] = Path("video.mp4"),
    quality: Annotated[
        str,
        typer.Option("--quality", "-q", help="best, worst, or height such as 1080"),
    ] = "best",
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", min=1, max=32, help="Parallel downloads"),
    ] = 8,
    header: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="HTTP header; repeat as needed"),
    ] = None,
    referer: Annotated[
        str | None,
        typer.Option("--referer", help="Page URL sent as the Referer header"),
    ] = None,
    retries: Annotated[
        int,
        typer.Option("--retries", min=0, max=10, help="Retries per resource"),
    ] = 4,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1, help="HTTP timeout in seconds"),
    ] = 30.0,
    keep_temp: Annotated[
        bool,
        typer.Option("--keep-temp", help="Keep segments after successful muxing"),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-y", help="Replace an existing output file"),
    ] = False,
) -> None:
    """Download an HLS VOD playlist and remux it with FFmpeg."""
    try:
        headers = parse_headers(header or [], referer)
        downloader = HLSDownloader(
            url=url,
            output=output,
            quality=quality,
            workers=workers,
            headers=headers,
            retries=retries,
            timeout=timeout,
            keep_temp=keep_temp,
            overwrite=overwrite,
            console=console,
        )
        result = downloader.run()
    except (DownloadError, typer.BadParameter) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Temporary files were kept for resume.[/yellow]")
        raise typer.Exit(130)

    console.print(f"[bold green]Saved:[/bold green] {result}")


if __name__ == "__main__":
    app()
