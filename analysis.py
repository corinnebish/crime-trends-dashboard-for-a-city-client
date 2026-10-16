"""Clean the Los Angeles crime data and build dashboard-ready tables, findings and a data dictionary."""
import json
from pathlib import Path

import pandas as pd

RAW_FILE = Path("data/raw/export.csv")
OUT_DIR = Path("data/processed")
USE_COLS = ["DR_NO", "DATE OCC", "AREA NAME", "Crm Cd Desc", "LAT", "LON"]

BASELINE_MONTHS = 12   # a "usual level" is the average of the 12 months before
Z_CUTOFF = 3.0         # how many standard deviations above usual counts as a spike
MIN_JUMP = 20          # ignore spikes smaller than this many incidents (too small to matter)
MIN_PCT_JUMP = 20.0    # ignore spikes smaller than this percent above usual
TOP_CRIMES = 25        # crime types kept in the area-by-crime table to keep files small
MAX_OUTPUT_MB = 20

LEVEL_CITY = "Whole city"
LEVEL_AREA = "Area name"
LEVEL_CRIME = "Crime type"
FLAG_HIGH = "Unusually high"
FLAG_NORMAL = "Within usual range"


# ---------------------------------------------------------------- loading and cleaning

def load_raw():
    """Read only the columns this analysis needs from the raw export."""
    return pd.read_csv(RAW_FILE, usecols=USE_COLS)


def add_month_and_drop_partial(df):
    """Add a month column and drop months that are only partly covered by the data."""
    df = df.assign(month=df["DATE OCC"].dt.to_period("M").dt.to_timestamp())
    first, last = df["DATE OCC"].min(), df["DATE OCC"].max()
    partial = []
    if first.day > 1:
        partial.append(first.to_period("M").to_timestamp())
    if not last.is_month_end:
        partial.append(last.to_period("M").to_timestamp())
    kept = df[~df["month"].isin(partial)]
    return kept, len(df) - len(kept), partial


def clean(raw):
    """Fix types, remove duplicates and bad rows, and report what was removed and why."""
    stats = {"raw_rows": len(raw)}

    # The record number should be unique, so a repeat is the same incident twice.
    df = raw.drop_duplicates(subset="DR_NO").copy()
    stats["duplicates"] = len(raw) - len(df)
    print(f"Removed {stats['duplicates']:,} rows with a repeated record number (DR_NO): same incident twice.")

    # The first 11 characters hold the date. The time part is always midnight, so it is skipped.
    df["DATE OCC"] = pd.to_datetime(df["DATE OCC"].str[:11], format="%Y %b %d", errors="coerce")
    before = len(df)
    df = df.dropna(subset=["DATE OCC", "AREA NAME", "Crm Cd Desc"])
    stats["missing_key_fields"] = before - len(df)
    print(f"Removed {stats['missing_key_fields']:,} rows with no usable date, area or crime type: they cannot be counted.")

    for col in ["AREA NAME", "Crm Cd Desc"]:
        df[col] = df[col].str.strip()

    # A coordinate of 0 is not a real place in Los Angeles, so it is treated as missing.
    # The row stays in the counts and is only left out of the map position.
    zero_coords = (df["LAT"] == 0) | (df["LON"] == 0)
    stats["zero_coords"] = int(zero_coords.sum())
    df.loc[zero_coords, ["LAT", "LON"]] = float("nan")
    print(f"Set {stats['zero_coords']:,} zero coordinates to missing (rows kept for counts, left out of map positions).")

    # A partly covered month would look like a fake drop in crime.
    df, stats["partial_rows"], partial = add_month_and_drop_partial(df)
    months = ", ".join(f"{m:%b %Y}" for m in partial) or "none"
    print(f"Removed {stats['partial_rows']:,} rows from months only partly covered ({months}): they would look like a false drop.")

    stats["rows_kept"] = len(df)
    print(f"Rows kept for analysis: {len(df):,}")
    return df, stats


# ---------------------------------------------------------------- aggregation

