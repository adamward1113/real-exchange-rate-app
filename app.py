"""
Real Exchange Rate (RER) Explorer
=================================

Streamlit app that computes the real exchange rate between any two IMF
countries (or the Euro area) from monthly IMF CPI and exchange-rate data.

Definitions
-----------
S(t)   = units of Country 2 currency per 1 unit of Country 1 currency
P1(t)  = Country 1 monthly CPI
P2(t)  = Country 2 monthly CPI
RER(t) = S(t) * P1(t) / P2(t)

Over the user-selected sample period:
RER*           = average of RER(t) over valid months
Real Index(t)  = 100 * RER(t) / RER*

IMF exchange rates are local currency per USD (X). Therefore:
S(t) = X2(t) / X1(t), with X(t) = 1 for the United States.

Target runtime: Python 3.12.
"""

from __future__ import annotations

import io
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IMF_BASE_URL = "https://api.imf.org/external/sdmx/3.0"
IMF_BASE_URL_V21 = "https://api.imf.org/external/sdmx/2.1"  # fallback endpoint
IMF_AGENCY = "IMF.STA"
CPI_FLOW = "CPI"
ER_FLOW = "ER"
CPI_KEY = "{iso3}.CPI._T.IX.M"
ER_KEY = "{iso3}.XDC_USD.PA_RT.M"

START_PERIOD = "1976-01"
EURO_AREA_CODE = "G163"
USA_CODE = "USA"
REQUEST_TIMEOUT = 20  # seconds per request

# Bundled data: monthly series extracted from IMF bulk downloads (see README).
DATA_FILE = Path(__file__).parent / "imf_data.csv"
SOURCE_BUNDLED = "Bundled IMF download"
SOURCE_LIVE = "Live IMF API"
CACHE_TTL = 24 * 60 * 60  # refresh IMF data once a day

