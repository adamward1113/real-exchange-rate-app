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
import re

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
IMF_AGENCY = "IMF.STA"
CPI_FLOW = "CPI"
ER_FLOW = "ER"
CPI_KEY = "{iso3}.CPI._T.IX.M"
ER_KEY = "{iso3}.XDC_USD.PA_RT.M"

START_PERIOD = "1976-01"
EURO_AREA_CODE = "G163"
USA_CODE = "USA"
REQUEST_TIMEOUT = 60  # seconds
CACHE_TTL = 24 * 60 * 60  # refresh IMF data once a day

# IMF member countries (ISO3 code -> name), plus the Euro area.
COUNTRIES: dict[str, str] = {
    "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria", "AND": "Andorra",
    "AGO": "Angola", "ATG": "Antigua and Barbuda", "ARG": "Argentina",
    "ARM": "Armenia", "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan",
    "BHS": "Bahamas", "BHR": "Bahrain", "BGD": "Bangladesh", "BRB": "Barbados",
    "BLR": "Belarus", "BEL": "Belgium", "BLZ": "Belize", "BEN": "Benin",
    "BTN": "Bhutan", "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina",
    "BWA": "Botswana", "BRA": "Brazil", "BRN": "Brunei Darussalam",
    "BGR": "Bulgaria", "BFA": "Burkina Faso", "BDI": "Burundi",
    "CPV": "Cabo Verde", "KHM": "Cambodia", "CMR": "Cameroon", "CAN": "Canada",
    "CAF": "Central African Republic", "TCD": "Chad", "CHL": "Chile",
    "CHN": "China", "COL": "Colombia", "COM": "Comoros",
    "COD": "Congo, Democratic Republic of the", "COG": "Congo, Republic of",
    "CRI": "Costa Rica", "CIV": "Côte d'Ivoire", "HRV": "Croatia",
    "CYP": "Cyprus", "CZE": "Czech Republic", "DNK": "Denmark",
    "DJI": "Djibouti", "DMA": "Dominica", "DOM": "Dominican Republic",
    "ECU": "Ecuador", "EGY": "Egypt", "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "EST": "Estonia",
    "SWZ": "Eswatini", "ETH": "Ethiopia", "FJI": "Fiji", "FIN": "Finland",
    "FRA": "France", "GAB": "Gabon", "GMB": "Gambia", "GEO": "Georgia",
    "DEU": "Germany", "GHA": "Ghana", "GRC": "Greece", "GRD": "Grenada",
    "GTM": "Guatemala", "GIN": "Guinea", "GNB": "Guinea-Bissau",
    "GUY": "Guyana", "HTI": "Haiti", "HND": "Honduras",
    "HKG": "Hong Kong SAR, China", "HUN": "Hungary", "ISL": "Iceland",
    "IND": "India", "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq",
    "IRL": "Ireland", "ISR": "Israel", "ITA": "Italy", "JAM": "Jamaica",
    "JPN": "Japan", "JOR": "Jordan", "KAZ": "Kazakhstan", "KEN": "Kenya",
    "KIR": "Kiribati", "KOR": "Korea", "XKX": "Kosovo", "KWT": "Kuwait",
    "KGZ": "Kyrgyz Republic", "LAO": "Lao P.D.R.", "LVA": "Latvia",
    "LBN": "Lebanon", "LSO": "Lesotho", "LBR": "Liberia", "LBY": "Libya",
    "LIE": "Liechtenstein", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MAC": "Macao SAR, China", "MDG": "Madagascar", "MWI": "Malawi",
    "MYS": "Malaysia", "MDV": "Maldives", "MLI": "Mali", "MLT": "Malta",
    "MHL": "Marshall Islands", "MRT": "Mauritania", "MUS": "Mauritius",
    "MEX": "Mexico", "FSM": "Micronesia", "MDA": "Moldova", "MCO": "Monaco",
    "MNG": "Mongolia", "MNE": "Montenegro", "MAR": "Morocco",
    "MOZ": "Mozambique", "MMR": "Myanmar", "NAM": "Namibia", "NRU": "Nauru",
    "NPL": "Nepal", "NLD": "Netherlands", "NZL": "New Zealand",
    "NIC": "Nicaragua", "NER": "Niger", "NGA": "Nigeria",
    "MKD": "North Macedonia", "NOR": "Norway", "OMN": "Oman",
    "PAK": "Pakistan", "PLW": "Palau", "PAN": "Panama",
    "PNG": "Papua New Guinea", "PRY": "Paraguay", "PER": "Peru",
    "PHL": "Philippines", "POL": "Poland", "PRT": "Portugal", "QAT": "Qatar",
    "ROU": "Romania", "RUS": "Russia", "RWA": "Rwanda", "WSM": "Samoa",
    "SMR": "San Marino", "STP": "São Tomé and Príncipe", "SAU": "Saudi Arabia",
    "SEN": "Senegal", "SRB": "Serbia", "SYC": "Seychelles",
    "SLE": "Sierra Leone", "SGP": "Singapore", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SLB": "Solomon Islands", "SOM": "Somalia",
    "ZAF": "South Africa", "SSD": "South Sudan", "ESP": "Spain",
    "LKA": "Sri Lanka", "KNA": "St. Kitts and Nevis", "LCA": "St. Lucia",
    "VCT": "St. Vincent and the Grenadines", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand",
    "TLS": "Timor-Leste", "TGO": "Togo", "TON": "Tonga",
    "TTO": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Türkiye",
    "TKM": "Turkmenistan", "TUV": "Tuvalu", "UGA": "Uganda", "UKR": "Ukraine",
    "ARE": "United Arab Emirates", "GBR": "United Kingdom",
    "USA": "United States", "URY": "Uruguay", "UZB": "Uzbekistan",
    "VUT": "Vanuatu", "VEN": "Venezuela", "VNM": "Vietnam", "YEM": "Yemen",
    "ZMB": "Zambia", "ZWE": "Zimbabwe",
    EURO_AREA_CODE: "Euro area",
}


