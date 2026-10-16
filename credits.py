"""Trusted helpers shown on every dashboard: data source credit, plain-English data dictionary,
and readable labels for coded values. Written by Project Creator, not by the AI."""
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
NOT_DEFINED = "not explained by the data source"


@st.cache_data
def _dictionary() -> dict:
    path = ROOT / "data" / "processed" / "data_dictionary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"columns": [], "codes": []}


def show_data_credit() -> None:
    info = json.loads((ROOT / "data_credit.json").read_text(encoding="utf-8"))
    st.divider()
    st.caption(
        f"**Data source:** [{info['name']}]({info['landing_url']}), published by {info['publisher']}. "
        f"**License:** {info['license']}. This project is an independent portfolio piece and is not "
        "endorsed by the data publisher."
    )


def label_code(column: str, code) -> str:
    """'Sha Tin (ST)' when the source explains the code, otherwise 'S (not explained by the data source)'.
    Use it everywhere a coded value is shown: filters, legends, table cells, chart labels."""
    for item in _dictionary().get("codes", []):
        if item.get("column") == column and str(item.get("code")) == str(code):
            if item.get("source") != "not defined" and item.get("meaning"):
                return f"{item['meaning']} ({code})"
            break
    return f"{code} ({NOT_DEFINED})"


def code_format(column: str):
    """Pass as format_func=code_format("venue") to st.selectbox / st.multiselect / st.radio."""
    return lambda code: label_code(column, code)


def show_data_dictionary() -> None:
    """Plain-English guide to every column and code, for people who have never seen this data."""
    d = _dictionary()
    with st.expander("\U0001F4D8 Data dictionary: what every column and code means", expanded=False):
        st.caption("Written in plain English from the data source's own documentation. Where the source does "
                   "not explain something, this page says so instead of guessing.")
        cols = d.get("columns", [])
        if cols:
            st.markdown("**Columns**")
            rows = ["| What you see | What it means | Unit | Example | Where this comes from |", "|---|---|---|---|---|"]
            for c in cols:
                rows.append("| {} | {} | {} | {} | {} |".format(
                    c.get("label") or c.get("name"), (c.get("meaning") or "").replace("|", "/"),
                    c.get("unit") or "-", str(c.get("example") or "-").replace("|", "/"),
                    {"documentation": "The data source's documentation", "data": "Read from the data itself",
                     "calculated": "Calculated for this project"}.get(c.get("source"), "Not explained by the data source")))
            st.markdown("\n".join(rows))
        codes = d.get("codes", [])
        if codes:
            st.markdown("**Codes and abbreviations**")
            rows = ["| Column | Code | Means | Where this comes from |", "|---|---|---|---|"]
            for c in codes:
                ok = c.get("source") != "not defined" and c.get("meaning")
                rows.append("| {} | {} | {} | {} |".format(
                    c.get("column"), c.get("code"), c.get("meaning") if ok else "⚠️ Not explained by the data source",
                    {"documentation": "The data source's documentation", "data": "Read from the data itself"}.get(c.get("source"), "-")))
            st.markdown("\n".join(rows))
        for note in d.get("notes", []):
            st.caption(f"ℹ️ {note}")