# Countries with monthly CPI (or HICP) and USD exchange-rate data in the IMF
# downloads (ISO3 code -> name), plus the Euro area (G163).
COUNTRIES: dict[str, str] = {
    "AFG": "Afghanistan",
    "ALB": "Albania",
    "DZA": "Algeria",
    "AGO": "Angola",
    "ATG": "Antigua and Barbuda",
    "ARG": "Argentina",
    "ARM": "Armenia",
    "ABW": "Aruba",
    "AUS": "Australia",
    "AUT": "Austria",
    "AZE": "Azerbaijan",
    "BHS": "Bahamas",
    "BHR": "Bahrain",
    "BGD": "Bangladesh",
    "BRB": "Barbados",
    "BLR": "Belarus",
    "BEL": "Belgium",
    "BLZ": "Belize",
    "BEN": "Benin",
    "BTN": "Bhutan",
    "BOL": "Bolivia",
    "BIH": "Bosnia and Herzegovina",
    "BWA": "Botswana",
    "BRA": "Brazil",
    "BRN": "Brunei Darussalam",
    "BGR": "Bulgaria",
    "BFA": "Burkina Faso",
    "BDI": "Burundi",
    "CPV": "Cabo Verde",
    "KHM": "Cambodia",
    "CMR": "Cameroon",
    "CAN": "Canada",
    "CAF": "Central African Republic",
    "TCD": "Chad",
    "CHL": "Chile",
    "CHN": "China",
    "COL": "Colombia",
    "COM": "Comoros",
    "COD": "Congo, Democratic Republic of the",
    "COG": "Congo, Republic of",
    "CRI": "Costa Rica",
    "HRV": "Croatia",
    "CUW": "Curaçao",
    "CYP": "Cyprus",
    "CZE": "Czech Republic",
    'CIV': "Côte d'Ivoire",
    "DNK": "Denmark",
    "DJI": "Djibouti",
    "DMA": "Dominica",
    "DOM": "Dominican Republic",
    "ECU": "Ecuador",
    "EGY": "Egypt",
    "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea",
    "EST": "Estonia",
    "SWZ": "Eswatini",
    "ETH": "Ethiopia",
    "G163": "Euro area",
    "FJI": "Fiji",
    "FIN": "Finland",
    "FRA": "France",
    "GAB": "Gabon",
    "GMB": "Gambia",
    "GEO": "Georgia",
    "DEU": "Germany",
    "GHA": "Ghana",
    "GRC": "Greece",
    "GRD": "Grenada",
    "GLP": "Guadeloupe",
    "GTM": "Guatemala",
    "GIN": "Guinea",
    "GNB": "Guinea-Bissau",
    "GUY": "Guyana",
    "HTI": "Haiti",
    "HND": "Honduras",
    "HKG": "Hong Kong SAR, China",
    "HUN": "Hungary",
    "ISL": "Iceland",
    "IND": "India",
    "IDN": "Indonesia",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "IRL": "Ireland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JAM": "Jamaica",
    "JPN": "Japan",
    "JOR": "Jordan",
    "KAZ": "Kazakhstan",
    "KEN": "Kenya",
    "KIR": "Kiribati",
    "KOR": "Korea, Republic of",
    "KOS": "Kosovo",
    "KWT": "Kuwait",
    "KGZ": "Kyrgyz Republic",
    "LAO": "Lao P.D.R.",
    "LVA": "Latvia",
    "LBN": "Lebanon",
    "LSO": "Lesotho",
    "LBR": "Liberia",
    "LBY": "Libya",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MAC": "Macao SAR, China",
    "MDG": "Madagascar",
    "MWI": "Malawi",
    "MYS": "Malaysia",
    "MDV": "Maldives",
    "MLI": "Mali",
    "MLT": "Malta",
    "MTQ": "Martinique",
    "MRT": "Mauritania",
    "MUS": "Mauritius",
    "MEX": "Mexico",
    "MDA": "Moldova",
    "MNG": "Mongolia",
    "MNE": "Montenegro",
    "MSR": "Montserrat",
    "MAR": "Morocco",
    "MOZ": "Mozambique",
    "MMR": "Myanmar",
    "NAM": "Namibia",
    "NRU": "Nauru",
    "NPL": "Nepal",
    "NLD": "Netherlands",
    "NCL": "New Caledonia",
    "NIC": "Nicaragua",
    "NER": "Niger",
    "NGA": "Nigeria",
    "MKD": "North Macedonia",
    "NOR": "Norway",
    "OMN": "Oman",
    "PAK": "Pakistan",
    "PAN": "Panama",
    "PRY": "Paraguay",
    "PER": "Peru",
    "PHL": "Philippines",
    "POL": "Poland",
    "PRT": "Portugal",
    "QAT": "Qatar",
    "ROU": "Romania",
    "RUS": "Russian Federation",
    "RWA": "Rwanda",
    "WSM": "Samoa",
    "SMR": "San Marino",
    "SAU": "Saudi Arabia",
    "SEN": "Senegal",
    "SRB": "Serbia",
    "SYC": "Seychelles",
    "SLE": "Sierra Leone",
    "SGP": "Singapore",
    "SXM": "Sint Maarten",
    "SVK": "Slovak Republic",
    "SVN": "Slovenia",
    "SLB": "Solomon Islands",
    "SOM": "Somalia",
    "ZAF": "South Africa",
    "SSD": "South Sudan",
    "ESP": "Spain",
    "LKA": "Sri Lanka",
    "KNA": "St. Kitts and Nevis",
    "LCA": "St. Lucia",
    "VCT": "St. Vincent and the Grenadines",
    "SDN": "Sudan",
    "SUR": "Suriname",
    "SWE": "Sweden",
    "CHE": "Switzerland",
    "SYR": "Syrian Arab Republic",
    "STP": "São Tomé and Príncipe",
    "TJK": "Tajikistan",
    "TZA": "Tanzania",
    "THA": "Thailand",
    "TLS": "Timor-Leste",
    "TGO": "Togo",
    "TON": "Tonga",
    "TTO": "Trinidad and Tobago",
    "TUN": "Tunisia",
    "TUR": "Türkiye",
    "UGA": "Uganda",
    "UKR": "Ukraine",
    "ARE": "United Arab Emirates",
    "GBR": "United Kingdom",
    "USA": "United States",
    "URY": "Uruguay",
    "UZB": "Uzbekistan",
    "VEN": "Venezuela",
    "VNM": "Vietnam",
    "YEM": "Yemen",
    "ZMB": "Zambia",
    "ZWE": "Zimbabwe",
}


# ---------------------------------------------------------------------------
# IMF data retrieval
# ---------------------------------------------------------------------------

