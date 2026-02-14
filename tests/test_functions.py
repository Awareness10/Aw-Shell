"""Tests for pure functions in utils/functions.py."""

import os
from unittest.mock import patch, MagicMock

import pytest
from utils.functions import (
    ExecutableNotFoundError,
    format_time,
    convert_bytes,
    get_relative_time,
    convert_to_percent,
    merge_defaults,
    exclude_keys,
    unique_list,
    convert_seconds_to_milliseconds,
    parse_markup,
    validate_widgets,
    executable_exists,
    ensure_dir_exists,
    send_notification,
    uptime,
)


# =========================================================================
# format_time
# =========================================================================

class TestFormatTime:

    def test_zero_seconds(self):
        assert format_time(0) == "0 h 00 min"

    def test_one_hour(self):
        assert format_time(3600) == "1 h 00 min"

    def test_one_hour_thirty_min(self):
        assert format_time(5400) == "1 h 30 min"

    def test_partial_minutes_truncated(self):
        # 90 seconds = 1 min 30 sec -> 0 h 01 min (seconds ignored)
        assert format_time(90) == "0 h 01 min"

    def test_large_value(self):
        # 48 hours
        assert format_time(48 * 3600) == "48 h 00 min"

    def test_59_minutes(self):
        assert format_time(59 * 60) == "0 h 59 min"


# =========================================================================
# convert_bytes
# =========================================================================

class TestConvertBytes:

    def test_to_kb(self):
        assert convert_bytes(1024, "kb") == "1.0KB"

    def test_to_mb(self):
        assert convert_bytes(1048576, "mb") == "1.0MB"

    def test_to_gb(self):
        assert convert_bytes(1073741824, "gb") == "1.0GB"

    def test_zero_bytes(self):
        assert convert_bytes(0, "kb") == "0.0KB"

    def test_custom_format_spec(self):
        assert convert_bytes(1536, "kb", ".2f") == "1.50KB"

    def test_fractional_mb(self):
        result = convert_bytes(500000, "mb")
        assert result.endswith("MB")
        assert float(result[:-2]) == pytest.approx(0.5, abs=0.1)


# =========================================================================
# get_relative_time
# =========================================================================

class TestGetRelativeTime:

    def test_now(self):
        assert get_relative_time(0) == "now"

    def test_one_minute(self):
        assert get_relative_time(1) == "1 minute ago"

    def test_two_minutes(self):
        assert get_relative_time(2) == "2 minutes ago"

    def test_59_minutes(self):
        assert get_relative_time(59) == "59 minutes ago"

    def test_one_hour(self):
        assert get_relative_time(60) == "1 hour ago"

    def test_two_hours(self):
        assert get_relative_time(120) == "2 hours ago"

    def test_23_hours(self):
        assert get_relative_time(23 * 60) == "23 hours ago"

    def test_one_day(self):
        assert get_relative_time(1440) == "1 day ago"

    def test_two_days(self):
        assert get_relative_time(2880) == "2 days ago"

    def test_large_days(self):
        result = get_relative_time(14400)  # 10 days
        assert result == "10 days ago"


# =========================================================================
# convert_to_percent
# =========================================================================

class TestConvertToPercent:

    def test_half(self):
        assert convert_to_percent(50, 100) == 50

    def test_full(self):
        assert convert_to_percent(100, 100) == 100

    def test_zero(self):
        assert convert_to_percent(0, 100) == 0

    def test_returns_int_by_default(self):
        result = convert_to_percent(1, 3)
        assert isinstance(result, int)
        assert result == 33

    def test_returns_float_when_requested(self):
        result = convert_to_percent(1, 3, is_int=False)
        assert isinstance(result, float)
        assert result == pytest.approx(33.33, abs=0.01)

    def test_over_100_percent(self):
        assert convert_to_percent(150, 100) == 150


# =========================================================================
# merge_defaults
# =========================================================================

class TestMergeDefaults:

    def test_data_overrides_defaults(self):
        defaults = {"a": 1, "b": 2}
        data = {"b": 3}
        result = merge_defaults(data, defaults)
        assert result == {"a": 1, "b": 3}

    def test_empty_data_returns_defaults(self):
        defaults = {"a": 1}
        assert merge_defaults({}, defaults) == {"a": 1}

    def test_empty_defaults(self):
        assert merge_defaults({"x": 1}, {}) == {"x": 1}

    def test_data_adds_new_keys(self):
        result = merge_defaults({"c": 3}, {"a": 1})
        assert result == {"a": 1, "c": 3}

    def test_does_not_mutate_inputs(self):
        defaults = {"a": 1}
        data = {"b": 2}
        merge_defaults(data, defaults)
        assert defaults == {"a": 1}
        assert data == {"b": 2}


# =========================================================================
# exclude_keys
# =========================================================================

class TestExcludeKeys:

    def test_excludes_specified_keys(self):
        assert exclude_keys({"a": 1, "b": 2, "c": 3}, ["b"]) == {"a": 1, "c": 3}

    def test_empty_exclusion_list(self):
        d = {"a": 1}
        assert exclude_keys(d, []) == {"a": 1}

    def test_exclude_nonexistent_key(self):
        assert exclude_keys({"a": 1}, ["z"]) == {"a": 1}

    def test_exclude_all_keys(self):
        assert exclude_keys({"a": 1, "b": 2}, ["a", "b"]) == {}

    def test_does_not_mutate_input(self):
        d = {"a": 1, "b": 2}
        exclude_keys(d, ["a"])
        assert d == {"a": 1, "b": 2}