class IMFRequestError(RuntimeError):
    """Raised when the IMF API cannot be reached or returns an error."""


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


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_imf_series(flow: str, key: str) -> pd.Series:
    """
    Fetch one monthly IMF series from January 1976 onward.

    Returns an empty Series when the IMF has no data for the key.
    Raises IMFRequestError for network or server problems.
    """
    url = f"{IMF_BASE_URL}/data/dataflow/{IMF_AGENCY}/{flow}/+/{key}"
    params = {"c[TIME_PERIOD]": f"ge:{START_PERIOD}"}
    formats = (
        "application/vnd.sdmx.data+csv;version=2.0.0",
        "application/vnd.sdmx.data+json;version=2.0.0",
    )
    last_error = ""
    for accept in formats:
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Accept": accept, "User-Agent": "rer-streamlit-app"},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise IMFRequestError(f"Could not reach the IMF API: {exc}") from exc

        if response.status_code == 404:
            return pd.Series(dtype="float64")  # no data for this key
        if not response.ok:
            last_error = f"HTTP {response.status_code} for {response.url}"
            continue

        body = response.text.strip()
        if not body:
            return pd.Series(dtype="float64")
        try:
            if body.startswith("{"):
                return _parse_sdmx_json(response.json())
            return _parse_sdmx_csv(body)
        except (ValueError, KeyError, TypeError) as exc:
            last_error = f"Could not parse IMF response ({accept}): {exc}"
            continue

    raise IMFRequestError(last_error or "The IMF API returned no usable data.")


def get_cpi(iso3: str) -> pd.Series:
    return fetch_imf_series(CPI_FLOW, CPI_KEY.format(iso3=iso3))


def get_usd_rate(iso3: str) -> pd.Series | None:
    """Local currency per USD. Returns None for the USA (rate is 1)."""
    if iso3 == USA_CODE:
        return None
    return fetch_imf_series(ER_FLOW, ER_KEY.format(iso3=iso3))


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

    try:
        with st.spinner(f"Loading IMF data for {name1} and {name2}..."):
            x1, x2 = get_usd_rate(code1), get_usd_rate(code2)
            p1, p2 = get_cpi(code1), get_cpi(code2)
    except IMFRequestError as exc:
        st.error(f"IMF data request failed. {exc}")
        st.stop()

    missing = []
    for name, series, label in (
        (name1, x1, "exchange rate"), (name2, x2, "exchange rate"),
        (name1, p1, "CPI"), (name2, p2, "CPI"),
    ):
        if series is not None and series.dropna().empty:
            missing.append(f"monthly {label} for {name}")
    if missing:
        st.error("The IMF has no data for: " + "; ".join(missing) + ".")
        st.stop()

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

    with st.expander("Method"):
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
- Source: IMF SDMX 3.0 API, dataflows `{IMF_AGENCY}:{CPI_FLOW}` (key
  `{{ISO3}}.CPI._T.IX.M`) and `{IMF_AGENCY}:{ER_FLOW}` (key
  `{{ISO3}}.XDC_USD.PA_RT.M`).
"""
        )


if __name__ == "__main__":
    main()
