# Real Exchange Rate Explorer

A Streamlit app that computes the monthly real exchange rate (RER) between any two IMF countries, or the Euro area, using IMF CPI and exchange-rate data from January 1976 onward where available.

## Features

- Choose **Country 1** and **Country 2** from 190 economies with IMF monthly CPI and exchange-rate data, including the Euro area.
- Uses IMF data bundled in the repo (`imf_data.csv`), with an option to query the live IMF SDMX 3.0 API instead.
- Pick a start and end month; the sample-period average **RER\*** and the **Real Index** recalculate automatically.
- Interactive Plotly charts with a **Real**, **Nominal**, or **Both** view (Both uses separate y-axes).
- **CSV download** of every observation and calculation in the selected sample period.

## Method

| Symbol | Definition |
|---|---|
| X1(t), X2(t) | Local currency per USD from the IMF (X = 1 for the United States) |
| S(t) | Units of Country 2 currency per 1 unit of Country 1 currency = X2(t) / X1(t) |
| P1(t), P2(t) | Monthly CPI of Country 1 and Country 2 (HICP for the Euro area) |
| RER(t) | S(t) × P1(t) / P2(t) |
| RER\* | Average of RER(t) over valid months in the selected sample period |
| Real Index(t) | 100 × RER(t) / RER\* |

- A rising RER is a real appreciation for Country 1.
- A month is **valid** only if both exchange rates and both CPIs are present and positive. Other months are left blank, not filled in.
- S(t) is plotted in actual currency units and is not normalized.
- Because each CPI has its own base year, the RER level is arbitrary; the Real Index puts it on a common scale where the sample average equals 100.

## Data source

All data come from the IMF (`IMF.STA` agency):

| Series | Dataflow | Key |
|---|---|---|
| Monthly CPI (index) | `IMF.STA:CPI` | `{ISO3}.CPI._T.IX.M` |
| Monthly HICP (used only where no CPI exists, i.e. the Euro area) | `IMF.STA:CPI` | `{ISO3}.HICP._T.IX.M` |
| Monthly exchange rate (period average, local currency per USD) | `IMF.STA:ER` | `{ISO3}.XDC_USD.PA_RT.M` |

`{ISO3}` is the country code; the Euro area uses `G163`. The IMF publishes Euro area consumer prices only as the HICP, which starts in December 1999 in this dataset.

### Bundled data (default)

`imf_data.csv` holds the series above, January 1976 through September 2026, extracted from IMF bulk downloads made on 26 October 2026:

- `IMF.STA:CPI` version 5.0.0
- `IMF.STA:ER` version 4.0.1

The full downloads are 240 MB and 95 MB, which is over GitHub's 100 MB file limit, so only the needed series were kept (about 4.5 MB). Columns: `series` (`CPI`, `HICP`, or `ER`), `iso3`, `date` (`YYYY-MM`), `value`. Months after the download date were dropped.

To refresh the data, download the CPI and ER datasets again from data.imf.org and re-extract the same series codes.

### Live IMF API (optional)

Choose **Live IMF API** in the sidebar to query `https://api.imf.org/external/sdmx/3.0` directly. The app tries CSV, JSON, and XML responses, then the SDMX 2.1 endpoint. Any series it can't retrieve falls back to the bundled file, with a warning on the page. The **IMF connection diagnostics** panel lists every request and its result. Successful responses are cached for 24 hours; failed requests are not cached.

### Optional IMF API key

Some IMF gateway configurations require a subscription key and answer requests without one with HTTP 404. If live requests return 404 for every country, request a key from the IMF API portal and add it as a Streamlit secret:

- **Streamlit Cloud:** App → Settings → Secrets:
  ```toml
  IMF_API_KEY = "your-key"
  ```
- **Locally:** create `.streamlit/secrets.toml` with the same line, or set the `IMF_API_KEY` environment variable.

The key is sent in the `Ocp-Apim-Subscription-Key` header. Never commit it to GitHub.

## Run locally

Requires **Python 3.12**.

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt`, `README.md`, and `imf_data.csv` to a GitHub repository.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app from the repository with `app.py` as the main file.
3. Under **Advanced settings**, set the Python version to **3.12**.
4. Deploy.

## Files

- `app.py`: the Streamlit app
- `requirements.txt`: Python dependencies
- `README.md`: this file
- `imf_data.csv`: monthly IMF CPI, HICP, and exchange-rate series used by the app

## Data license

Data are from the International Monetary Fund (https://data.imf.org) and subject to the IMF's terms of use (https://www.imf.org/external/terms.htm).