_MONTH_PATTERNS = (
    re.compile(r"^(\d{4})-M(\d{1,2})$"),  # 1976-M01
    re.compile(r"^(\d{4})M(\d{1,2})$"),   # 1976M01
    re.compile(r"^(\d{4})-(\d{1,2})$"),   # 1976-01
)


def parse_month(period: str) -> pd.Period | None:
    """Convert an SDMX monthly period string to a pandas monthly Period."""
    text = str(period).strip()
    for pattern in _MONTH_PATTERNS:
        match = pattern.match(text)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12:
                return pd.Period(year=year, month=month, freq="M")
    return None


def _to_series(periods: list, values: list) -> pd.Series:
    """Build a clean monthly series from raw period and value lists."""
    index = [parse_month(p) for p in periods]
    data = pd.to_numeric(pd.Series(values, dtype="object"), errors="coerce")
    series = pd.Series(data.to_numpy(), index=index, dtype="float64")
    series = series[[i is not None for i in series.index]]
    series.index = pd.PeriodIndex(series.index, freq="M")
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series[series.index >= pd.Period(START_PERIOD, freq="M")]


def _parse_sdmx_csv(text: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text), dtype=str)
    columns = {c.upper(): c for c in frame.columns}
    if "TIME_PERIOD" not in columns or "OBS_VALUE" not in columns:
        raise ValueError("CSV response is missing TIME_PERIOD or OBS_VALUE")
    return _to_series(
        frame[columns["TIME_PERIOD"]].tolist(),
        frame[columns["OBS_VALUE"]].tolist(),
    )


def _parse_sdmx_json(payload: dict) -> pd.Series:
    """Parse an SDMX-JSON data message (series-level observations)."""
    data = payload.get("data", payload)
    datasets = data.get("dataSets") or []
    structures = data.get("structures") or [data.get("structure", {})]
    if not datasets or not structures:
        return pd.Series(dtype="float64")

    obs_dims = structures[0].get("dimensions", {}).get("observation", [])
    time_dim = next(
        (d for d in obs_dims if d.get("id") == "TIME_PERIOD"),
        obs_dims[0] if obs_dims else None,
    )
    if time_dim is None:
        return pd.Series(dtype="float64")
    time_values = [v.get("id") or v.get("value") for v in time_dim["values"]]

    periods: list = []
    values: list = []
    for series in (datasets[0].get("series") or {}).values():
        for obs_index, obs in (series.get("observations") or {}).items():
            idx = int(str(obs_index).split(":")[0])
            if idx < len(time_values):
                periods.append(time_values[idx])
                values.append(obs[0] if isinstance(obs, list) and obs else None)
    return _to_series(periods, values)


def _parse_sdmx_xml(text: str) -> pd.Series:
    """
    Parse SDMX-ML (2.1 or 3.0, generic or structure-specific) observations.
    Handles <Obs TIME_PERIOD=".." OBS_VALUE=".."/> and
    <Obs><ObsDimension value=".."/><ObsValue value=".."/></Obs>.
    """
    root = ET.fromstring(text)
    periods: list = []
    values: list = []
    for obs in root.iter():
        if not obs.tag.endswith("Obs"):
            continue
        period = obs.attrib.get("TIME_PERIOD")
        value = obs.attrib.get("OBS_VALUE")
        for child in obs:
            if child.tag.endswith("ObsDimension"):
                period = child.attrib.get("value", period)
            elif child.tag.endswith("ObsValue"):
                value = child.attrib.get("value", value)
        if period is not None:
            periods.append(period)
            values.append(value)
    return _to_series(periods, values)


def _parse_body(body: str) -> pd.Series:
    if body.startswith("{"):
        import json
        return _parse_sdmx_json(json.loads(body))
    if body.startswith("<"):
        if "<html" in body[:500].lower():
            raise ValueError("received an HTML page, not data")
        return _parse_sdmx_xml(body)
    return _parse_sdmx_csv(body)


def imf_url(flow: str, key: str) -> str:
    """
    Primary SDMX 3.0 data query:
    {base}/data/dataflow/{agency}/{flow}/~/{key}?c[TIME_PERIOD]=ge:1976-M01
    '~' requests the latest version of the dataflow.
    """
    start = START_PERIOD.replace("-", "-M")  # 1976-01 -> 1976-M01
    return (
        f"{IMF_BASE_URL}/data/dataflow/{IMF_AGENCY}/{flow}/~/{key}"
        f"?c[TIME_PERIOD]=ge:{start}"
    )


