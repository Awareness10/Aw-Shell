def wifi_level(bitrate_mbps: int, strength: int) -> int:
    """Connection quality 0-3 from the link speed; signal strength if the speed is unknown.

    Signal % alone is misleading: a strong but slow link (2.4 GHz, 20 MHz) can show 100%
    while a fast 160 MHz link shows ~70%.
    """
    if bitrate_mbps > 0:
        return 3 if bitrate_mbps >= 600 else 2 if bitrate_mbps >= 200 else 1 if bitrate_mbps >= 50 else 0
    return 3 if strength >= 75 else 2 if strength >= 50 else 1 if strength >= 25 else 0
