import pytest

from ai_subtitle_studio.domain.errors import InvalidMediaError
from ai_subtitle_studio.media.probe import parse_probe


def test_rational_fps_indexes_and_pts():
    info = parse_probe(
        {
            "format": {"duration": "12.3456", "start_time": "-0.125"},
            "streams": [
                {"index": 0, "codec_type": "video", "avg_frame_rate": "24000/1001"},
                {
                    "index": 3,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "tags": {"language": "jpn", "title": "日本語"},
                    "start_time": "0.25",
                },
                {"index": 7, "codec_type": "subtitle", "codec_name": "ass"},
            ],
        }
    )
    assert (info.duration_ms, info.fps_num, info.fps_den) == (12346, 24000, 1001)
    assert info.start_time_ms == -125
    assert info.audio_tracks[0].stream_index == 3
    assert info.audio_tracks[0].start_time_ms == 250
    assert info.audio_tracks[0].language == "jpn"
    assert info.subtitle_tracks[0].stream_index == 7


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"streams": []},
        {"streams": [], "format": {"duration": "NaN"}},
        {"streams": [], "format": {"duration": "-1"}},
        {"streams": None, "format": {"duration": "1"}},
    ],
)
def test_bad_metadata(payload):
    with pytest.raises(InvalidMediaError):
        parse_probe(payload)


def test_unknown_fps_not_zero():
    info = parse_probe(
        {
            "format": {"duration": "0"},
            "streams": [
                {"index": 0, "codec_type": "video", "avg_frame_rate": "0/0", "r_frame_rate": "0/0"}
            ],
        }
    )
    assert info.fps_num is None
    assert info.duration_ms == 0