def _request_plan(flow: str, key: str) -> list[tuple[str, str]]:
    """(url, Accept header) pairs, tried in order until one returns data."""
    v30 = imf_url(flow, key)
    v21 = f"{IMF_BASE_URL_V21}/data/{IMF_AGENCY},{flow}/{key}?startPeriod={START_PERIOD}"
    return [
        (v30, "text/csv"),
        (v30, "application/json"),
        (v30, "application/xml"),
        (v21, "application/vnd.sdmx.data+csv;version=1.0.0"),
        (v21, "application/vnd.sdmx.data+json;version=1.0.0"),
        (v21, "application/xml"),
    ]


def _api_key() -> str | None:
    """Optional IMF API subscription key from Streamlit secrets or env var."""
    try:
        key = st.secrets.get("IMF_API_KEY")
    except Exception:  # no secrets file configured
        key = None
    return key or os.environ.get("IMF_API_KEY") or None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _fetch_imf_series_cached(flow: str, key: str, api_key: str | None) -> tuple[pd.Series, list[str]]:
    """
    Fetch one monthly IMF series from January 1976 onward.

    Returns (series, log). The series is empty if no attempt returned data;
    the log records the outcome of every attempt for troubleshooting.
    Failures are not cached for long because st.cache_data only caches
    returned values; callers decide what to show.
    """
    headers_base = {
        "Cache-Control": "no-cache",
        "User-Agent": "rer-streamlit-app/1.0 (python-requests)",
    }
    if api_key:
        headers_base["Ocp-Apim-Subscription-Key"] = api_key

    log: list[str] = []
    for url, accept in _request_plan(flow, key):
        response = None
        for attempt in range(2):  # one retry for rate limits / server errors
            try:
                response = requests.get(
                    url, headers={**headers_base, "Accept": accept}, timeout=REQUEST_TIMEOUT
                )
            except requests.RequestException as exc:
                log.append(f"[network error] {url} ({accept}): {type(exc).__name__}: {exc}")
                response = None
                break
            if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(2)
                continue
            break
        if response is None:
            continue

        status = response.status_code
        body = response.text.strip()
        snippet = re.sub(r"\s+", " ", body[:200])
        if not response.ok:
            log.append(f"[HTTP {status}] {url} ({accept}): {snippet}")
            continue
        if not body:
            log.append(f"[HTTP {status}, empty body] {url} ({accept})")
            continue
        try:
            series = _parse_body(body).dropna()
        except Exception as exc:  # parsing problems -> try next format
            log.append(f"[HTTP {status}, parse error] {url} ({accept}): {exc}; body starts: {snippet}")
            continue
        if series.empty:
            log.append(f"[HTTP {status}, 0 observations] {url} ({accept})")
            continue
        log.append(f"[OK, {len(series)} months] {url} ({accept})")
        return series, log
    # Raising (instead of returning) keeps failures out of the cache.
    raise _FetchFailed(log)


class _FetchFailed(Exception):
    def __init__(self, log: list[str]):
        super().__init__("no data")
        self.log = log


def fetch_imf_series(flow: str, key: str) -> pd.Series:
    """Return the series, or an empty Series if every attempt failed."""
    try:
        series, log = _fetch_imf_series_cached(flow, key, _api_key())
    except _FetchFailed as exc:
        series, log = pd.Series(dtype="float64"), exc.log
    st.session_state.setdefault("imf_log", {})[f"{flow}:{key}"] = log
    return series


@st.cache_data(show_spinner=False)
def load_bundled_data() -> dict[tuple[str, str], pd.Series]:
    """
    Load imf_data.csv (extracted from IMF bulk downloads of the CPI and ER
    dataflows). Columns: series (CPI / HICP / ER), iso3, date (YYYY-MM), value.
    Returns {(series, iso3): monthly Series}.
    """
    if not DATA_FILE.exists():
        return {}
    frame = pd.read_csv(DATA_FILE, dtype={"series": str, "iso3": str, "date": str})
    frame["period"] = pd.PeriodIndex(frame["date"], freq="M")
    out: dict[tuple[str, str], pd.Series] = {}
    for (series, iso3), group in frame.groupby(["series", "iso3"], sort=False):
        out[(series, iso3)] = (
            pd.Series(group["value"].to_numpy(dtype="float64"), index=group["period"])
            .sort_index()
        )
    return out


