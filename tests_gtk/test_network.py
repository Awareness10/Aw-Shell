"""Which network device is primary, from NetworkManager's primary connection."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.network import NetworkClient


def _client(connection_type):
    client = MagicMock(name="NM.Client")
    if connection_type is None:
        client.get_primary_connection.return_value = None  # offline
    else:
        client.get_primary_connection.return_value.get_connection_type.return_value = \
            connection_type
    return SimpleNamespace(_client=client)


@pytest.mark.parametrize("connection_type, expected", [
    ("802-11-wireless", "wifi"),
    ("802-3-ethernet", "wired"),
    ("vpn", None),
    (None, None),  # no primary connection: offline
])
def test_primary_device(connection_type, expected):
    assert NetworkClient._get_primary_device(_client(connection_type)) == expected


def test_no_networkmanager_client():
    assert NetworkClient._get_primary_device(SimpleNamespace(_client=None)) is None