def monthly_counts(df, name_col, level, all_months):
    """Count incidents per month for each value of name_col, filling empty months with zero."""
    counts = df.groupby(["month", name_col]).size().unstack(fill_value=0)
    counts = counts.reindex(all_months, fill_value=0)
    long = counts.stack().rename("incidents").reset_index()
    long.columns = ["month", "name", "incidents"]
    long.insert(0, "level", level)
    return long


def city_counts(df, all_months):
    """Count incidents per month for the whole city."""
    counts = df.groupby("month").size().reindex(all_months, fill_value=0)
    out = counts.rename("incidents").reset_index()
    out.columns = ["month", "incidents"]
    out.insert(0, "name", "Los Angeles")
    out.insert(0, "level", LEVEL_CITY)
    return out


def add_trend_columns(series):
    """Add month-to-month change, a usual-level baseline and a spike flag to each series."""
    series = series.sort_values(["level", "name", "month"]).reset_index(drop=True)
    grouped = series.groupby(["level", "name"])["incidents"]
    series["previous_month"] = grouped.shift(1)
    series["mom_change"] = series["incidents"] - series["previous_month"]
    series["mom_pct_change"] = (series["mom_change"] / series["previous_month"].where(series["previous_month"] > 0)) * 100

    # shift(1) keeps the month being tested out of its own baseline
    series["baseline_mean"] = grouped.transform(lambda s: s.shift(1).rolling(BASELINE_MONTHS).mean())
    series["baseline_std"] = grouped.transform(lambda s: s.shift(1).rolling(BASELINE_MONTHS).std())
    series["z_score"] = (series["incidents"] - series["baseline_mean"]) / series["baseline_std"].where(series["baseline_std"] > 0)

    jump = series["incidents"] - series["baseline_mean"]
    pct_jump = jump / series["baseline_mean"].where(series["baseline_mean"] > 0) * 100
    is_spike = (series["z_score"] >= Z_CUTOFF) & (jump >= MIN_JUMP) & (pct_jump >= MIN_PCT_JUMP)
    series["flag"] = is_spike.map({True: FLAG_HIGH, False: FLAG_NORMAL})

    for col in ["mom_pct_change", "baseline_mean", "baseline_std", "z_score"]:
        series[col] = series[col].round(2)
    return series


def period_change(series, level, name_col):
    """Compare the last 12 months with the 12 months before, for each name at one level."""
    months = sorted(series["month"].unique())
    if len(months) < 24:
        raise ValueError("Need at least 24 full months to compare two 12-month periods.")
    last, prior = months[-12:], months[-24:-12]
    sub = series[series["level"] == level]
    table = pd.DataFrame({
        "last_12_months": sub[sub["month"].isin(last)].groupby("name")["incidents"].sum(),
        "prior_12_months": sub[sub["month"].isin(prior)].groupby("name")["incidents"].sum(),
    }).fillna(0).astype(int)
    table["change_12m"] = table["last_12_months"] - table["prior_12_months"]
    table["pct_change_12m"] = (table["change_12m"] / table["prior_12_months"].where(table["prior_12_months"] > 0) * 100).round(1)
    return table.rename_axis(name_col).reset_index()


def build_area_map(df, area_changes):
    """Join 12-month changes to a typical map position and total count for each area."""
    position = df.groupby("AREA NAME")[["LAT", "LON"]].median().round(4)  # median resists stray points
    totals = df.groupby("AREA NAME").size().rename("total_incidents")
    area_map = area_changes.merge(position, on="AREA NAME", how="left").merge(totals, on="AREA NAME", how="left")
    cols = ["AREA NAME", "LAT", "LON", "total_incidents", "last_12_months",
            "prior_12_months", "change_12m", "pct_change_12m"]
    return area_map[cols]


def build_area_crime(df):
    """Count incidents per month, area and crime type for the most common crime types."""
    top = df["Crm Cd Desc"].value_counts().head(TOP_CRIMES).index
    sub = df[df["Crm Cd Desc"].isin(top)]
    return sub.groupby(["month", "AREA NAME", "Crm Cd Desc"]).size().rename("incidents").reset_index()


