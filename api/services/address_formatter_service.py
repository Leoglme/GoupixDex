"""Format a postal address per destination country (UPU recipient block, country uppercased)."""

from __future__ import annotations

# ISO-3166-1 alpha-2 → English country name printed in uppercase on the last line
# (UPU recommends English or French; English is universally recognised by sorting machines).
_COUNTRY_NAMES_EN: dict[str, str] = {
    "FR": "FRANCE",
    "BE": "BELGIUM",
    "LU": "LUXEMBOURG",
    "CH": "SWITZERLAND",
    "DE": "GERMANY",
    "AT": "AUSTRIA",
    "NL": "NETHERLANDS",
    "ES": "SPAIN",
    "PT": "PORTUGAL",
    "IT": "ITALY",
    "DK": "DENMARK",
    "SE": "SWEDEN",
    "NO": "NORWAY",
    "FI": "FINLAND",
    "PL": "POLAND",
    "CZ": "CZECH REPUBLIC",
    "SK": "SLOVAKIA",
    "HU": "HUNGARY",
    "IE": "IRELAND",
    "GB": "UNITED KINGDOM",
    "UK": "UNITED KINGDOM",
    "US": "UNITED STATES",
    "CA": "CANADA",
    "AU": "AUSTRALIA",
    "NZ": "NEW ZEALAND",
    "JP": "JAPAN",
    "CN": "CHINA",
    "HK": "HONG KONG",
    "SG": "SINGAPORE",
    "MX": "MEXICO",
    "BR": "BRAZIL",
    "AR": "ARGENTINA",
    "CL": "CHILE",
    "RO": "ROMANIA",
    "GR": "GREECE",
    "BG": "BULGARIA",
    "HR": "CROATIA",
    "SI": "SLOVENIA",
    "EE": "ESTONIA",
    "LV": "LATVIA",
    "LT": "LITHUANIA",
    "IS": "ICELAND",
    "MT": "MALTA",
    "CY": "CYPRUS",
    "TR": "TURKEY",
    "IL": "ISRAEL",
    "ZA": "SOUTH AFRICA",
    "MA": "MOROCCO",
    "DZ": "ALGERIA",
    "TN": "TUNISIA",
    "RU": "RUSSIA",
    "UA": "UKRAINE",
    "KR": "SOUTH KOREA",
    "TW": "TAIWAN",
    "TH": "THAILAND",
    "VN": "VIETNAM",
    "MY": "MALAYSIA",
    "PH": "PHILIPPINES",
    "ID": "INDONESIA",
    "IN": "INDIA",
    "AE": "UNITED ARAB EMIRATES",
    "SA": "SAUDI ARABIA",
}


def country_name(code: str | None) -> str:
    """Return the English uppercase country name for an ISO-2 code (fallback: the code itself)."""
    if not code:
        return ""
    c = code.strip().upper()
    return _COUNTRY_NAMES_EN.get(c, c)


def _city_postal_default(postal_code: str, city: str) -> str:
    """``75001 PARIS`` — most of Europe (incl. France, Germany, Belgium, Switzerland, Spain…)."""
    parts = [p for p in (postal_code.strip(), city.strip()) for p in [p] if p]
    return " ".join(parts)


def _city_postal_us(city: str, state: str | None, postal_code: str) -> str:
    """``BROOKLYN, NY 11201`` — US Postal Service standard."""
    line = city.strip().upper()
    if state and state.strip():
        line = f"{line}, {state.strip().upper()}"
    if postal_code.strip():
        line = f"{line} {postal_code.strip()}"
    return line


def _city_postal_ca(city: str, state: str | None, postal_code: str) -> str:
    """``MONTREAL QC  H2X 1Y4`` — Canada Post (city + province + postal code, two spaces)."""
    line = city.strip().upper()
    if state and state.strip():
        line = f"{line} {state.strip().upper()}"
    if postal_code.strip():
        line = f"{line}  {postal_code.strip().upper()}"
    return line


def format_label_lines(
    *,
    full_name: str,
    line1: str,
    line2: str | None,
    postal_code: str,
    city: str,
    state: str | None = None,
    country_code: str | None = None,
    sender_country_code: str = "FR",
) -> list[str]:
    """
    Build the printable lines for an envelope, preserving line breaks:
    name → street → (complement) → city/postal block (per country) → COUNTRY (if international).

    The sender country (default ``FR``) decides whether to omit the country line for domestic mail.
    """
    name = (full_name or "").strip()
    street1 = (line1 or "").strip()
    street2 = (line2 or "").strip() if line2 else ""
    pc = (postal_code or "").strip()
    cty = (city or "").strip()
    st = (state or "").strip() if state else ""
    cc = (country_code or "").strip().upper()
    home_cc = (sender_country_code or "FR").strip().upper()

    if cc == "US":
        city_postal = _city_postal_us(cty, st or None, pc)
    elif cc == "CA":
        city_postal = _city_postal_ca(cty, st or None, pc)
    elif cc == "GB" or cc == "UK":
        city_postal = cty.upper()
    elif cc == "IE":
        city_postal = cty.upper()
    else:
        city_postal = _city_postal_default(pc, cty)

    lines: list[str] = []
    if name:
        lines.append(name)
    if street1:
        lines.append(street1)
    if street2:
        lines.append(street2)
    if cc == "GB" or cc == "UK":
        if city_postal:
            lines.append(city_postal)
        if pc:
            lines.append(pc.upper())
    elif cc == "IE":
        if city_postal:
            lines.append(city_postal)
        if pc:
            lines.append(pc.upper())
    else:
        if city_postal:
            lines.append(city_postal)

    if cc and cc != home_cc:
        lines.append(country_name(cc))

    return lines
