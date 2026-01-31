"""Tests for pure functions in utils/functions.py."""

import pytest
from utils.functions import (
    format_time,
    convert_bytes,
    get_relative_time,
    convert_to_percent,
    merge_defaults,
    exclude_keys,
    unique_list,
    convert_seconds_to_milliseconds,
    parse_markup,
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