def get_cpi(iso3: str, source: str) -> tuple[pd.Series, str]:
    """
    Monthly CPI index. Uses {ISO3}.CPI._T.IX.M; if the IMF has no CPI for the
    economy (the Euro area), falls back to the HICP: {ISO3}.HICP._T.IX.M.
    Returns (series, description of what was used).
    """
    for index_type in ("CPI", "HICP"):
        key = f"{iso3}.{index_type}._T.IX.M"
        if source == SOURCE_LIVE:
            series = fetch_imf_series(CPI_FLOW, key)
            if not series.empty:
                return series, f"{key} (live IMF API)"
        series = load_bundled_data().get((index_type, iso3), pd.Series(dtype="float64"))
        if not series.empty:
            origin = "bundled IMF download" + (
                ", live API unavailable" if source == SOURCE_LIVE else ""
            )
            return series, f"{key} ({origin})"
    return pd.Series(dtype="float64"), f"{iso3}.CPI._T.IX.M (no data)"


def get_usd_rate(iso3: str, source: str) -> tuple[pd.Series | None, str]:
    """Local currency per USD. Returns None for the USA (rate is 1)."""
    if iso3 == USA_CODE:
        return None, "USD per USD = 1"
    key = ER_KEY.format(iso3=iso3)
    if source == SOURCE_LIVE:
        series = fetch_imf_series(ER_FLOW, key)
        if not series.empty:
            return series, f"{key} (live IMF API)"
    series = load_bundled_data().get(("ER", iso3), pd.Series(dtype="float64"))
    if not series.empty:
        origin = "bundled IMF download" + (
            ", live API unavailable" if source == SOURCE_LIVE else ""
        )
        return series, f"{key} ({origin})"
    return series, f"{key} (no data)"


def show_diagnostics(expanded: bool = False) -> None:
    """Show every IMF request the app made and what came back."""
    logs = st.session_state.get("imf_log", {})
    if not logs:
        return
    with st.expander("IMF connection diagnostics", expanded=expanded):
        st.caption(
            "Each line is one request to the IMF API. "
            f"API key in use: {'yes' if _api_key() else 'no'}."
        )
        for series_id, lines in logs.items():
            st.markdown(f"**{series_id}**")
            st.code("\n".join(lines) or "(no requests made)", language="text")


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def build_monthly_frame(
    x1: pd.Series | None,
    x2: pd.Series | None,
    p1: pd.Series,
    p2: pd.Series,
) -> pd.DataFrame:
    """
    Align the inputs on a monthly index and compute S(t) and RER(t).

    x1, x2: local currency per USD (None means the country is the USA).
    """
    pieces = [s for s in (x1, x2, p1, p2) if s is not None and not s.empty]
    if not pieces:
        return pd.DataFrame()
    start = max(pd.Period(START_PERIOD, freq="M"), min(s.index.min() for s in pieces))
    end = max(s.index.max() for s in pieces)
    index = pd.period_range(start, end, freq="M")

    def align(series: pd.Series | None) -> pd.Series:
        if series is None:
            return pd.Series(1.0, index=index)
        return series.reindex(index)

    frame = pd.DataFrame(index=index)
    frame["X1"] = align(x1)
    frame["X2"] = align(x2)
    frame["P1"] = align(p1)
    frame["P2"] = align(p2)
    rates_ok = (frame[["X1", "X2"]] > 0).all(axis=1)
    frame["S"] = np.where(rates_ok, frame["X2"] / frame["X1"], np.nan)

    inputs = frame[["X1", "X2", "P1", "P2"]]
    frame["valid"] = (inputs.notna() & (inputs > 0)).all(axis=1)
    frame["RER"] = np.where(
        frame["valid"], frame["S"] * frame["P1"] / frame["P2"], np.nan
    )
    return frame


