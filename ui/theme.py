"""P3: one palette, page configuration and Plotly template."""
import plotly.graph_objects as go
import streamlit as st

COLORS = {"primary": "#2563EB", "secondary": "#0F766E", "accent": "#D97706", "text": "#172033"}
PLOTLY_TEMPLATE = go.layout.Template(layout={
    "font": {"family": "Arial, sans-serif", "color": COLORS["text"]},
    "colorway": [COLORS["primary"], COLORS["secondary"], COLORS["accent"]],
    "paper_bgcolor": "white", "plot_bgcolor": "white",
    "xaxis": {"gridcolor": "#E8EDF5"}, "yaxis": {"gridcolor": "#E8EDF5"},
})


def apply_theme(page_title: str = "EV Intelligence") -> None:
    st.set_page_config(page_title=page_title, page_icon="🔋", layout="wide")
