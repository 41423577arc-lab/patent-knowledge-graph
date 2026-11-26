"""P3: v0 design tokens, native navigation and shared Plotly theme."""
from pathlib import Path

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import streamlit as st

from ui.assets import asset_uri

COLORS = {"background": "#071b2a", "panel": "#0d293d", "soft": "#10334a",
          "border": "#23536c", "primary": "#00d9ef", "secondary": "#329bf5",
          "accent": "#f3bd6a", "text": "#f0f6fc", "muted": "#a8bdcc"}
PLOTLY_TEMPLATE = go.layout.Template(layout={
    "font": {"family": "Microsoft YaHei, Noto Sans SC, Arial, sans-serif", "color": COLORS["text"], "size": 12},
    "colorway": [COLORS["primary"], COLORS["secondary"], "#63d4b2", COLORS["accent"], "#ae9aff"],
    "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
    "xaxis": {"gridcolor": "#1d4259", "zerolinecolor": "#28536b", "automargin": True},
    "yaxis": {"gridcolor": "#1d4259", "zerolinecolor": "#28536b", "automargin": True},
    "hoverlabel": {"bgcolor": "#10334a", "font_color": COLORS["text"]},
    "margin": {"l": 20, "r": 20, "t": 35, "b": 30},
})
pio.templates["ev_intelligence"]=PLOTLY_TEMPLATE
px.defaults.template="ev_intelligence"


def apply_theme(page_title: str = "EV Intelligence") -> None:
    st.set_page_config(page_title=f"{page_title} · EV Intelligence", page_icon="🔋",
                       layout="wide", initial_sidebar_state="expanded")
    css = (Path(__file__).with_name("styles.css")).read_text(encoding="utf-8")
    for token, name in {"__SIDEBAR_ART__": "sidebar-energy.png", "__SIDEBAR_WAVE__": "decor/wave_sidebar.svg",
                        "__NETWORK__": "decor/network_motif.svg"}.items():
        css = css.replace(token, asset_uri(name))
    st.html(f"<style>{css}</style>")
    st.html(f'''<header class="ev-topbar"><img src="{asset_uri('brand/logo_ev.svg')}" alt="EV 品牌标志">
       <strong>EV Intelligence</strong><span class="ev-topbar-divider"></span>
       <span class="ev-platform-name">新能源汽车产业技术情报知识图谱平台</span>
       <span class="ev-platform-tag">知识图谱 · 产业洞察</span></header>''')
    pages = [("产业技术全景", "pages/01_产业技术全景.py", "overview"),
             ("创新主体与合作网络", "pages/02_创新主体与合作网络.py", "cooperation"),
             ("智能问答与关联路径", "pages/03_智能问答与关联路径.py", "chat")]
    with st.sidebar:
        st.html('<div class="ev-navigation-label">工作空间 <span>WORKSPACE</span></div>')
        for index, (label, path, icon) in enumerate(pages):
            active = page_title == label
            container_key = f"ev_nav_{index}_{'active' if active else 'idle'}"
            with st.container(key=container_key):
                uri = asset_uri(f"icons/svg/{icon}_{'active' if active else 'default'}.svg")
                st.html(f'<style>.st-key-{container_key} [data-testid="stPageLink"] {{background:url("{uri}") no-repeat left center / 18px 18px; padding-left:27px;}}</style>')
                st.page_link(path, label=label)
        st.page_link("app.py", label="返回平台首页", icon=":material/home:")
        st.html('<div class="ev-sidebar-note">以专利连接产业知识<br><span>CONNECTING INNOVATION</span></div>')
