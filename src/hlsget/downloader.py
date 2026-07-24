from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
import m3u8
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)


class DownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Job:
    url: str
    path: Path
    range_start: int | None = None
    range_length: int | None = None


class HLSDownloader:
    def __init__(
        self,
        *,
        url: str,
        output: Path,
        quality: str,
        workers: int,
        headers: dict[str, str],
        retries: int,
        timeout: float,
        keep_temp: bool,
        overwrite: bool,
        console: Console,
    ) -> None:
        self.url = url
        self.output = output.expanduser().resolve()
        self.quality = quality.lower()
        self.workers = workers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            **headers,
        }
        self.retries = retries
        self.timeout = timeout
        self.keep_temp = keep_temp
        self.overwrite = overwrite
        self.console = console
        token = hashlib.sha256(url.encode()).hexdigest()[:12]
        
        # Strictly confined snaps cannot create arbitrary hidden directories in
        # the user's home. Keep resumable state in Snap's writable data area
        # when available, and next to the output for regular installations.
        
        snap_user_common = os.environ.get("SNAP_USER_COMMON")
        if snap_user_common:
            self.workdir = (
                Path(snap_user_common) / "work" / f"{self.output.name}-{token}"
            )
        else:
            self.workdir = self.output.parent / f".{self.output.name}.hlsget-{token}"
        self._progress_lock = threading.Lock()

    def run(self) -> Path:
        self._validate_environment()
        self.workdir.mkdir(parents=True, exist_ok=True)
        segments_dir = self.workdir / "segments"
        keys_dir = self.workdir / "keys"
        segments_dir.mkdir(exist_ok=True)
        keys_dir.mkdir(exist_ok=True)

        limits = httpx.Limits(
            max_connections=max(self.workers + 2, 10),
            max_keepalive_connections=max(self.workers, 8),
        )
        with httpx.Client(
            headers=self.headers,
            follow_redirects=True,
            timeout=httpx.Timeout(self.timeout),
            limits=limits,
        ) as client:
            playlist, selected = self._resolve_playlist(client)
            self.console.print(
                f"[cyan]Playlist:[/cyan] {selected}; {len(playlist.segments)} segments"
            )
            jobs = self._prepare_jobs(playlist, segments_dir, keys_dir)
            self._download_jobs(client, jobs)

        local_manifest = self.workdir / "playlist.m3u8"
        local_manifest.write_text(playlist.dumps(), encoding="utf-8")
        self._mux(local_manifest)

        if not self.keep_temp:
            shutil.rmtree(self.workdir, ignore_errors=True)
        return self.output

    def _validate_environment(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise DownloadError("FFmpeg was not found. Install it with: sudo apt install ffmpeg")
        if self.output.exists() and not self.overwrite:
            raise DownloadError(
                f"Output already exists: {self.output}. Use --overwrite to replace it."
            )
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def _fetch_manifest(self, client: httpx.Client, url: str):
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DownloadError(f"Could not load playlist {url}: {exc}") from exc
        if "#EXTM3U" not in response.text[:1024]:
            raise DownloadError("The server response is not an HLS playlist.")
        return m3u8.loads(response.text, uri=str(response.url))

    def _resolve_playlist(self, client: httpx.Client):
        playlist = self._fetch_manifest(client, self.url)
        if not playlist.is_variant:
            return playlist, "media"
        if not playlist.playlists:
            raise DownloadError("Master playlist contains no video variants.")

        candidates = list(playlist.playlists)
        chosen = self._choose_variant(candidates)
        info = chosen.stream_info
        resolution = getattr(info, "resolution", None)
        label = f"{resolution[1]}p" if resolution else f"{info.bandwidth or 0} bps"
        media = self._fetch_manifest(client, chosen.absolute_uri)
        return media, label

    def _choose_variant(self, variants):
        def height(item) -> int:
            resolution = getattr(item.stream_info, "resolution", None)
            return int(resolution[1]) if resolution else 0

        def score(item) -> tuple[int, int]:
            return height(item), int(item.stream_info.bandwidth or 0)

        if self.quality == "best":
            return max(variants, key=score)
        if self.quality == "worst":
            return min(variants, key=score)
        try:
            target = int(self.quality.removesuffix("p"))
        except ValueError as exc:
            raise DownloadError("Quality must be best, worst, or a height such as 720.") from exc
        return min(variants, key=lambda item: (abs(height(item) - target), -score(item)[1]))

    @staticmethod
    def _extension(url: str, fallback: str) -> str:
        suffix = Path(unquote(urlparse(url).path)).suffix
        if not suffix or len(suffix) > 8 or not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
            return fallback
        return suffix

    @staticmethod
    def _parse_byterange(value: str | None, previous_end: int | None) -> tuple[int | None, int | None, int | None]:
        if not value:
            return None, None, previous_end
        length_text, separator, offset_text = value.partition("@")
        length = int(length_text)
        if separator:
            start = int(offset_text)
        elif previous_end is not None:
            start = previous_end
        else:
            start = 0
        return start, length, start + length

    def _prepare_jobs(self, playlist, segments_dir: Path, keys_dir: Path) -> list[Job]:
        jobs: list[Job] = []
        previous_ranges: dict[str, int] = {}
        key_paths: dict[str, Path] = {}
        key_object_paths: dict[int, Path] = {}
        map_paths: dict[tuple[str, str | None], Path] = {}
        map_object_paths: dict[int, Path] = {}

        for index, segment in enumerate(playlist.segments):
            source = segment.absolute_uri
            if not source:
                raise DownloadError(f"Segment {index} has no URI.")
            start, length, end = self._parse_byterange(
                getattr(segment, "byterange", None), previous_ranges.get(source)
            )
            if end is not None:
                previous_ranges[source] = end
            ext = self._extension(source, ".ts")
            destination = segments_dir / f"{index:06d}{ext}"
            jobs.append(Job(source, destination, start, length))
            segment.uri = destination.relative_to(self.workdir).as_posix()

            init_section = getattr(segment, "init_section", None)
            if init_section and init_section.absolute_uri:
                object_id = id(init_section)
                if object_id not in map_object_paths:
                    map_source = init_section.absolute_uri
                    map_range = getattr(init_section, "byterange", None)
                    map_key = (map_source, map_range)
                    if map_key not in map_paths:
                        map_destination = segments_dir / f"init-{len(map_paths):03d}{self._extension(map_source, '.mp4')}"
                        map_start, map_length, _ = self._parse_byterange(map_range, None)
                        map_paths[map_key] = map_destination
                        jobs.append(Job(map_source, map_destination, map_start, map_length))
                    map_object_paths[object_id] = map_paths[map_key]
                init_section.uri = map_object_paths[object_id].relative_to(self.workdir).as_posix()

            key = getattr(segment, "key", None)
            if key and key.method and key.method.upper() != "NONE":
                if key.method.upper() != "AES-128":
                    raise DownloadError(
                        f"Unsupported encryption method: {key.method}. DRM/SAMPLE-AES is not supported."
                    )
                object_id = id(key)
                if object_id not in key_object_paths:
                    key_source = key.absolute_uri
                    if not key_source:
                        raise DownloadError("Encrypted segment has no accessible key URI.")
                    if key_source not in key_paths:
                        key_destination = keys_dir / f"key-{len(key_paths):03d}.bin"
                        key_paths[key_source] = key_destination
                        jobs.append(Job(key_source, key_destination))
                    key_object_paths[object_id] = key_paths[key_source]
                key.uri = key_object_paths[object_id].relative_to(self.workdir).as_posix()

        if not playlist.segments:
            raise DownloadError("Media playlist contains no segments.")
        return jobs

    def _download_jobs(self, client: httpx.Client, jobs: list[Job]) -> None:
        pending = [job for job in jobs if not job.path.exists() or job.path.stat().st_size == 0]
        reused = len(jobs) - len(pending)
        if reused:
            self.console.print(f"[green]Resume:[/green] reusing {reused} existing files")
        if not pending:
            return

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.fields[downloaded]}") ,
            TimeRemainingColumn(),
            console=self.console,
        )
        with progress:
            task_id = progress.add_task("Downloading", total=len(pending), downloaded="0 B")
            total_bytes = 0

            def add_bytes(amount: int) -> None:
                nonlocal total_bytes
                with self._progress_lock:
                    total_bytes += amount
                    progress.update(task_id, downloaded=self._human_size(total_bytes))

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(self._download_one, client, job, add_bytes): job
                    for job in pending
                }
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        for other in futures:
                            other.cancel()
                        raise DownloadError(f"Failed to download {job.url}: {exc}") from exc
                    progress.advance(task_id)

    def _download_one(self, client: httpx.Client, job: Job, add_bytes) -> None:
        if job.path.exists() and job.path.stat().st_size > 0:
            return
        part = job.path.with_suffix(job.path.suffix + ".part")
        request_headers: dict[str, str] = {}
        if job.range_start is not None and job.range_length is not None:
            end = job.range_start + job.range_length - 1
            request_headers["Range"] = f"bytes={job.range_start}-{end}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                part.unlink(missing_ok=True)
                with client.stream("GET", job.url, headers=request_headers) as response:
                    response.raise_for_status()
                    with part.open("wb") as file:
                        for chunk in response.iter_bytes(128 * 1024):
                            file.write(chunk)
                            add_bytes(len(chunk))
                if job.range_length is not None and part.stat().st_size != job.range_length:
                    raise IOError(
                        f"byte range size mismatch: expected {job.range_length}, got {part.stat().st_size}"
                    )
                os.replace(part, job.path)
                return
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                part.unlink(missing_ok=True)
                if attempt < self.retries:
                    time.sleep(min(2**attempt, 8))
        assert last_error is not None
        raise last_error

    def _mux(self, manifest: Path) -> None:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-protocol_whitelist",
            "file,crypto,data",
            "-allowed_extensions",
            "ALL",
            "-i",
            str(manifest),
            "-map",
            "0",
            "-c",
            "copy",
        ]
        if self.output.suffix.lower() in {".mp4", ".m4v", ".mov"}:
            command.extend(["-movflags", "+faststart"])
        command.extend(["-y" if self.overwrite else "-n", str(self.output)])
        self.console.print("[cyan]Muxing with FFmpeg…[/cyan]")
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode != 0:
            tail = "\n".join(result.stderr.strip().splitlines()[-12:])
            raise DownloadError(
                f"FFmpeg could not create the output. Temporary files were kept.\n{tail}"
            )

    @staticmethod
    def _human_size(value: int) -> str:
        size = float(value)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if size < 1024 or unit == "GiB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GiB"
