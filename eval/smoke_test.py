"""Check all new Streamlit entry points in sample mode, without Neo4j."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core import config


def main():
    assert config.USE_SAMPLE, "Run baseline checks with USE_SAMPLE=true"
    root = Path(__file__).resolve().parents[1]
    entries = [root / "app.py", *sorted((root / "pages").glob("*.py"))]
    assert len(entries) == 4
    for entry in entries:
        app = AppTest.from_file(str(entry), default_timeout=30).run()
        assert not app.exception, f"{entry.name}: {app.exception}"
        if entry.name.startswith("03_"):
            app.text_input[0].set_value("某企业有哪些专利？").run()
            app.button[0].click().run()
            assert not app.exception, app.exception
            assert app.warning, "Unimplemented QA must display its status"
        print("PASS", entry.name)


if __name__ == "__main__":
    main()
