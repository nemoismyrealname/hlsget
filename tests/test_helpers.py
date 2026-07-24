from pathlib import Path

from rich.console import Console

from hlsget.downloader import HLSDownloader


def make_downloader(tmp_path: Path) -> HLSDownloader:
    return HLSDownloader(
        url="https://example.test/master.m3u8",
        output=tmp_path / "out.mp4",
        quality="best",
        workers=4,
        headers={},
        retries=1,
        timeout=5,
        keep_temp=True,
        overwrite=False,
        console=Console(),
    )


def test_byterange_with_explicit_offset():
    assert HLSDownloader._parse_byterange("100@25", None) == (25, 100, 125)


def test_byterange_with_implicit_offset():
    assert HLSDownloader._parse_byterange("100", 125) == (125, 100, 225)


def test_extension_fallback():
    assert HLSDownloader._extension("https://e.test/chunk", ".ts") == ".ts"
    assert HLSDownloader._extension("https://e.test/chunk.m4s?q=1", ".ts") == ".m4s"


def test_quality_selection(tmp_path):
    import m3u8

    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=1280x720
720.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1920x1080
1080.m3u8
""",
        uri="https://example.test/master.m3u8",
    )
    downloader = make_downloader(tmp_path)
    assert downloader._choose_variant(playlist.playlists).stream_info.resolution[1] == 1080
