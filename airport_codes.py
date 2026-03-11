# IATA airport code lookup — lowercase city name → IATA code
# FIX: Added more major Indian cities that users are likely to query
AIRPORT_CODES = {
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",          # legacy alias
    "nagpur": "NAG",
    "pune": "PNQ",
    "bangalore": "BLR",
    "bengaluru": "BLR",       # FIX: official spelling alias
    "hyderabad": "HYD",
    "chennai": "MAA",
    "madras": "MAA",          # legacy alias
    "kolkata": "CCU",
    "calcutta": "CCU",        # legacy alias
    "ahmedabad": "AMD",
    "goa": "GOI",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "kochi": "COK",
    "cochin": "COK",          # alias
    "bhubaneswar": "BBI",
    "indore": "IDR",
    "surat": "STV",
    "vadodara": "BDQ",
    "amritsar": "ATQ",
    "chandigarh": "IXC",
    "visakhapatnam": "VTZ",
    "vizag": "VTZ",           # alias
}