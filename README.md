# hlsget

`hlsget` is a small command-line tool for downloading an authorized HLS stream
from a direct `.m3u8` link. It downloads media segments concurrently, shows a
clear progress bar, and asks FFmpeg to assemble the final video without
re-encoding it.

> Use `hlsget` only for streams you own or are allowed to download. It does not
> discover links on websites, bypass DRM, or unlock protected content.

## Quick start

Once the app is published in the Snap Store, installation will take one command:

```bash
sudo snap install hlsget
```

Download a stream into the current directory:

```bash
hlsget 'https://example.com/master.m3u8'
```

By default, `hlsget`:

- selects the best available video quality;
- uses 8 concurrent downloads;
- saves the result as `video.mp4`;
- keeps completed segments after an error so the next run can resume.

Choose a different file name or location:

```bash
hlsget 'https://example.com/master.m3u8' -o ~/Videos/movie.mp4
```

## Streams that require request headers

Some servers check which page the request came from. Pass that page with
`--referer`:

```bash
hlsget 'M3U8_URL' \
  --referer 'https://example.com/video' \
  -o movie.mp4
```

You can repeat `--header` for additional HTTP headers:

```bash
hlsget 'M3U8_URL' \
  -H 'Origin: https://example.com' \
  -H 'Cookie: name=value' \
  -o movie.mkv
```

Be careful with cookies and access tokens. A command containing them may remain
in your terminal history. Never publish them in an issue, screenshot, or log.

## Common options

```text
-o, --output FILE       Output file name and location
-q, --quality VALUE     best, worst, or a height such as 720 or 1080
-w, --workers NUMBER    Concurrent downloads; the default is 8
-H, --header HEADER     Additional HTTP header; can be repeated
--referer URL           Source page sent in the Referer header
--retries NUMBER        Retry attempts for each resource
--keep-temp             Keep segments after a successful download
-y, --overwrite         Replace an existing output file
--version               Print the installed version
```

If a server responds with `429 Too Many Requests`, lower the worker count:

```bash
hlsget 'M3U8_URL' --workers 4
```

## Where files are saved

Relative output paths start in the directory where you run the command:

```bash
cd ~/Downloads
hlsget 'M3U8_URL'
```

The result will be `~/Downloads/video.mp4`.

The strictly confined Snap can write to normal, non-hidden folders inside your
home directory. External drives are not enabled in the first Snap release.

## Supported today

- direct HLS master and media playlists;
- best, worst, or nearest requested resolution;
- concurrent downloads, retries, and basic resume;
- MPEG-TS and fragmented MP4 segments;
- `EXT-X-MAP` and byte-range resources;
- ordinary HLS AES-128 encryption;
- MP4 and MKV remuxing through bundled FFmpeg.

## Not supported yet

- finding the playlist URL on a web page;
- live-stream polling;
- separate external audio or subtitle renditions;
- DRM and SAMPLE-AES;
- downloading content without the required authorization.

## Troubleshooting

### `401 Unauthorized` or `403 Forbidden`

The signed URL may have expired, or the server may require the browser's
`Referer`, `Origin`, or authorized session cookies. Capture a fresh playlist URL
and pass only the headers you are permitted to use.

### `429 Too Many Requests`

Try `--workers 4` or `--workers 2`. More connections do not always mean a faster
download.

### The output has no audio

The master playlist probably points to a separate audio rendition. The current
version does not download external audio tracks yet.

### FFmpeg reports an error

Temporary resources are kept after a failed run. Run the same command again
with the same URL and output path to reuse completed downloads.

### The player cannot open the file

Inspect the result with:

```bash
ffprobe -v error \
  -show_entries stream=codec_type,codec_name \
  -show_entries format=duration,size \
  video.mp4
```

## Development setup

Snap is the intended installation method for end users. Contributors can run
the project from source:

```bash
sudo apt install python3 python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
hlsget --help
```

See [`SNAPCRAFT.md`](SNAPCRAFT.md) for the release process and
[`PRIVACY.md`](PRIVACY.md) for the privacy statement. The project is licensed
under the MIT License.
