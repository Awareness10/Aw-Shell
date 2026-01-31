"""Tests for utils/conversion.py - Unit conversion logic."""

import pytest
from utils.conversion import Conversion, Units


@pytest.fixture
def conv():
    return Conversion()


@pytest.fixture
def units():
    return Units()


# =========================================================================
# Units chart structure tests
# =========================================================================

class TestUnitsCharts:
    """Verify chart data integrity."""

    def test_weight_chart_has_aliases(self, units):
        assert units.WEIGHT_CHART["kg"] == units.WEIGHT_CHART["kilogram"]
        assert units.WEIGHT_CHART["lb"] == units.WEIGHT_CHART["pound"]
        assert units.WEIGHT_CHART["oz"] == units.WEIGHT_CHART["ounce"]

    def test_length_chart_has_aliases(self, units):
        assert units.LENGTH_CHART["m"] == units.LENGTH_CHART["meter"]
        assert units.LENGTH_CHART["km"] == units.LENGTH_CHART["kilometer"]
        assert units.LENGTH_CHART["ft"] == units.LENGTH_CHART["foot"]

    def test_length_chart_case_insensitive_aliases(self, units):
        assert units.LENGTH_CHART["m"] == units.LENGTH_CHART["M"]
        assert units.LENGTH_CHART["km"] == units.LENGTH_CHART["KM"]

    def test_temperature_chart_has_lambdas(self, units):
        for key in ["celsius", "c", "fahrenheit", "f", "kelvin", "k"]:
            assert key in units.TEMPERATURE_CHART
            assert callable(units.TEMPERATURE_CHART[key][0])
            assert callable(units.TEMPERATURE_CHART[key][1])

    def test_storage_chart_bit_is_base(self, units):
        assert units.STORAGE_TYPE_CHART["bit"] == 1
        assert units.STORAGE_TYPE_CHART["byte"] == 8
        assert units.STORAGE_TYPE_CHART["KB"] == 8192


# =========================================================================
# Temperature conversions
# =========================================================================

class TestTemperatureConversion:

    def test_celsius_to_fahrenheit(self, conv):
        result = conv.convert(100, "celsius", "fahrenheit")
        assert result == pytest.approx(212, abs=0.01)

    def test_fahrenheit_to_celsius(self, conv):
        result = conv.convert(32, "fahrenheit", "celsius")
        assert result == pytest.approx(0, abs=0.01)

    def test_celsius_to_kelvin(self, conv):
        result = conv.convert(0, "celsius", "kelvin")
        assert result == pytest.approx(273.15, abs=0.01)

    def test_kelvin_to_celsius(self, conv):
        result = conv.convert(273.15, "kelvin", "celsius")
        assert result == pytest.approx(0, abs=0.01)

    def test_same_unit_returns_value(self, conv):
        assert conv.convert(42, "celsius", "celsius") == 42

    def test_freezing_point_f_to_c(self, conv):
        assert conv.convert(32, "f", "c") == pytest.approx(0, abs=0.01)

    def test_boiling_point_c_to_f(self, conv):
        assert conv.convert(100, "c", "f") == pytest.approx(212, abs=0.01)

    def test_absolute_zero_k_to_c(self, conv):
        assert conv.convert(0, "k", "c") == pytest.approx(-273.15, abs=0.01)

    def test_body_temperature(self, conv):
        assert conv.convert(37, "c", "f") == pytest.approx(98.6, abs=0.1)

    def test_negative_celsius_to_fahrenheit(self, conv):
        assert conv.convert(-40, "c", "f") == pytest.approx(-40, abs=0.01)


# =========================================================================
# Weight conversions
# =========================================================================

class TestWeightConversion:

    def test_kg_to_lb(self, conv):
        result = conv.convert(1, "kg", "lb")
        assert result == pytest.approx(2.2046, abs=0.01)

    def test_lb_to_kg(self, conv):
        result = conv.convert(2.2046, "lb", "kg")
        assert result == pytest.approx(1, abs=0.01)

    def test_kg_to_g(self, conv):
        result = conv.convert(1, "kg", "gram")
        assert result == pytest.approx(1000, abs=0.1)

    def test_oz_to_gram(self, conv):
        result = conv.convert(1, "oz", "gram")
        assert result == pytest.approx(28.3495, abs=0.1)

    def test_same_unit_returns_value(self, conv):
        assert conv.convert(5, "kg", "kg") == 5

    def test_tonne_to_kg(self, conv):
        assert conv.convert(1, "tonne", "kg") == pytest.approx(1000, abs=1)


# =========================================================================
# Length conversions
# =========================================================================

class TestLengthConversion:

    def test_km_to_m(self, conv):
        assert conv.convert(1, "km", "m") == pytest.approx(1000)

    def test_m_to_cm(self, conv):
        assert conv.convert(1, "m", "cm") == pytest.approx(100)

    def test_mile_to_km(self, conv):
        assert conv.convert(1, "mile", "km") == pytest.approx(1.609344)

    def test_foot_to_m(self, conv):
        assert conv.convert(1, "foot", "m") == pytest.approx(0.3048)

    def test_inch_to_cm(self, conv):
        assert conv.convert(1, "inch", "cm") == pytest.approx(2.54)

    def test_same_unit_returns_value(self, conv):
        assert conv.convert(42, "m", "m") == 42

    def test_yard_to_foot(self, conv):
        assert conv.convert(1, "yard", "foot") == pytest.approx(3, abs=0.01)

    def test_nautical_mile_to_km(self, conv):
        assert conv.convert(1, "nautical-mile", "km") == pytest.approx(1.852)


