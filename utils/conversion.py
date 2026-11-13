import math
import re

import requests

# A number with its unit attached, as in "10km"
_GLUED = re.compile(r"([-+]?(?:\d+\.?\d*|\.\d+))(\D.*)")


class Units():
    def __init__(self):
        self.WEIGHT_CHART: dict[str, tuple[float, float]] = {
            "kilogram": (1, 1),
            "kg": (1, 1),
            "tonne": (1000, 0.001),
            "ton": (1000, 0.001),
            "gram": (1e-3, 1e3),
            "g": (1e-3, 1e3),
            "milligram": (1e-6, 1e6),
            "mg": (1e-6, 1e6),
            "metric-ton": (1000, 0.001),
            "metric-tonne": (1000, 0.001),
            "long-ton": (1016.04608, 0.0009842073),
            "short-ton": (907.184, 0.0011023122),
            "pound": (0.453592, 2.2046244202),
            "lb": (0.453592, 2.2046244202),
            "stone": (6.35029, 0.1574731728),
            "st": (6.35029, 0.1574731728),
            "ounce": (0.0283495, 35.273990723),
            "oz": (0.0283495, 35.273990723),
            "carrat": (0.0002, 5000),
            "ct": (0.0002, 5000),
            "atomic-mass-unit": (1.660540199e-27, 6.022136652e26),
        }

        self.LENGTH_CHART: dict[str, float] = {
            # meter
            "m": 1,              
            "M": 1,              
            "meter": 1,          
            # kilometer
            "km": 1e3,           
            "KM": 1e3,           
            "kilometer": 1e3,    
            # centimeter
            "cm": 1e-2,          
            "CM": 1e-2,          
            "centimeter": 1e-2,  
            # millimeter
            "mm": 1e-3,          
            "MM": 1e-3,
            "millimeter": 1e-3,
            # micrometer
            "um": 1e-6,          
            "UM": 1e-6,
            "micrometer": 1e-6,
            # nanometer          
            "nm": 1e-9,          
            "NM": 1e-9,          
            "nanometer": 1e-9,
            # mile
            "mi": 1609.344,      
            "MI": 1609.344,      
            "mile": 1609.344,    
            # yard
            "yd": 0.9144,        
            "YD": 0.9144,        
            "yard": 0.9144,
            # foot
            "ft": 0.3048,        
            "FT": 0.3048,        
            "foot": 0.3048,      
            "feet": 0.3048,      
            # inch
            "in": 0.0254,
            "IN": 0.0254,
            "inch": 0.0254,
            "inches": 0.0254,
            # nautical mile
            "nmi": 1852,         
            "NMI": 1852,         
            "nautical-mile": 1852,
        }

        self.STORAGE_TYPE_CHART: dict[str, float] = {
            "bit": 1,
            "byte": 8,
            "B": 8,
            "kilobyte": 8192,
            "KB": 8192,
            "megabyte": 8388608,
            "MB": 8388608,
            "gigabyte": 8589934592,
            "GB": 8589934592,
            "terabyte": 8796093022208,
            "TB": 8796093022208,
            "petabyte": 9007199254740992,
            "PB": 9007199254740992,
            "exabyte": 9223372036854775808,
            "EB": 9223372036854775808,
        }

        self.TEMPERATURE_CHART = {
            "celsius": (lambda v: v + 273.15, lambda v: v - 273.15),
            "c": (lambda v: v + 273.15, lambda v: v - 273.15),
            "fahrenheit": (lambda v: (v - 32) * 5/9 + 273.15, lambda v: (v - 273.15) * 9/5 + 32),
            "f": (lambda v: (v - 32) * 5/9 + 273.15, lambda v: (v - 273.15) * 9/5 + 32),
            "kelvin": (lambda v: v, lambda v: v),
            "k": (lambda v: v, lambda v: v),
            "rankine": (lambda v: v * 5/9, lambda v: v * 9/5),
            "reaumur": (lambda v: v * 5/4 + 273.15, lambda v: (v - 273.15) * 4/5),
        }

        self.TIME_CHART: dict[str, float] = {
            "second": 1,
            "s": 1,
            "minute": 60,
            "min": 60,
            "m": 60,
            "hour": 3600,
            "h": 3600,
            "milisecond": 1e-3,
            "ms": 1e-3,
            "day": 86400,
            "d": 86400,
            "week": 604800,
            "w": 604800,
            "fortnight": 1209600,
            "month": 2628000,  # Approximation (30.44 days)
            "mo": 2628000,  # Approximation (30.44 days)
            "year": 31536000,  # Approximation (365 days)
            "yr": 31536000,  # Approximation (365 days)
            "decade": 315360000,  # Approximation (10 years)
            "dec": 315360000,  # Approximation (10 years)
            "century": 3153600000,  # Approximation (100 years)
            "cent": 3153600000,  # Approximation (100 years)
            "millennium": 31536000000,  # Approximation (1000 years)
            "millenia": 31536000000,  # Approximation (1000 years)
        }

        self.LIQUID_VOLUME_CHART: dict[str, float] = {
            "liter": 1,
            "l": 1,
            "milliliter": 1e-3,
            "ml": 1e-3,
            "gallon": 3.78541,
            "quart": 0.946353,
            "pint": 0.473176,
            "fluid-ounce": 0.0295735,
            "fl-oz": 0.0295735,
            "oz": 0.0295735,
            "ounce": 0.0295735,
            "cup": 0.236588,
            "tablespoon": 0.0147868,
            "tbsp": 0.0147868,
            "teaspoon": 0.00492892,
            "tsp": 0.00492892,
        }

        self.ANGLE_CHART: dict[str, float] = {
            "degree": 1,
            "deg": 1,
            "radian": 57.2958,
            "rad": 57.2958,
            "gradian": 0.9,
            "gon": 0.9,
        }

        self.ENERGY_CHART: dict[str, float] = {
            "joule": 1,
            "j": 1,
            "kilojoule": 1000,
            "kj": 1000,
            "calorie": 4.184,
            "cal": 4.184,
            "kilocalorie": 4184,
            "kcal": 4184,
            "watt-hour": 3600,
            "wh": 3600,
            "kilowatt-hour": 3.6e6,
            "kwh": 3.6e6,
        }

        self.SPEED_CHART: dict[str, float] = {
            "mps": 1,
            "kmph": 0.277778,
            "mph": 0.44704,
            "fps": 0.3048,
            "knot": 0.514444,
        }

        self.PRESSURE_CHART: dict[str, float] = {
            "pascal": 1,
            "Pa": 1,
            "bar": 100000,
            "atm": 101325,
            "torr": 133.322,
            "mmHg": 133.322,
            "psi": 6894.76,
        }

        self.FORCE_CHART: dict[str, float] = {
            "newton": 1,
            "N": 1,
            "kilonewton": 1000,
            "kN": 1000,
            "pound-force": 4.44822,
            "lbf": 4.44822,
            "dyne": 1e-5,
        }

        self.POWER_CHART: dict[str, float] = {
            "watt": 1,
            "W": 1,
            "kilowatt": 1000,
            "kW": 1000,
            "horsepower": 745.7,
            "hp": 745.7,
            "megawatt": 1e6,
            "MW": 1e6,
        }

        self.VOLTAGE_CHART: dict[str, float] = {
            "volt": 1,
            "V": 1,
            "millivolt": 1e-3,
            "mV": 1e-3,
            "kilovolt": 1000,
            "kV": 1000,
            "megavolt": 1e6,
            "MV": 1e6,
        }

        self.CURRENT_CHART: dict[str, float] = {
            "ampere": 1,
            "A": 1,
            "milliampere": 1e-3,
            "mA": 1e-3,
            "microampere": 1e-6,
            "μA": 1e-6,
        }

        self.RESISTANCE_CHART: dict[str, float] = {
            "ohm": 1,
            "Ω": 1,
            "kilohm": 1000,
            "kΩ": 1000,
            "megohm": 1e6,
            "MΩ": 1e6,
        }
        
        self.CAPACITANCE_CHART: dict[str, float] = {
            "farad": 1,
            "F": 1,
            "millifarad": 1e-3,
            "mF": 1e-3,
            "microfarad": 1e-6,
            "μF": 1e-6,
            "nanofarad": 1e-9,
            "nF": 1e-9,
        }

        self.INDUCTANCE_CHART: dict[str, float] = {
            "henry": 1,
            "H": 1,
            "millihenry": 1e-3,
            "mH": 1e-3,
            "microhenry": 1e-6,
            "μH": 1e-6,
            "nanohenry": 1e-9,
            "nH": 1e-9,
        }

        self.FREQUENCY_CHART: dict[str, float] = {
            "hertz": 1,
            "Hz": 1,
            "kilohertz": 1e3,
            "kHz": 1e3,
            "megahertz": 1e6,
            "MHz": 1e6,
            "gigahertz": 1e9,
            "GHz": 1e9,
        }

        self.LUMINANCE_CHART: dict[str, float] = {
            "candela": 1,
            "cd": 1,
            "lumen": 1,
            "lm": 1,
            "lux": 1,
            "lx": 1,
        }  

        self.AREA_CHART: dict[str, float] = {
            "square-meter": 1,
            "m2": 1,
            "square-kilometer": 1e6,
            "km2": 1e6,
            "hectare": 1e4,
            "ha": 1e4,
            "are": 1e2,
            "a": 1e2,
            "square-centimeter": 1e-4,
            "cm2": 1e-4,
            "square-millimeter": 1e-6,
            "mm2": 1e-6,
        }

        # Ya no usamos currency_converter aquí.