# =========================================================================
# unique_list
# =========================================================================

class TestUniqueList:

    def test_removes_duplicates(self):
        result = unique_list([1, 2, 2, 3, 3, 3])
        assert sorted(result) == [1, 2, 3]

    def test_empty_list(self):
        assert unique_list([]) == []

    def test_already_unique(self):
        result = unique_list([1, 2, 3])
        assert sorted(result) == [1, 2, 3]

    def test_strings(self):
        result = unique_list(["a", "b", "a"])
        assert sorted(result) == ["a", "b"]


# =========================================================================
# Simple helpers
# =========================================================================

class TestSimpleHelpers:

    def test_convert_seconds_to_milliseconds(self):
        assert convert_seconds_to_milliseconds(1) == 1000
        assert convert_seconds_to_milliseconds(0) == 0
        assert convert_seconds_to_milliseconds(5) == 5000

    def test_parse_markup_passthrough(self):
        assert parse_markup("hello <b>world</b>") == "hello <b>world</b>"
        assert parse_markup("") == ""


# =========================================================================
# ExecutableNotFoundError
# =========================================================================

class TestExecutableNotFoundError:

    def test_message_contains_name(self):
        err = ExecutableNotFoundError("hyprctl")
        assert "hyprctl" in str(err)

    def test_is_import_error(self):
        assert issubclass(ExecutableNotFoundError, ImportError)


# =========================================================================
# validate_widgets
# =========================================================================

class TestValidateWidgets:

    def test_valid_widgets_pass(self):
        parsed = {"layout": {"left": ["clock", "battery"], "right": ["volume"]}}
        defaults = {"clock": {}, "battery": {}, "volume": {}}
        validate_widgets(parsed, defaults)  # should not raise

    def test_invalid_widget_raises(self):
        parsed = {"layout": {"center": ["nonexistent_widget"]}}
        defaults = {"clock": {}}
        with pytest.raises(ValueError, match="nonexistent_widget"):
            validate_widgets(parsed, defaults)

    def test_empty_layout(self):
        parsed = {"layout": {"left": []}}
        validate_widgets(parsed, {})  # should not raise


# =========================================================================
# executable_exists
# =========================================================================

class TestExecutableExists:

    @patch("utils.functions.shutil.which", return_value="/usr/bin/hyprctl")
    def test_found(self, _mock):
        assert executable_exists("hyprctl") is True

    @patch("utils.functions.shutil.which", return_value=None)
    def test_not_found(self, _mock):
        assert executable_exists("nonexistent_binary") is False


# =========================================================================
# ensure_dir_exists
# =========================================================================

class TestEnsureDirExists:

    @patch("utils.functions.os.makedirs")
    @patch("utils.functions.os.path.exists", return_value=False)
    def test_creates_when_missing(self, _exists, mock_makedirs):
        ensure_dir_exists("/tmp/test_dir")
        mock_makedirs.assert_called_once_with("/tmp/test_dir")

    @patch("utils.functions.os.makedirs")
    @patch("utils.functions.os.path.exists", return_value=True)
    def test_skips_when_exists(self, _exists, mock_makedirs):
        ensure_dir_exists("/tmp/test_dir")
        mock_makedirs.assert_not_called()


# =========================================================================
# send_notification
# =========================================================================

class TestSendNotification:

    @patch("utils.functions.subprocess.run")
    def test_basic_notification(self, mock_run):
        send_notification("Title", "Body", "normal")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "notify-send"
        assert "--urgency" in cmd
        assert "normal" in cmd
        assert "Title" in cmd
        assert "Body" in cmd

    @patch("utils.functions.subprocess.run")
    def test_with_icon(self, mock_run):
        send_notification("T", "B", "low", icon="dialog-info")
        cmd = mock_run.call_args[0][0]
        assert "--icon" in cmd
        assert "dialog-info" in cmd

    @patch("utils.functions.subprocess.run")
    def test_with_timeout(self, mock_run):
        send_notification("T", "B", "critical", timeout=5000)
        cmd = mock_run.call_args[0][0]
        assert "-t" in cmd
        assert "5000" in cmd

    @patch("utils.functions.subprocess.run")
    def test_with_app_name(self, mock_run):
        send_notification("T", "B", "normal", app_name="aw-shell")
        cmd = mock_run.call_args[0][0]
        assert "--app-name" in cmd
        assert "aw-shell" in cmd

    @patch("utils.functions.subprocess.run", side_effect=__import__("subprocess").CalledProcessError(1, "notify-send"))
    def test_failure_prints_error(self, _mock, capsys):
        send_notification("T", "B", "normal")
        assert "Failed to send notification" in capsys.readouterr().out


# =========================================================================
# uptime
# =========================================================================

class TestUptime:

    @patch("utils.functions.datetime")
    @patch("utils.functions.psutil.boot_time")
    def test_uptime_format(self, mock_boot, mock_dt):
        # Simulate 2h 30m uptime
        mock_boot.return_value = 1000.0
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 1000.0 + (2 * 3600) + (30 * 60)
        mock_dt.datetime.now.return_value = mock_now
        assert uptime() == "02:30"

    @patch("utils.functions.datetime")
    @patch("utils.functions.psutil.boot_time")
    def test_uptime_zero(self, mock_boot, mock_dt):
        mock_boot.return_value = 5000.0
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 5000.0
        mock_dt.datetime.now.return_value = mock_now
        assert uptime() == "00:00"
