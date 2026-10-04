"""Tests for deep_update - Recursive dict merge."""

from config.settings_utils import deep_update


class TestDeepUpdateFlat:

    def test_simple_override(self):
        target = {"a": 1, "b": 2}
        deep_update(target, {"b": 3})
        assert target == {"a": 1, "b": 3}

    def test_adds_new_keys(self):
        target = {"a": 1}
        deep_update(target, {"b": 2})
        assert target == {"a": 1, "b": 2}

    def test_empty_update(self):
        target = {"a": 1}
        deep_update(target, {})
        assert target == {"a": 1}

    def test_empty_target(self):
        target = {}
        deep_update(target, {"a": 1})
        assert target == {"a": 1}

    def test_returns_target(self):
        target = {"a": 1}
        result = deep_update(target, {"b": 2})
        assert result is target


class TestDeepUpdateNested:

    def test_nested_dict_merged(self):
        target = {"a": {"x": 1, "y": 2}}
        deep_update(target, {"a": {"y": 3}})
        assert target == {"a": {"x": 1, "y": 3}}

    def test_deeply_nested(self):
        target = {"a": {"b": {"c": 1, "d": 2}}}
        deep_update(target, {"a": {"b": {"c": 99}}})
        assert target == {"a": {"b": {"c": 99, "d": 2}}}

    def test_nested_adds_new_subkeys(self):
        target = {"a": {"x": 1}}
        deep_update(target, {"a": {"y": 2}})
        assert target == {"a": {"x": 1, "y": 2}}

    def test_dict_replaced_by_non_dict(self):
        target = {"a": {"x": 1}}
        deep_update(target, {"a": "string"})
        assert target == {"a": "string"}

    def test_non_dict_replaced_by_dict(self):
        target = {"a": "string"}
        deep_update(target, {"a": {"x": 1}})
        assert target == {"a": {"x": 1}}


class TestDeepUpdateEdgeCases:

    def test_list_values_replaced_not_merged(self):
        target = {"a": [1, 2]}
        deep_update(target, {"a": [3, 4]})
        assert target == {"a": [3, 4]}

    def test_none_value_override(self):
        target = {"a": 1}
        deep_update(target, {"a": None})
        assert target == {"a": None}

    def test_bool_value_override(self):
        target = {"enabled": True}
        deep_update(target, {"enabled": False})
        assert target == {"enabled": False}

    def test_mixed_types_in_nested(self):
        target = {
            "metrics_visible": {"cpu": True, "ram": True},
            "bar_theme": "Pills",
        }
        deep_update(target, {
            "metrics_visible": {"cpu": False},
            "bar_theme": "Dense",
        })
        assert target == {
            "metrics_visible": {"cpu": False, "ram": True},
            "bar_theme": "Dense",
        }
