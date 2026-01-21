# versie 1.0.0 - Streamlit Heatmap voor ENTSO-E prijzen

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import streamlit as st

# --- CONFIGURATIE ---
TOKEN = "402f3440-9c49-4469-9ab2-eb35e0808626"
DOMAIN = "10YBE----------2"

# --- FUNCTIES ---
def get_entsoe_data(target_date):
    p_start = target_date.strftime("%Y%m%d0000")
    p_end   = target_date.strftime("%Y%m%d2359")
    params = {
        "securityToken": TOKEN,
        "documentType": "A44",
        "in_Domain": DOMAIN,
        "out_Domain": DOMAIN,
        "periodStart": p_start,
        "periodEnd": p_end
    }
    try:
        r = requests.get("https://web-api.tp.entsoe.eu/api", params=params, timeout=10)
        return r.content if r.status_code == 200 else None
    except:
        return None

def parse_xml(xml_content):
    try:
        root = ET.fromstring(xml_content)
        data = []
        for ts in root.findall('.//{*}TimeSeries'):
            period = ts.find('{*}Period')
            start_dt = datetime.strptime(
                period.find('{*}timeInterval/{*}start').text,
                "%Y-%m-%dT%H:%MZ"
            ).replace(tzinfo=timezone.utc)

            res = period.find('{*}resolution').text

            for point in period.findall('{*}Point'):
                pos = int(point.find('{*}position').text)
                price = float(point.find('{*}price.amount').text)

                if res == "PT15M":
                    ts_point = start_dt + timedelta(minutes=(pos - 1) * 15)
                else:
                    ts_point = start_dt + timedelta(hours=(pos - 1))

                data.append({
                    'timestamp': ts_point,
                    'priceMwh': price
                })

        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- STREAMLIT UI ---
st.title("🔌 Energieprijs Heatmap (ENTSO-E)")
st.write("Visualisatie van de uurprijzen voor België (Day-Ahead).")

# Datumselectie
default_date = datetime.now(timezone.utc).date() + timedelta(days=1)
target_date = st.date_input("Kies datum", default_date)

# Data ophalen
xml = get_entsoe_data(target_date)
if not xml or b"999" in xml:
    st.warning("Geen data voor gekozen datum. Probeer vandaag.")
    target_date = datetime.now(timezone.utc).date()
    xml = get_entsoe_data(target_date)

df = parse_xml(xml)

if df.empty:
    st.error("Geen data beschikbaar.")
else:
    df['local_time'] = df['timestamp'].dt.tz_convert(None) + timedelta(hours=1)
    df['uur'] = df['local_time'].dt.hour
    df['prijs'] = (df['priceMwh'] / 1000).round(4)
    final = df.groupby('uur')['prijs'].mean().reset_index()

    # --- VISUALISATIE ---
    fig, ax = plt.subplots(figsize=(10, 8))

    norm = mcolors.Normalize(vmin=final['prijs'].min(), vmax=final['prijs'].max())
    cmap = plt.get_cmap('RdYlGn_r')
    colors = [cmap(norm(v)) for v in final['prijs']]

    widths = (final['prijs'].max() - final['prijs']) + (final['prijs'].max() * 0.1)

    bars = ax.barh(final['uur'], widths, color=colors, edgecolor='black', height=0.8)

    for i, bar in enumerate(bars):
        ax.text(
            bar.get_width() / 2,
            bar.get_y() + bar.get_height() / 2,
            f"{final['prijs'][i]:.4f} €",
            va='center', ha='center', fontweight='bold', color='black'
        )

    ax.set_yticks(range(0, 24))
    ax.set_ylabel("Uur van de dag")
    ax.set_xlabel("Besparingspotentieel (Langer is beter)")
    ax.set_title(f"Energie Heatmap: {target_date}")
    ax.invert_yaxis()
    ax.grid(axis='x', linestyle='--', alpha=0.7)

    st.pyplot(fig)