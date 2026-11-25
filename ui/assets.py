"""Original v0 assets, embedded locally; no external requests or generated replacements."""
import base64
from functools import lru_cache
from html import escape
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=96)
def asset_uri(name: str) -> str:
    path = (ASSET_DIR / name).resolve()
    if not path.is_relative_to(ASSET_DIR.resolve()):
        raise ValueError("Asset must stay inside ui/assets")
    mime = "image/svg+xml" if path.suffix == ".svg" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def icon_html(name: str, *, active: bool = True, size: int = 18) -> str:
    state = "active" if active else "default"
    return f'<img class="ev-icon" src="{asset_uri(f"icons/svg/{name}_{state}.svg")}" width="{size}" height="{size}" alt="" aria-hidden="true">'


def heading_html(title: str, subtitle: str = "", number: str = "03") -> str:
    return f'''<section class="ev-hero" aria-label="{escape(title, quote=True)}">
      <img class="ev-hero-wave" src="{asset_uri('decor/wave_header.svg')}" alt="" aria-hidden="true">
      <img class="ev-hero-art" src="{asset_uri('ev-banner.png')}" alt="" aria-hidden="true">
      <div class="ev-hero-copy"><div class="ev-hero-title"><span>{escape(number)}</span><h1>{escape(title)}</h1></div>
      <p>{escape(subtitle)}</p></div></section>'''
