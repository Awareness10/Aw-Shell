"""cava's FIFO and config live in the private runtime folder, not /tmp."""

import configparser

import config.paths as paths


def _read(path):
    config = configparser.ConfigParser()
    config.read(path)
    return config


def test_config_points_cava_at_our_fifo(sandbox):
    from modules.cavalcade import write_cava_config

    written = write_cava_config()
    assert written == str(paths.CAVA_CONFIG)
    assert paths.CAVA_CONFIG.is_relative_to(sandbox.runtime)
    config = _read(written)
    assert config["output"]["raw_target"] == str(paths.CAVA_FIFO)
    template = _read(paths.CAVA_TEMPLATE)
    assert config["general"]["bars"] == template["general"]["bars"]
    assert config["output"]["method"] == "raw"


def test_shipped_template_is_untouched():
    # Written to the runtime folder; the code folder may be read-only
    assert "raw_target = /tmp/cava.fifo" in paths.CAVA_TEMPLATE.read_text()


def test_spectrum_uses_the_runtime_fifo(sandbox):
    from modules.cavalcade import Cava

    cava = Cava()  # creates the FIFO; doesn't start cava
    assert cava.path == str(paths.CAVA_FIFO)
    assert cava.cava_config_file == str(paths.CAVA_CONFIG)
    assert paths.CAVA_FIFO.is_fifo()