def apply_sample(frame: pd.DataFrame, start: pd.Period, end: pd.Period) -> tuple[pd.DataFrame, float]:
    """Restrict to the sample period and compute RER* and the Real Index."""
    window = frame.loc[(frame.index >= start) & (frame.index <= end)].copy()
    rer_star = float(window.loc[window["valid"], "RER"].mean())
    window["RER_star"] = rer_star
    window["Real_Index"] = 100.0 * window["RER"] / rer_star
    return window, rer_star


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def build_chart(window: pd.DataFrame, view: str, name1: str, name2: str) -> go.Figure:
    dates = window.index.to_timestamp()
    s_label = f"S(t): {name2} currency per 1 {name1} currency"
    real_label = "Real Index (sample average = 100)"

    real_trace = go.Scatter(
        x=dates, y=window["Real_Index"], name="Real Index", mode="lines",
        line={"color": "#1f77b4", "width": 2}, connectgaps=False,
        hovertemplate="%{x|%b %Y}<br>Real Index: %{y:.2f}<extra></extra>",
    )
    nominal_trace = go.Scatter(
        x=dates, y=window["S"], name="Nominal S(t)", mode="lines",
        line={"color": "#d62728", "width": 2}, connectgaps=False,
        hovertemplate="%{x|%b %Y}<br>S(t): %{y:,.6g}<extra></extra>",
    )

    if view == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(real_trace, secondary_y=False)
        fig.add_trace(nominal_trace, secondary_y=True)
        fig.update_yaxes(title_text=real_label, secondary_y=False)
        fig.update_yaxes(title_text=s_label, secondary_y=True, showgrid=False)
        fig.add_hline(y=100, line_dash="dot", line_color="gray", secondary_y=False)
    elif view == "Nominal":
        fig = go.Figure(nominal_trace)
        fig.update_yaxes(title_text=s_label)
    else:
        fig = go.Figure(real_trace)
        fig.update_yaxes(title_text=real_label)
        fig.add_hline(y=100, line_dash="dot", line_color="gray")

    fig.update_layout(
        height=520,
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis_title="Month",
    )
    fig.update_xaxes(rangeslider_visible=True)
    return fig


def build_csv(window: pd.DataFrame, code1: str, code2: str) -> bytes:
    out = pd.DataFrame(
        {
            "date": window.index.strftime("%Y-%m"),
            f"X1_{code1}_per_USD": window["X1"],
            f"X2_{code2}_per_USD": window["X2"],
            f"S_{code2}_per_{code1}": window["S"],
            f"P1_CPI_{code1}": window["P1"],
            f"P2_CPI_{code2}": window["P2"],
            "RER": window["RER"],
            "RER_star": window["RER_star"],
            "Real_Index": window["Real_Index"],
            "valid_month": window["valid"],
        }
    )
    return out.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def country_label(code: str) -> str:
    return f"{COUNTRIES[code]} ({code})"


