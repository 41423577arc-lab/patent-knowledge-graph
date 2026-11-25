"""Check all new Streamlit entry points in sample mode, without Neo4j."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core import config


def main():
    assert config.USE_SAMPLE, "Run baseline checks with USE_SAMPLE=true"
    root = Path(__file__).resolve().parents[1]
    entries = [root / "app.py", *sorted((root / "pages").glob("*.py"))]
    assert len(entries) == 4
    old_backend = config.QA_BACKEND
    config.QA_BACKEND = "mock"
    try:
        for entry in entries:
            app = AppTest.from_file(str(entry), default_timeout=30).run()
            assert not app.exception, f"{entry.name}: {app.exception}"
            assert not app.error, f"{entry.name}: {app.error}"
            if entry.name.startswith("03_"):
                for question in ["演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]:
                    app.text_input[0].set_value(question).run()
                    app.button[0].click().run()
                    assert not app.exception and not app.error, (app.exception, app.error)
                    assert any("【演示假数据】" in item.value for item in app.markdown)
                app.text_input[0].set_value("不支持的问题").run()
                app.button[0].click().run()
                assert not app.exception and app.error
                config.QA_BACKEND = "real"
                app.button[0].click().run()
                assert not app.exception and app.error
                assert "待 P2 实现" in app.error[0].value
            print("PASS", entry.name)
    finally:
        config.QA_BACKEND = old_backend


if __name__ == "__main__":
    main()