class ConversionError(ValueError):
    """Why an expression can't be converted, worded for the launcher."""


def format_result(value: float) -> str:
    """Two decimals; four significant digits below 1 (0.001538 BTC, not 0.00)."""
    if value == 0 or abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.{3 - math.floor(math.log10(abs(value)))}f}"


class Conversion():
    def __init__(self):
        self.units = Units()
        self._unit_names = {name for chart in vars(self.units).values() for name in chart}

    def convert(self, value: float, from_type: str, to_type: str):
        """
        Generalized conversion function que funciona con todas las categorías,
        incluyendo moneda via floatrates.com.
        """
        # Colección de todos los charts no-monedas
        charts = {
            "WEIGHT_CHART": self.units.WEIGHT_CHART,
            "LENGTH_CHART": self.units.LENGTH_CHART,
            "TEMPERATURE_CHART": self.units.TEMPERATURE_CHART,
            "TIME_CHART": self.units.TIME_CHART,
            "LIQUID_VOLUME_CHART": self.units.LIQUID_VOLUME_CHART,
            "STORAGE_TYPE_CHART": self.units.STORAGE_TYPE_CHART,
            "ANGLE_CHART": self.units.ANGLE_CHART,
            "ENERGY_CHART": self.units.ENERGY_CHART,
            "SPEED_CHART": self.units.SPEED_CHART,  
            "PRESSURE_CHART": self.units.PRESSURE_CHART,
            "FORCE_CHART": self.units.FORCE_CHART,
            "POWER_CHART": self.units.POWER_CHART,
            "VOLTAGE_CHART": self.units.VOLTAGE_CHART,
            "CURRENT_CHART": self.units.CURRENT_CHART,
            "RESISTANCE_CHART": self.units.RESISTANCE_CHART,
            "CAPACITANCE_CHART": self.units.CAPACITANCE_CHART,
            "INDUCTANCE_CHART": self.units.INDUCTANCE_CHART,
            "FREQUENCY_CHART": self.units.FREQUENCY_CHART,
            "LUMINANCE_CHART": self.units.LUMINANCE_CHART,
            "AREA_CHART": self.units.AREA_CHART,
        }

        # 1) Revisar si está en alguno de los charts (no monedas)
        for chart_name, chart in charts.items():
            if from_type in chart and to_type in chart:
                # Temperaturas usan lambdas
                if chart_name == "TEMPERATURE_CHART":
                    if from_type == to_type:
                        return value
                    to_kelvin = chart[from_type][0]
                    from_kelvin = chart[to_type][1]
                    return from_kelvin(to_kelvin(value))
                
                # Handle WEIGHT_CHART separately (tuple values)
                if chart_name == "WEIGHT_CHART":
                    if from_type == to_type:
                        return value
                    to_kg = chart[from_type][0]
                    from_kg = chart[to_type][1]
                    return value * to_kg * from_kg

                # Cualquier otro chart numérico
                if from_type == to_type:
                    return value
                return value * (chart[from_type] / chart[to_type])

        # 2) Si ambos son códigos de moneda (p. ej. “USD”, “ARS”)
        #    asumimos que están en mayúsculas y tienen 3 letras.
        if all(code.isalpha() and 3 <= len(code) <= 5 for code in (from_type, to_type)):
            return self._convert_currency(value, from_type, to_type)

        # 3) Si no cae en ningún caso, error.
        raise ConversionError(f"Can't convert {from_type} to {to_type}")

    def _convert_currency(self, value: float, from_code: str, to_code: str) -> float:
        """Fiat pairs from floatrates; anything it doesn't know (crypto) from
        CoinGecko."""
        try:
            try:
                return self._convert_currency_via_floatrates(value, from_code, to_code)
            except ValueError:
                from_lower, to_lower = from_code.lower(), to_code.lower()
                prices = self._coingecko_prices(from_lower, to_lower)
        except requests.RequestException as error:
            raise ConversionError("Can't reach the rates service") from error
        if prices.get(from_lower, {}).get(to_lower):
            return value * prices[from_lower][to_lower]
        if prices.get(to_lower, {}).get(from_lower):  # fiat to crypto
            return value / prices[to_lower][from_lower]
        raise ConversionError(f"No rate for {from_code.upper()} to {to_code.upper()}")

    @staticmethod
    def _coingecko_prices(*symbols: str) -> dict:
        """{coin: {versus: price}} between the lowercase symbols, in one
        request (the keyless API allows only a few a minute); coins and
        pairs CoinGecko doesn't have are left out."""
        both = ",".join(symbols)
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"symbols": both, "vs_currencies": both},
            timeout=5,
        )
        if resp.status_code == 429:
            raise ConversionError("CoinGecko rate limit reached, try again in a minute")
        return resp.json() if resp.status_code == 200 else {}

    def _convert_currency_via_floatrates(self, value: float, from_code: str, to_code: str) -> float:
        """
        Convierte usando el JSON de floatrates.com:
        - Hace GET a https://www.floatrates.com/daily/{from_lower}.json
        - Toma el rate de la clave to_lower y multiplica.
        """
        from_lower = from_code.lower()
        to_lower = to_code.lower()

        if from_lower == to_lower:
            return value

        url = f"https://www.floatrates.com/daily/{from_lower}.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            raise ValueError(f"Error al obtener datos de floatrates para {from_code}")

        data = resp.json()
        if to_lower not in data:
            raise ValueError(f"Moneda destino '{to_code}' no encontrada en la respuesta de floatrates para '{from_code}'")

        rate = float(data[to_lower]["rate"])  # floatrates sends it as a string
        return value * rate

    @staticmethod
    def _is_number(token: str) -> bool:
        try:
            float(token)
            return True
        except ValueError:
            return False

    @staticmethod
    def _number(token: str) -> float:
        try:
            return float(token)
        except ValueError:
            raise ConversionError(f"'{token}' is not a number") from None

    @classmethod
    def _split_glued(cls, token: str) -> list[str]:
        """'10km' -> ['10', 'km']; numbers ('1e3') and units stay whole."""
        if cls._is_number(token):
            return [token]
        match = _GLUED.fullmatch(token)
        return list(match.groups()) if match else [token]

    def parse_input_and_convert(self, input: str):
        parts = [part for token in input.split() for part in self._split_glued(token)]
        if parts and not self._is_number(parts[0]):
            parts.insert(0, "1")  # "usd to nok" is one dollar
        addition = "s" if parts[-1].endswith("s") else ""

        if "and" in parts:  # valor unidad1 and valor2 unidad2 _ a unidad_destino
            parts.remove("and")
            if len(parts) != 6:
                raise ConversionError("Expected: 1 h and 30 min to s")
            
            value1, from_type1, value2, from_type2, _, to_type = parts
            value1, value2 = self._number(value1), self._number(value2)
            from_type1 = self.clean_type(from_type1)
            from_type2 = self.clean_type(from_type2)
            to_type = self.clean_type(to_type)

            if from_type1 == from_type2:
                return self.convert(value1 + value2, from_type1, to_type), to_type + addition
            else:
                res = 0
                res += self.convert(value1, from_type1, to_type)
                res += self.convert(value2, from_type2, to_type)
                return res, to_type + addition
        else:
            if len(parts) != 4:
                raise ConversionError("Expected: 10 km to mi")
            value, from_type, _, to_type = parts
            value = self._number(value)
            from_type = self.clean_type(from_type)
            to_type = self.clean_type(to_type)
            return self.convert(value, from_type, to_type), to_type + addition

    def clean_type(self, type: str) -> str:
        """
        Si es moneda (3 letras), lo pasa a mayúsculas. 
        Si termina en 's' (y no es 'celsius'), le quita la 's' para 
        las otras unidades. """
        if type in self._unit_names:
            return type  # "cup" is the unit; "CUP" is the currency
        if len(type) == 3 and type.isalpha():
            if type.islower() and type.endswith("s") and type[:-1] in self._unit_names:
                return type[:-1]  # "lbs" is pounds, not a currency
            return type.upper()
        if type.endswith("s") and type.lower() != "celsius":
            # Para las tablas que tienen singular/plural
            singular = type[:-1].lower()
            # Si existe en STORAGE_TYPE_CHART, lo usamos; 
            # si no, devolvemos singular en minúsculas para otros charts.
            if singular in self.units.STORAGE_TYPE_CHART:
                return singular
            return singular.lower()
        return type


# Ejemplo rápido de uso:
if __name__ == "__main__":
    conv = Conversion()
    # Convierte 10 USD a ARS:
    result, suffix = conv.parse_input_and_convert("10 USD _ ARS")
    print(f"{result:.2f} {suffix}")  # Ej: "10 USD _ ARS" -> "38754.23 ARS"