# =========================================================================
# Storage conversions
# =========================================================================

class TestStorageConversion:

    def test_byte_to_bit(self, conv):
        assert conv.convert(1, "byte", "bit") == pytest.approx(8)

    def test_kb_to_byte(self, conv):
        assert conv.convert(1, "KB", "byte") == pytest.approx(1024)

    def test_mb_to_kb(self, conv):
        assert conv.convert(1, "MB", "KB") == pytest.approx(1024)

    def test_gb_to_mb(self, conv):
        assert conv.convert(1, "GB", "MB") == pytest.approx(1024)

    def test_tb_to_gb(self, conv):
        assert conv.convert(1, "TB", "GB") == pytest.approx(1024)


# =========================================================================
# Time conversions
# =========================================================================

class TestTimeConversion:

    def test_minute_to_second(self, conv):
        assert conv.convert(1, "minute", "second") == pytest.approx(60)

    def test_hour_to_minute(self, conv):
        assert conv.convert(1, "hour", "minute") == pytest.approx(60)

    def test_day_to_hour(self, conv):
        assert conv.convert(1, "day", "hour") == pytest.approx(24)

    def test_week_to_day(self, conv):
        assert conv.convert(1, "week", "day") == pytest.approx(7)

    def test_same_unit(self, conv):
        assert conv.convert(100, "s", "s") == 100


# =========================================================================
# Other chart conversions
# =========================================================================

class TestOtherConversions:

    def test_liter_to_ml(self, conv):
        assert conv.convert(1, "liter", "milliliter") == pytest.approx(1000)

    def test_degree_to_radian(self, conv):
        assert conv.convert(57.2958, "degree", "radian") == pytest.approx(1, abs=0.01)

    def test_kcal_to_cal(self, conv):
        assert conv.convert(1, "kcal", "cal") == pytest.approx(1000)

    def test_kwh_to_joule(self, conv):
        assert conv.convert(1, "kwh", "joule") == pytest.approx(3.6e6)

    def test_kmph_to_mps(self, conv):
        assert conv.convert(3.6, "kmph", "mps") == pytest.approx(1, abs=0.01)

    def test_atm_to_pascal(self, conv):
        assert conv.convert(1, "atm", "pascal") == pytest.approx(101325)

    def test_hp_to_watt(self, conv):
        assert conv.convert(1, "hp", "watt") == pytest.approx(745.7)

    def test_kv_to_volt(self, conv):
        assert conv.convert(1, "kV", "volt") == pytest.approx(1000)

    def test_khz_to_hz(self, conv):
        assert conv.convert(1, "kHz", "Hz") == pytest.approx(1000)


# =========================================================================
# Error handling
# =========================================================================

class TestConversionErrors:

    def test_unsupported_conversion_raises(self, conv):
        with pytest.raises(ValueError, match="Unsupported conversion"):
            conv.convert(1, "kg", "meter")

    def test_nonsense_units_raises(self, conv):
        with pytest.raises(ValueError):
            conv.convert(1, "banana", "apple")


# =========================================================================
# clean_type
# =========================================================================

class TestCleanType:

    def test_three_letter_currency_uppercased(self, conv):
        assert conv.clean_type("usd") == "USD"
        assert conv.clean_type("ars") == "ARS"

    def test_plural_stripped(self, conv):
        assert conv.clean_type("kilograms") == "kilogram"
        assert conv.clean_type("meters") == "meter"

    def test_celsius_not_stripped(self, conv):
        assert conv.clean_type("celsius") == "celsius"

    def test_short_alias_unchanged(self, conv):
        assert conv.clean_type("kg") == "kg"
        assert conv.clean_type("m") == "m"


# =========================================================================
# parse_input_and_convert
# =========================================================================

class TestParseInputAndConvert:

    def test_simple_conversion(self, conv):
        result, suffix = conv.parse_input_and_convert("100 celsius _ fahrenheit")
        assert result == pytest.approx(212, abs=0.1)
        assert suffix == "fahrenheit"

    def test_simple_with_plural_suffix(self, conv):
        result, suffix = conv.parse_input_and_convert("1000 meters _ kilometers")
        assert result == pytest.approx(1, abs=0.01)
        assert suffix == "kilometers"

    def test_compound_same_type(self, conv):
        # 1 hour and 30 minutes to minutes
        result, suffix = conv.parse_input_and_convert("1 hour and 30 minute _ minute")
        assert result == pytest.approx(90, abs=0.1)

    def test_invalid_format_raises(self, conv):
        with pytest.raises(ValueError):
            conv.parse_input_and_convert("just some random text")

    def test_invalid_and_format_raises(self, conv):
        with pytest.raises(ValueError):
            conv.parse_input_and_convert("1 kg and 2 _ lb")
