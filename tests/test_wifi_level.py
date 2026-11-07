import pytest

from utils.wifi import wifi_level


@pytest.mark.parametrize(
    "bitrate, strength, level",
    [
        (1729, 71, 3),  # fast 160 MHz link with "only" 71% signal -> full bars
        (600, 10, 3),
        (599, 100, 2),
        (200, 100, 2),
        (144, 100, 1),  # strong but slow 2.4 GHz link
        (50, 100, 1),
        (49, 100, 0),
        (0, 80, 3),  # speed unknown -> fall back to signal strength
        (0, 60, 2),
        (0, 30, 1),
        (0, 10, 0),
    ],
)
def test_wifi_level(bitrate, strength, level):
    assert wifi_level(bitrate, strength) == level