def build_tables(df):
    """Build every table the dashboard needs and return them by file name."""
    all_months = sorted(df["month"].unique())
    series = pd.concat([
        city_counts(df, all_months),
        monthly_counts(df, "AREA NAME", LEVEL_AREA, all_months),
        monthly_counts(df, "Crm Cd Desc", LEVEL_CRIME, all_months),
    ], ignore_index=True)
    series = add_trend_columns(series)
    area_changes = period_change(series, LEVEL_AREA, "AREA NAME")
    crime_changes = period_change(series, LEVEL_CRIME, "Crm Cd Desc")
    return {
        "monthly_series.csv": series,
        "area_map.csv": build_area_map(df, area_changes),
        "crime_changes.csv": crime_changes,
        "area_crime_monthly.csv": build_area_crime(df),
    }


def save_tables(tables):
    """Write tables to data/processed and check the total size stays small."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        out = table.copy()
        out["month"] = out["month"].dt.strftime("%Y-%m-%d") if "month" in out else None
        if out["month"].isna().all():
            out = out.drop(columns="month")
        out.to_csv(OUT_DIR / name, index=False)
    total_mb = sum(p.stat().st_size for p in OUT_DIR.glob("*.csv")) / 1e6
    print(f"Saved {len(tables)} tables, {total_mb:.1f} MB in total.")
    if total_mb > MAX_OUTPUT_MB:
        raise ValueError("Processed tables are larger than the size limit.")


# ---------------------------------------------------------------- findings

def pct_text(value):
    """Format a percent change with a sign."""
    return f"{value:+.1f}%"


def build_metrics(stats, series, area_changes):
    """Create the headline KPI cards."""
    city = series[series["level"] == LEVEL_CITY].sort_values("month")
    latest = city.iloc[-1]
    last12 = city["incidents"].tail(12).sum()
    prior12 = city["incidents"].iloc[-24:-12].sum()
    city_pct = (last12 - prior12) / prior12 * 100
    flagged = (series["flag"] == FLAG_HIGH).sum()
    top_area = area_changes.loc[area_changes["change_12m"].abs().idxmax()]
    return [
        {"label": "Incidents analyzed", "value": f"{stats['rows_kept']:,}",
         "explanation": "Reported incidents left after cleaning, across all months and areas."},
        {"label": f"Incidents in {latest['month']:%b %Y}", "value": f"{int(latest['incidents']):,}",
         "explanation": f"Count in the latest full month. That is {pct_text(latest['mom_pct_change'])} compared with the month before."},
        {"label": "Last 12 months vs the 12 before", "value": pct_text(city_pct),
         "explanation": f"The city logged {int(last12):,} incidents in the last 12 full months and {int(prior12):,} in the 12 months before."},
        {"label": "Unusual spikes flagged", "value": f"{flagged:,}",
         "explanation": f"Months where an area, crime type or the whole city ran well above its usual level of the prior {BASELINE_MONTHS} months."},
        {"label": "Biggest area change", "value": f"{top_area['AREA NAME']} ({int(top_area['change_12m']):+,})",
         "explanation": "The area whose 12-month count moved the most, in either direction, compared with the 12 months before."},
    ]


def spike_finding(series):
    """Describe the largest flagged spike among areas and crime types."""
    flagged = series[(series["flag"] == FLAG_HIGH)]
    detail = flagged[flagged["level"] != LEVEL_CITY].copy()
    counts = flagged["level"].value_counts()
    if detail.empty:
        return {"statement": "No area or crime type rose far above its usual level in any month.",
                "evidence": f"Spike rule: at least {Z_CUTOFF:.0f} standard deviations above the prior {BASELINE_MONTHS}-month average.",
                "so_what": "No special follow-up is needed. Keep monitoring monthly."}
    detail["excess"] = detail["incidents"] - detail["baseline_mean"]
    top = detail.loc[detail["excess"].idxmax()]
    return {
        "statement": f"Spikes are rare but real. The largest was {top['name']} in {top['month']:%b %Y}.",
        "evidence": (f"{top['name']} had {int(top['incidents']):,} incidents against a usual {top['baseline_mean']:.0f}. "
                     f"Flagged months: {counts.get(LEVEL_AREA, 0)} area-months, {counts.get(LEVEL_CRIME, 0)} crime-type-months, "
                     f"{counts.get(LEVEL_CITY, 0)} whole-city months."),
        "so_what": "Review the flagged months first. Check whether a real event, a change in reporting or a data entry batch caused each jump.",
    }


def build_findings(series, area_changes, crime_changes):
    """Create the plain-English findings, each with evidence and a suggested action."""
    city = series[series["level"] == LEVEL_CITY].sort_values("month")
    last12 = city["incidents"].tail(12).sum()
    prior12 = city["incidents"].iloc[-24:-12].sum()
    city_pct = (last12 - prior12) / prior12 * 100
    area_up = area_changes.loc[area_changes["change_12m"].idxmax()]
    area_down = area_changes.loc[area_changes["change_12m"].idxmin()]
    crime_up = crime_changes.loc[crime_changes["change_12m"].idxmax()]
    crime_down = crime_changes.loc[crime_changes["change_12m"].idxmin()]

    latest_month = city["month"].max()
    latest = series[series["month"] == latest_month]
    area_now = latest[latest["level"] == LEVEL_AREA]
    crime_now = latest[latest["level"] == LEVEL_CRIME]
    area_move = area_now.loc[area_now["mom_change"].abs().idxmax()]
    crime_move = crime_now.loc[crime_now["mom_change"].abs().idxmax()]

    return [
        {"statement": f"Citywide incidents changed {pct_text(city_pct)} over the last 12 full months compared with the 12 months before.",
         "evidence": f"{int(last12):,} incidents in the last 12 months against {int(prior12):,} in the 12 months before.",
         "so_what": "Use this as the baseline for planning. Judge each area against the citywide direction, not in isolation."},
        {"statement": f"{area_up['AREA NAME']} moved up the most and {area_down['AREA NAME']} moved down the most over the last 12 months.",
         "evidence": (f"{area_up['AREA NAME']}: {int(area_up['change_12m']):+,} incidents ({pct_text(area_up['pct_change_12m'])}). "
                      f"{area_down['AREA NAME']}: {int(area_down['change_12m']):+,} incidents ({pct_text(area_down['pct_change_12m'])})."),
         "so_what": f"Look first at {area_up['AREA NAME']} when deciding where to add resources. Study what is working in {area_down['AREA NAME']}."},
        {"statement": f"{crime_up['Crm Cd Desc']} moved up the most and {crime_down['Crm Cd Desc']} moved down the most among crime types.",
         "evidence": (f"{crime_up['Crm Cd Desc']}: {int(crime_up['change_12m']):+,} ({pct_text(crime_up['pct_change_12m'])}). "
                      f"{crime_down['Crm Cd Desc']}: {int(crime_down['change_12m']):+,} ({pct_text(crime_down['pct_change_12m'])})."),
         "so_what": "Point prevention work at the crime types with the biggest increases, since they add the most new cases."},
        spike_finding(series),
        {"statement": f"In {latest_month:%b %Y}, the biggest month-to-month moves were in {area_move['name']} and {crime_move['name']}.",
         "evidence": (f"{area_move['name']}: {int(area_move['mom_change']):+,} incidents versus the month before. "
                      f"{crime_move['name']}: {int(crime_move['mom_change']):+,} incidents."),
         "so_what": "Treat one month as a prompt to look closer, not as proof of a trend. Check the next month before changing plans."},
    ]


def build_method_notes():
    """Explain each method, why it fits and what else could be used."""
    return [
        {"method": "SQL-style aggregation (group and count)",
         "why": "The raw file has one row per incident. Counting rows by month, area and crime type turns it into small tables a dashboard can read quickly.",
         "alternative": "A database could do the same counts. It adds setup work and is not needed for one file."},
        {"method": "Geographic analysis",
         "why": "Each area gets a map point (the median of its incident coordinates) and a 12-month change, so the client can see where counts move.",
         "alternative": "Drawing area boundaries would be more exact, but the data has no boundary file and only point coordinates."},
        {"method": "Anomaly detection with a trailing baseline",
         "why": f"A month is flagged when it is at least {Z_CUTOFF:.0f} standard deviations above the average of the prior {BASELINE_MONTHS} months, and also {MIN_JUMP}+ incidents and {MIN_PCT_JUMP:.0f}%+ above it. This is simple to explain and ignores tiny counts.",
         "alternative": "Forecasting models such as seasonal models could handle seasons better. They are harder to explain and need more tuning for little gain here."},
    ]


def build_caveats(stats, series):
    """List the limits of this analysis, with numbers computed from the data."""
    months = sorted(series["month"].unique())
    return [
        "These are reported incidents, not all crime. Changes can come from reporting habits as well as real changes in crime.",
        "Counts are by the date the incident happened. Recent months may be incomplete if incidents are reported late.",
        "The data has no population figures, so counts are not rates per resident. Larger areas will have more incidents.",
        "The data only has area names, not finer neighborhood names, so 'neighborhood' here means the named area.",
        f"{stats['zero_coords']:,} rows had a coordinate of 0. They are counted but have no place on the map.",
        f"{stats['duplicates']:,} repeated record numbers were removed. {stats['partial_rows']:,} rows from partly covered months were left out.",
        "Some crime type descriptions are cut off in the source file, so a few names look shortened.",
        f"A spike flag needs {BASELINE_MONTHS} earlier months, so no flags exist before {months[BASELINE_MONTHS]:%b %Y}.",
        "The data shows what changed, not why. Causes need local knowledge.",
    ]


def write_findings(stats, series, tables):
    """Write findings.json with the headline, metrics, findings, methods and caveats."""
    area_changes = tables["area_map.csv"]
    crime_changes = tables["crime_changes.csv"]
    city = series[series["level"] == LEVEL_CITY].sort_values("month")
    last12 = city["incidents"].tail(12).sum()
    prior12 = city["incidents"].iloc[-24:-12].sum()
    city_pct = (last12 - prior12) / prior12 * 100
    top_area = area_changes.loc[area_changes["change_12m"].abs().idxmax()]
    direction = "rose" if city_pct >= 0 else "fell"
    findings = {
        "headline": (f"Reported incidents in Los Angeles {direction} {abs(city_pct):.1f}% in the last 12 full months, "
                     f"and {top_area['AREA NAME']} changed the most among areas."),
        "rows_analyzed": int(stats["rows_kept"]),
        "date_range": f"{city['month'].min():%b %Y} to {city['month'].max():%b %Y}",
        "metrics": build_metrics(stats, series, area_changes),
        "findings": build_findings(series, area_changes, crime_changes),
        "method_notes": build_method_notes(),
        "caveats": build_caveats(stats, series),
    }
    (OUT_DIR / "findings.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- data dictionary

NOT_DEFINED = "Not explained by the data source"

COLUMN_INFO = {
    "level": ("Series level", "Says whether a row counts the whole city, one area or one crime type. It lets the dashboard filter the long table.", "", "calculated"),
    "name": ("Series name", "The name of the city, area or crime type that the row counts. It goes with the level column.", "", "calculated"),
    "month": ("Month", "The first day of the month in which the incidents happened, taken from the occurrence date. It is the time axis for every trend.", "date", "calculated"),
    "incidents": ("Incidents", "The number of reported incidents counted in that row. It is the main measure used in every chart.", "incidents", "calculated"),
    "previous_month": ("Incidents in previous month", "The incident count of the same series in the month before. It is empty for the first month.", "incidents", "calculated"),
    "mom_change": ("Change from previous month", "Incidents this month minus incidents last month. A positive number means a rise.", "incidents", "calculated"),
    "mom_pct_change": ("Percent change from previous month", "The month-to-month change as a percent of last month's count. It is empty when last month had no incidents.", "percent", "calculated"),
    "baseline_mean": ("Usual level", "The average monthly count over the 12 months before this one. It shows what is normal for that series.", "incidents", "calculated"),
    "baseline_std": ("Usual variation", "How much the monthly count normally moves around the usual level, over the prior 12 months. A larger value means a noisier series.", "incidents", "calculated"),
    "z_score": ("Spike score", "How many standard deviations this month sits above its usual level. Higher values mean a more unusual month.", "standard deviations", "calculated"),
    "flag": ("Spike flag", "Marks months that are far above the usual level by score, size and percent. Other months are marked as within the usual range.", "", "calculated"),
    "AREA NAME": ("Area name", "The name of the area the incident is recorded under in the data file. It is used to compare places across the city.", "", "data"),
    "Crm Cd Desc": ("Crime type", "The text description of the crime type recorded for the incident. Some descriptions are cut off in the source file.", "", "data"),
    "LAT": ("Latitude", "The middle latitude of all incidents recorded in the area. It places the area on the map.", "degrees", "calculated"),
    "LON": ("Longitude", "The middle longitude of all incidents recorded in the area. It places the area on the map.", "degrees", "calculated"),
    "total_incidents": ("Total incidents", "All incidents counted for the area across every month analyzed. It shows the overall size of the area's caseload.", "incidents", "calculated"),
    "last_12_months": ("Incidents in last 12 months", "Incidents counted in the most recent 12 full months. It is the current period in the comparison.", "incidents", "calculated"),
    "prior_12_months": ("Incidents in prior 12 months", "Incidents counted in the 12 full months before the latest 12. It is the comparison period.", "incidents", "calculated"),
    "change_12m": ("Change over 12 months", "Incidents in the last 12 months minus incidents in the 12 months before. A positive number means a rise.", "incidents", "calculated"),
    "pct_change_12m": ("Percent change over 12 months", "The 12-month change as a percent of the earlier 12 months. It is empty when the earlier period had no incidents.", "percent", "calculated"),
}


def example_value(name, saved):
    """Take a real example value for a column from the first saved table that has it."""
    for table in saved.values():
        if name in table.columns:
            return str(table[name].dropna().iloc[0])
    raise KeyError(name)


def short_code_entries(saved):
    """List every distinct value of columns holding short codes (4 characters or fewer)."""
    entries = []
    for table in saved.values():
        for col in table.columns:
            if pd.api.types.is_numeric_dtype(table[col]):
                continue
            values = table[col].dropna().astype(str).unique()
            if len(values) and all(len(v) <= 4 for v in values):
                entries += [{"column": col, "code": v, "meaning": NOT_DEFINED, "source": "not defined"} for v in values]
    return entries


def write_dictionary():
    """Write data_dictionary.json covering every column of every saved table."""
    saved = {p.name: pd.read_csv(p) for p in sorted(OUT_DIR.glob("*.csv"))}
    names = list(dict.fromkeys(col for table in saved.values() for col in table.columns))
    missing = [n for n in names if n not in COLUMN_INFO]
    if missing:
        raise KeyError(f"Columns without a dictionary entry: {missing}")
    columns = []
    for name in names:
        label, meaning, unit, source = COLUMN_INFO[name]
        columns.append({"name": name, "label": label, "meaning": meaning, "unit": unit,
                        "example": example_value(name, saved), "source": source})
    dictionary = {
        "columns": columns,
        "codes": short_code_entries(saved),
        "notes": [
            "Area names and crime type descriptions come straight from the raw file. Their text was kept as stored.",
            "A month is a calendar month based on the date the incident happened, not the date it was reported.",
            "The area_crime_monthly table only has rows for months with at least one incident, and only for the most common crime types.",
        ],
    }
    (OUT_DIR / "data_dictionary.json").write_text(json.dumps(dictionary, indent=2, ensure_ascii=False))


def main():
    """Run the full pipeline: load, clean, aggregate, save, and describe the results."""
    raw = load_raw()
    df, stats = clean(raw)
    tables = build_tables(df)
    save_tables(tables)
    write_findings(stats, tables["monthly_series.csv"], tables)
    write_dictionary()
    print("Wrote findings.json and data_dictionary.json")


if __name__ == "__main__":
    main()