def main() -> None:
    st.set_page_config(page_title="Real Exchange Rate Explorer", layout="wide")
    st.title("Real Exchange Rate Explorer")
    st.caption(
        "Monthly real exchange rates from IMF CPI and exchange-rate data, "
        "January 1976 onward where available."
    )

    codes = sorted(COUNTRIES, key=lambda c: COUNTRIES[c])

    with st.sidebar:
        st.header("Countries")
        code1 = st.selectbox(
            "Country 1", codes, index=codes.index(USA_CODE), format_func=country_label
        )
        code2 = st.selectbox(
            "Country 2", codes, index=codes.index(EURO_AREA_CODE), format_func=country_label
        )

    if code1 == code2:
        st.warning("Choose two different countries.")
        st.stop()

    name1, name2 = COUNTRIES[code1], COUNTRIES[code2]

    with st.sidebar:
        st.header("Data source")
        source = st.radio(
            "Data source",
            [SOURCE_BUNDLED, SOURCE_LIVE],
            label_visibility="collapsed",
            help=(
                "Bundled: monthly series extracted from IMF CPI and ER bulk downloads "
                "(imf_data.csv in the repo). Live: queries the IMF SDMX 3.0 API and "
                "falls back to the bundled file for any series it can't retrieve."
            ),
        )

    if source == SOURCE_BUNDLED and not DATA_FILE.exists():
        st.error(
            "imf_data.csv was not found next to app.py. Add it to the repo, "
            f"or switch the data source to '{SOURCE_LIVE}'."
        )
        st.stop()

    st.session_state["imf_log"] = {}
    with st.spinner(f"Loading IMF data for {name1} and {name2}..."):
        x1, x1_src = get_usd_rate(code1, source)
        x2, x2_src = get_usd_rate(code2, source)
        p1, p1_src = get_cpi(code1, source)
        p2, p2_src = get_cpi(code2, source)

    missing = []
    for name, series, label, src in (
        (name1, x1, "exchange rate", x1_src),
        (name2, x2, "exchange rate", x2_src),
        (name1, p1, "CPI", p1_src),
        (name2, p2, "CPI", p2_src),
    ):
        if series is not None and series.dropna().empty:
            missing.append(f"- Monthly {label} for {name}: `{src}`")
    if missing:
        st.error("The IMF data has no observations for:\n" + "\n".join(missing))
        if source == SOURCE_LIVE:
            show_diagnostics(expanded=True)
        st.stop()

    for name, src in ((name1, p1_src), (name2, p2_src)):
        if ".HICP." in src:
            st.info(
                f"The IMF publishes no national CPI series for {name}, so its "
                "Harmonised Index of Consumer Prices (HICP) is used as P(t)."
            )
    if source == SOURCE_LIVE and any(
        "live API unavailable" in s for s in (x1_src, x2_src, p1_src, p2_src)
    ):
        st.warning(
            "The live IMF API did not return some series, so the bundled IMF download "
            "was used for them. See the diagnostics at the bottom of the page."
        )

    frame = build_monthly_frame(x1, x2, p1, p2)
    valid_months = frame.index[frame["valid"]] if not frame.empty else frame.index
    if len(valid_months) == 0:
        st.error(
            f"No months where exchange-rate and CPI data overlap for {name1} and {name2}."
        )
        st.stop()

    first, last = valid_months.min(), valid_months.max()
    if first > pd.Period(START_PERIOD, freq="M"):
        st.info(
            f"Overlapping data for this pair begins in {first.strftime('%B %Y')} "
            f"and ends in {last.strftime('%B %Y')}."
        )

    month_options = list(pd.period_range(first, last, freq="M"))
    with st.sidebar:
        st.header("Sample period")
        start, end = st.select_slider(
            "Start and end month",
            options=month_options,
            value=(first, last),
            format_func=lambda p: p.strftime("%b %Y"),
        )
        st.header("Chart")
        view = st.radio("Show", ["Real", "Nominal", "Both"], horizontal=True)

    window, rer_star = apply_sample(frame, start, end)
    n_valid = int(window["valid"].sum())
    if n_valid == 0:
        st.error("No valid months in the selected sample period.")
        st.stop()

    latest = window.loc[window["valid"]].iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric("RER* (sample average of RER)", f"{rer_star:,.6g}")
    col2.metric("Valid months in sample", f"{n_valid:,}")
    col3.metric(
        f"Latest Real Index ({window.loc[window['valid']].index[-1].strftime('%b %Y')})",
        f"{latest['Real_Index']:.2f}",
    )

    st.plotly_chart(build_chart(window, view, name1, name2))

    st.download_button(
        "Download CSV of sample period",
        data=build_csv(window, code1, code2),
        file_name=f"rer_{code1}_{code2}_{start.strftime('%Y%m')}_{end.strftime('%Y%m')}.csv",
        mime="text/csv",
    )

    if source == SOURCE_LIVE:
        show_diagnostics(expanded=False)

    with st.expander("Method and data"):
        st.markdown(
            f"""
- **S(t)** = units of {name2} currency per 1 unit of {name1} currency,
  computed as X2(t) / X1(t), where X is local currency per USD from the IMF
  (X = 1 for the United States).
- **RER(t) = S(t) × P1(t) / P2(t)**, where P1 and P2 are monthly CPIs.
  A rise in RER is a real appreciation for {name1}.
- **RER\\*** = average RER(t) over valid months in the selected sample period.
- **Real Index(t) = 100 × RER(t) / RER\\***.
- A month is valid only if both exchange rates and both CPIs are present
  and positive. Other months are left blank, not filled in.
- IMF dataflows `{IMF_AGENCY}:{CPI_FLOW}` (key `{{ISO3}}.CPI._T.IX.M`; HICP key
  `{{ISO3}}.HICP._T.IX.M` where no CPI exists) and `{IMF_AGENCY}:{ER_FLOW}`
  (key `{{ISO3}}.XDC_USD.PA_RT.M`, period average).

**Series used for this pair**

| | Series |
|---|---|
| X1 ({name1}) | `{x1_src}` |
| X2 ({name2}) | `{x2_src}` |
| P1 ({name1}) | `{p1_src}` |
| P2 ({name2}) | `{p2_src}` |
"""
        )


if __name__ == "__main__":
    main()
