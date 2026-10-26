# Real Exchange Rate Explorer

A Streamlit app that computes the monthly real exchange rate (RER) between any two IMF countries, or the Euro area, using IMF CPI and exchange-rate data from January 1976 onward where available.

## Features

- Choose **Country 1** and **Country 2** from IMF member countries and the Euro area.
- Pulls monthly CPI and exchange-rate data directly from the IMF SDMX 3.0 API.
- Pick a start and end month; the sample-period average **RER\*** and the **Real Index** recalculate automatically.
- Interactive Plotly charts with a **Real**, **Nominal**, or **Both** view (Both uses separate y-axes).
- **CSV download** of every observation and calculation in the selected sample period.

## Method

| Symbol | Definition |
|---|---|
| X1(t), X2(t) | Local currency per USD from the IMF (X = 1 for the United States) |
| S(t) | Units of Country 2 currency per 1 unit of Country 1 currency = X2(t) / X1(t) |
| P1(t), P2(t) | Monthly CPI of Country 1 and Country 2 |
| RER(t) | S(t) × P1(t) / P2(t) |
| RER\* | Average of RER(t) over valid months in the selected sample period |
| Real Index(t) | 100 × RER(t) / RER\* |

- A rising RER is a real appreciation for Country 1.
- A month is **valid** only if both exchange rates and both CPIs are present and positive. Other months are left blank, not filled in.
- S(t) is plotted in actual currency units and is not normalized.
- Because each CPI has its own base year, the RER level is arbitrary; the Real Index puts it on a common scale where the sample average equals 100.

## Data source

IMF SDMX 3.0 API: `https://api.imf.org/external/sdmx/3.0`

| Series | Dataflow | Key |
|---|---|---|
| Monthly CPI | `IMF.STA:CPI` | `{ISO3}.CPI._T.IX.M` |
| Monthly exchange rate (period average, local currency per USD) | `IMF.STA:ER` | `{ISO3}.XDC_USD.PA_RT.M` |

`{ISO3}` is the country code; the Euro area uses `G163`. Responses are cached for 24 hours.

## Run locally

Requires **Python 3.12**.

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt`, and `README.md` to a GitHub repository.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app from the repository with `app.py` as the main file.
3. Under **Advanced settings**, set the Python version to **3.12**.
4. Deploy.

## Files

- `app.py`: the Streamlit app
- `requirements.txt`: Python dependencies
- `README.md`: this file

## Data license

Data are from the International Monetary Fund (https://data.imf.org) and subject to the IMF's terms of use (https://www.imf.org/external/terms.htm).
