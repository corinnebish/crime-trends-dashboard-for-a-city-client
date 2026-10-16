"""Streamlit dashboard: where reported crime in Los Angeles is rising or falling."""
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from credits import code_format, label_code, show_data_credit, show_data_dictionary
from hero import render_hero

st.set_page_config(page_title="The LA Crime Ledger", page_icon="🕵️", layout="wide")

PROCESSED = Path("data/processed")
LEVEL_AREA = "Area name"
LEVEL_CRIME = "Crime type"
FLAG_HIGH = "Unusually high"
CITY_LABEL = "Whole city"

# Old-time palette: newsprint paper, ink, police blue, wanted-poster red, brass gold
INK = "#1b1a17"
PAPER = "#f1e6cf"
BLUE = "#1f3a5f"
RED = "#8c2a1c"
GOLD = "#b8892b"
GRID = "rgba(27,26,23,0.12)"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rye&family=Special+Elite&family=Libre+Baskerville:wght@400;700&display=swap');
html, body, p, li, label, .stMarkdown, [data-testid="stCaptionContainer"] { font-family: 'Libre Baskerville', serif; }
h1, h2, h3, h4 { font-family: 'Rye', serif !important; letter-spacing: .03em; font-weight: 400 !important; color: #1b1a17; }
h2 { border-bottom: 3px double #1b1a17; padding-bottom: .3rem; }
.kicker { font-family: 'Special Elite', monospace; font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: #8c2a1c; margin: 1.4rem 0 .2rem; }
.lede { font-size: 1.12rem; line-height: 1.65; max-width: 62rem; }
.howto { font-size: .92rem; color: #4a4034; border-left: 4px solid #b8892b; padding: .3rem .8rem; margin: .2rem 0 1rem; }
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(ellipse at 10% 0%, rgba(184,137,43,.22), transparent 50%),
    radial-gradient(ellipse at 95% 30%, rgba(140,42,28,.10), transparent 45%),
    repeating-linear-gradient(0deg, rgba(27,26,23,.025) 0 2px, transparent 2px 5px),
    #f1e6cf;
}
[data-testid="stMetric"] { background: #f9f1de; border: 2px solid #1b1a17; border-radius: 6px; padding: 14px 16px;
  box-shadow: 4px 4px 0 #1b1a17; transition: transform .2s, box-shadow .2s; }
[data-testid="stMetric"]:hover { transform: translate(-2px,-4px); box-shadow: 7px 8px 0 #8c2a1c; }
[data-testid="stMetricLabel"] p { font-family: 'Special Elite', monospace; color: #4a4034; text-transform: uppercase; letter-spacing: .06em; font-size: .78rem; }
[data-testid="stMetricValue"] { font-family: 'Rye', serif; color: #1f3a5f; font-size: 1.6rem; }
.stTabs [data-baseweb="tab"] { font-family: 'Special Elite', monospace; font-size: .95rem; }
.stTabs [aria-selected="true"] { color: #8c2a1c !important; }
[data-testid="stExpander"] { border: 2px solid #1b1a17; border-radius: 6px; background: rgba(249,241,222,.8); }
.card { background: #f9f1de; border: 2px solid #1b1a17; border-radius: 6px; padding: 16px 20px; margin-bottom: 14px; box-shadow: 4px 4px 0 rgba(27,26,23,.85); }
.card b.tag { font-family: 'Special Elite', monospace; color: #8c2a1c; letter-spacing: .08em; text-transform: uppercase; }
@media (prefers-reduced-motion: no-preference) {
  .stTabs [data-baseweb="tab-panel"] { animation: fadeUp .55s ease both; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
  .card { transition: transform .2s; }
  .card:hover { transform: translateY(-3px); }
}
</style>
"""


@st.cache_data
def load_table(name):
    """Read one processed CSV file."""
    return pd.read_csv(PROCESSED / name)


@st.cache_data
def load_series():
    """Read the monthly series and parse its month column."""
    df = load_table("monthly_series.csv")
    df["month"] = pd.to_datetime(df["month"])
    return df


@st.cache_data
def load_findings():
    """Read findings.json from the processed folder, or return an empty dict."""
    path = PROCESSED / "findings.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_int(value):
    """Format a whole number with thousands separators."""
    return f"{int(value):,}"


def computed_metrics(area_map, series):
    """Build the headline metric cards from the data when findings.json is absent."""
    last12 = area_map["last_12_months"].sum()
    prior12 = area_map["prior_12_months"].sum()
    pct = (last12 - prior12) / prior12 * 100 if prior12 else float("nan")
    biggest = area_map.loc[area_map["change_12m"].abs().idxmax()]
    return [
        {"label": "Incidents analyzed", "value": fmt_int(area_map["total_incidents"].sum()),
         "explanation": "Reported incidents counted across all areas and months."},
        {"label": "Last 12 months vs the 12 before", "value": f"{pct:+.1f}%",
         "explanation": f"{fmt_int(last12)} incidents against {fmt_int(prior12)}."},
        {"label": "Unusual spikes flagged", "value": fmt_int((series["flag"] == FLAG_HIGH).sum()),
         "explanation": "Months that ran well above the usual level of the prior 12 months."},
        {"label": "Biggest area change", "value": f"{biggest['AREA NAME']} ({int(biggest['change_12m']):+,})",
         "explanation": "The area whose 12-month count moved the most."},
    ]


def style(fig, height=430):
    """Apply the shared transparent, newsprint look to a Plotly figure."""
    fig.update_layout(
        template="simple_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Libre Baskerville, serif", color=INK, size=13),
        margin=dict(l=10, r=10, t=60, b=10), height=height,
        title=dict(font=dict(size=18)), hoverlabel=dict(bgcolor=PAPER, font_color=INK),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=INK)
    fig.update_yaxes(gridcolor=GRID, linecolor=INK)
    return fig


def how_to_read(text):
    """Show the one-sentence reading guide under a chart."""
    st.markdown(f'<div class="howto">{text}</div>', unsafe_allow_html=True)


def code_column(level):
    """Return the original column name that holds the names for a series level."""
    return "AREA NAME" if level == LEVEL_AREA else "Crm Cd Desc"


def trend_chart(series):
    """Line chart of monthly incidents for the whole city or one area."""
    areas = sorted(series.loc[series["level"] == LEVEL_AREA, "name"].unique())
    area_fmt = code_format("AREA NAME")
    choice = st.selectbox("Show reported incidents for", [CITY_LABEL] + areas,
                          format_func=lambda v: v if v == CITY_LABEL else area_fmt(v))
    rows = series[series["level"] == LEVEL_AREA]
    if choice != CITY_LABEL:
        rows = rows[rows["name"] == choice]
    monthly = rows.groupby("month", as_index=False)["incidents"].sum()
    if monthly.empty:
        st.info("No incidents to show for this choice.")
        return
    shown = CITY_LABEL if choice == CITY_LABEL else label_code("AREA NAME", choice)
    peak = monthly.loc[monthly["incidents"].idxmax()]
    low = monthly.iloc[-1]
    fig = go.Figure(go.Scatter(
        x=monthly["month"], y=monthly["incidents"], mode="lines+markers",
        line=dict(color=BLUE, width=3), marker=dict(size=5, color=BLUE),
        hovertemplate="%{x|%b %Y}: %{y:,} incidents<extra></extra>"))
    fig.update_layout(title=f"{shown}: busiest month was {peak['month']:%b %Y}, latest month was {fmt_int(low['incidents'])} incidents")
    fig.update_xaxes(title="Month the incident happened")
    fig.update_yaxes(title="Reported incidents per month", tickformat=",", rangemode="tozero")
    st.plotly_chart(style(fig), use_container_width=True, config={"displayModeBar": False})
    how_to_read("Each dot is one month. Hover over a dot to see its exact count. "
                "Recent months can look low because late reports may not be in yet.")


def map_chart(area_map):
    """Scatter plot of areas at their map position, coloured by 12-month change."""
    data = area_map[(area_map["LAT"] != 0) & (area_map["LON"] != 0)].dropna(subset=["pct_change_12m"]).copy()
    if data.empty:
        st.info("No areas have map positions and a 12-month change.")
        return
    data["Area"] = [label_code("AREA NAME", v) for v in data["AREA NAME"]]
    data["size"] = data["last_12_months"].clip(lower=1)
    labels = {"pct_change_12m": "Change over 12 months (%)", "last_12_months": "Incidents in last 12 months",
              "change_12m": "Change in incidents"}
    fig = px.scatter(data, x="LON", y="LAT", size="size", color="pct_change_12m", text="Area",
                     hover_name="Area", size_max=38, labels=labels,
                     hover_data={"LON": False, "LAT": False, "size": False, "pct_change_12m": ":.1f",
                                 "last_12_months": ":,", "change_12m": ":,"},
                     color_continuous_scale=[BLUE, "#efe3c8", RED], color_continuous_midpoint=0)
    fig.update_traces(textposition="top center", textfont=dict(size=10, color=INK))
    stretch = 1 / math.cos(math.radians(data["LAT"].mean()))  # keeps north-south and east-west distances true
    fig.update_yaxes(title="Latitude (degrees north)", scaleanchor="x", scaleratio=stretch)
    fig.update_xaxes(title="Longitude (degrees east, negative means west)")
    fig.update_layout(title="Areas drawn where their incidents cluster: blue fell, red rose",
                      coloraxis_colorbar=dict(title="Change over 12 months", ticksuffix="%"))
    st.plotly_chart(style(fig, 560), use_container_width=True, config={"displayModeBar": False})
    how_to_read("Each bubble is a police area placed at the middle of its incidents. Bigger bubbles had more incidents in the last 12 months. "
                "Hover over a bubble for its numbers. There is no street map, only positions.")


def area_bar_chart(area_map):
    """Horizontal bars of each area's 12-month change in incidents."""
    data = area_map.copy()
    data["Area"] = [label_code("AREA NAME", v) for v in data["AREA NAME"]]
    data["Direction"] = data["change_12m"].apply(lambda v: "Rose" if v > 0 else "Fell or stayed level")
    data = data.sort_values("change_12m", ascending=False)
    fig = px.bar(data, x="change_12m", y="Area", color="Direction", orientation="h",
                 color_discrete_map={"Rose": RED, "Fell or stayed level": BLUE},
                 labels={"change_12m": "Change in incidents", "Direction": "Direction"},
                 hover_data={"last_12_months": ":,", "prior_12_months": ":,", "Direction": False})
    fig.update_yaxes(title="Police area", autorange="reversed")
    fig.update_xaxes(title="Change in reported incidents (last 12 months minus the 12 before)", tickformat=",")
    fig.update_layout(title="Which areas moved the most in the last 12 months")
    st.plotly_chart(style(fig, 620), use_container_width=True, config={"displayModeBar": False})
    how_to_read("Bars to the right mean more incidents than a year earlier. Bars to the left mean fewer. Hover for both 12-month totals.")


def crime_bar_chart(crimes):
    """Bars of the crime types whose 12-month counts moved the most."""
    view = st.radio("Show the crime types with the", ["Biggest moves", "Biggest rises", "Biggest falls"], horizontal=True)
    count = st.slider("How many crime types", 5, 20, 10)
    data = crimes.copy()
    if view == "Biggest rises":
        data = data[data["change_12m"] > 0].nlargest(count, "change_12m")
    elif view == "Biggest falls":
        data = data[data["change_12m"] < 0].nsmallest(count, "change_12m")
    else:
        data = data.reindex(data["change_12m"].abs().nlargest(count).index)
    if data.empty:
        st.info("No crime types match this view.")
        return
    data["Crime type"] = [label_code("Crm Cd Desc", v) for v in data["Crm Cd Desc"]]
    data["Direction"] = data["change_12m"].apply(lambda v: "Rose" if v > 0 else "Fell or stayed level")
    data = data.sort_values("change_12m")
    fig = px.bar(data, x="change_12m", y="Crime type", color="Direction", orientation="h",
                 color_discrete_map={"Rose": RED, "Fell or stayed level": BLUE},
                 labels={"change_12m": "Change in incidents"},
                 hover_data={"last_12_months": ":,", "prior_12_months": ":,", "pct_change_12m": ":.1f", "Direction": False})
    fig.update_xaxes(title="Change in reported incidents over 12 months", tickformat=",")
    fig.update_yaxes(title="")
    fig.update_layout(title=f"{view}: the {len(data)} crime types that changed the most")
    st.plotly_chart(style(fig, 150 + 42 * len(data)), use_container_width=True, config={"displayModeBar": False})
    how_to_read("Red bars rose, blue bars fell. Longer bars are bigger changes in the number of incidents. Hover to see the percent change too.")


def spike_chart(series):
    """Line chart with a usual-range band and red dots on unusually high months."""
    levels = [v for v in (LEVEL_AREA, LEVEL_CRIME) if v in set(series["level"])]
    level = st.radio("Look at", levels, horizontal=True, format_func=code_format("level"))
    pool = series[series["level"] == level]
    flagged_all = pool[pool["flag"] == FLAG_HIGH]
    names = sorted(pool["name"].unique())
    default = flagged_all.loc[flagged_all["z_score"].idxmax(), "name"] if not flagged_all.empty else names[0]
    name_fmt = code_format(code_column(level))
    name = st.selectbox("Pick one to inspect", names, index=names.index(default), format_func=name_fmt)
    one = pool[pool["name"] == name].sort_values("month")
    base = one.dropna(subset=["baseline_mean", "baseline_std"])
    if base.empty:
        st.info("This series has no usual range yet. It needs 12 earlier months.")
        return
    upper = base["baseline_mean"] + 3 * base["baseline_std"]
    lower = (base["baseline_mean"] - 3 * base["baseline_std"]).clip(lower=0)
    hits = one[one["flag"] == FLAG_HIGH]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=base["month"], y=upper, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=base["month"], y=lower, mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(184,137,43,0.28)", name="Usual range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=one["month"], y=one["incidents"], mode="lines", name="Incidents",
                             line=dict(color=BLUE, width=3), hovertemplate="%{x|%b %Y}: %{y:,} incidents<extra></extra>"))
    fig.add_trace(go.Scatter(x=hits["month"], y=hits["incidents"], mode="markers", name="Unusual spike",
                             marker=dict(color=RED, size=13, symbol="star", line=dict(color=INK, width=1)),
                             customdata=hits[["baseline_mean"]],
                             hovertemplate="%{x|%b %Y}: %{y:,} incidents, usual %{customdata[0]:,.0f}<extra></extra>"))
    fig.update_xaxes(title="Month the incident happened")
    fig.update_yaxes(title="Reported incidents per month", tickformat=",", rangemode="tozero")
    fig.update_layout(title=f"{label_code(code_column(level), name)}: {len(hits)} unusual spike month(s)")
    st.plotly_chart(style(fig), use_container_width=True, config={"displayModeBar": False})
    how_to_read("The gold band is the usual range from the prior 12 months. Red stars are months far above it. Hover on a star to compare with the usual level.")
    show_spike_table(flagged_all, level)


def show_spike_table(flagged, level):
    """Show the strongest flagged months for the chosen level as a table."""
    st.markdown("**The strongest spikes in this view**")
    if flagged.empty:
        st.info("No months were flagged for this view.")
        return
    top = flagged.nlargest(15, "z_score")
    col = code_column(level)
    table = pd.DataFrame({
        "Name": [label_code(col, v) for v in top["name"]],
        "Month": top["month"].dt.strftime("%b %Y"),
        "Incidents": top["incidents"].map(fmt_int),
        "Usual level": top["baseline_mean"].round(0).map(fmt_int),
        "Spike score": top["z_score"].round(1),
    })
    st.dataframe(table, hide_index=True, use_container_width=True)


def section_head(number, kicker, headline):
    """Print a numbered kicker and a section headline."""
    st.markdown(f'<div class="kicker">{number} - {kicker}</div>', unsafe_allow_html=True)
    st.header(headline)


def render_findings(findings):
    """Show the 'What this means' cards."""
    items = findings.get("findings", [])
    if not items:
        st.info("The written findings file was not found, so only computed numbers are shown.")
    for item in items:
        st.markdown(
            f'<div class="card"><b class="tag">The finding</b><br>{item["statement"]}<br><br>'
            f'<b class="tag">The evidence</b><br>{item["evidence"]}<br><br>'
            f'<b class="tag">What to do with it</b><br>{item["so_what"]}</div>', unsafe_allow_html=True)


def render_text_sections(findings):
    """Show how-to-read, method notes, limits and the glossary."""
    with st.expander("How to read this dashboard"):
        st.markdown(
            "- **Incident** means one crime report logged by the police.\n"
            "- **Counts** are numbers of incidents per month, never rates per person.\n"
            "- **12-month change** compares the latest 12 full months with the 12 months before.\n"
            "- **Percent** (%) shows a change as a share of the earlier count.\n"
            "- **Red** always means a rise or a spike. **Blue** always means a fall or a normal line.\n"
            "- Hover over any chart to see exact numbers.")
    section_head("05", "THE METHOD", "How it was done")
    notes = findings.get("method_notes", [])
    for note in notes:
        st.markdown(f"**{note['method']}**  \n{note['why']}  \n*Another way:* {note['alternative']}")
    if not notes:
        st.caption("Method notes were not found in the data folder.")
    section_head("06", "THE FINE PRINT", "Limits of this data")
    for caveat in findings.get("caveats", []):
        st.markdown(f"- {caveat}")
    with st.expander("Glossary: every technical term used here"):
        st.markdown(
            "- **Aggregation:** adding up many rows into group totals, such as incidents per month.\n"
            "- **Anomaly or spike:** a month far above what is normal for that series.\n"
            "- **Usual level (baseline):** the average monthly count over the 12 months before.\n"
            "- **Standard deviation:** a measure of how much a count normally bounces around its average.\n"
            "- **Spike score (z-score):** how many standard deviations a month sits above its usual level.\n"
            "- **Usual range:** the usual level plus or minus 3 standard deviations.\n"
            "- **Month-to-month change:** this month's count minus last month's count.\n"
            "- **Latitude and longitude:** map coordinates, north-south and east-west, in degrees.\n"
            "- **LAPD:** the Los Angeles Police Department, which publishes the data.")


def main():
    """Build the whole dashboard page."""
    area_map = load_table("area_map.csv")
    crimes = load_table("crime_changes.csv")
    series = load_series()
    findings = load_findings()
    st.markdown(CSS, unsafe_allow_html=True)

    start, end = series["month"].min(), series["month"].max()
    render_hero(
        title="The LA Crime Ledger",
        eyebrow="CASE FILE - CITY OF LOS ANGELES",
        subtitle=f"Which crimes and areas are rising or falling, month by month, {start:%b %Y} to {end:%b %Y}.",
        stats=[
            {"value": int(area_map["total_incidents"].sum()), "label": "incidents on file"},
            {"value": int(area_map["AREA NAME"].nunique()), "label": "police areas"},
            {"value": int(series["month"].nunique()), "label": "months covered"},
            {"value": int((series["flag"] == FLAG_HIGH).sum()), "label": "unusual spikes flagged"},
        ],
        motif="particles",
        palette={"accent": "#d9a441", "accent2": "#b5392b", "bg": "#14110d", "bg2": "#2a2118", "text": "#f4e9d0"},
        dark=True, title_font="Rye", body_font="Special Elite", height=520)

    section_head("01", "THE QUESTION", findings.get("headline", "Where is reported crime rising or falling?"))
    st.markdown('<p class="lede">A city agency needs to know where to send its people. '
                'This ledger asks: <b>which crime types and areas are rising or falling from month to month, '
                'and where do the biggest changes happen?</b> It uses real police reports, counted and compared.</p>',
                unsafe_allow_html=True)

    metrics = findings.get("metrics") or computed_metrics(area_map, series)
    for col, metric in zip(st.columns(len(metrics)), metrics):
        col.metric(metric["label"], metric["value"], help=metric["explanation"])
        col.caption(metric["explanation"])

    section_head("02", "THE EVIDENCE", "Follow the trail through four exhibits")
    tab1, tab2, tab3, tab4 = st.tabs(["📈 The big picture", "🗺️ Where it moves", "🔎 Which crimes move", "🚨 Unusual spikes"])
    with tab1:
        st.subheader("Reported incidents fell sharply in recent months")
        trend_chart(series)
    with tab2:
        st.subheader("Nearly every area changed, but by very different amounts")
        map_chart(area_map)
        area_bar_chart(area_map)
    with tab3:
        st.subheader("A few crime types account for most of the change")
        crime_bar_chart(crimes)
    with tab4:
        st.subheader("Spikes are rare, so each one deserves a second look")
        spike_chart(series)

    section_head("03", "THE VERDICT", "What this means")
    render_findings(findings)
    render_text_sections(findings)


main()
show_data_dictionary()
show_data_credit()
