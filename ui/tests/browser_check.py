"""Optional dev-only Playwright checks. Requires playwright + an installed Edge browser."""
import argparse
import json
from pathlib import Path


def main():
    from playwright.sync_api import sync_playwright, expect
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18503")
    parser.add_argument("--output", default="tmp/visual-qa")
    options = parser.parse_args()
    output = Path(options.output)
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for width in [1280, 1440, 1920]:
            page = browser.new_page(viewport={"width": width, "height": 1080}, device_scale_factor=1)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(options.url)
            page.locator('[data-testid="stSidebar"]').get_by_text("智能问答与关联路径", exact=True).click()
            chat = page.get_by_placeholder("输入完整产业技术问题…")
            chat.wait_for(timeout=45000)
            page.get_by_role("button", name="演示：主体 A 的依赖暴露度", exact=True).click()
            expect(chat).to_have_value("演示：主体 A 的依赖暴露度", timeout=15000)
            chat.press("Enter")
            page.get_by_text("【演示假数据】依赖暴露度 60.0%，只供 UI 演示，不代表真实业务。", exact=True).last.wait_for(timeout=45000)
            figure = page.locator(".js-plotly-plot").first
            figure.wait_for()
            geometry = page.evaluate('''() => ({
                documentWidth:document.documentElement.scrollWidth, viewport:innerWidth,
                mainWidth:document.querySelector('[data-testid="stMain"]').clientWidth,
                mainScroll:document.querySelector('[data-testid="stMain"]').scrollWidth,
                brokenImages:[...document.querySelectorAll('img')].filter(e=>e.offsetWidth>0&&(!e.complete||!e.naturalWidth)).length,
                heroHeight:document.querySelector('.ev-hero').getBoundingClientRect().height
            })''')
            assert geometry["documentWidth"] <= width + 1, geometry
            assert geometry["mainScroll"] <= geometry["mainWidth"] + 1, geometry
            assert geometry["brokenImages"] == 0, geometry
            page.screenshot(path=str(output / f"answer-{width}.png"))
            figure.scroll_into_view_if_needed()
            page.screenshot(path=str(output / f"graph-{width}.png"))
            input_box = chat.bounding_box()
            graph_box = figure.bounding_box()
            assert input_box["y"] >= graph_box["y"] + graph_box["height"], "Composer overlays graph"
            points = figure.locator(".scatterlayer .trace").last.locator(".points path")
            # Plotly intentionally receives input through its drag overlay, as a user's mouse does.
            point_box = points.first.bounding_box()
            page.mouse.click(point_box["x"] + point_box["width"] / 2, point_box["y"] + point_box["height"] / 2)
            details = page.locator('.st-key-ev_qa_result details[open]').filter(has_text="实体 / 关系详情")
            details.wait_for(timeout=15000)
            assert details.inner_text().strip(), "Node/edge inspection did not render"
            page.get_by_role("button", name="大图查看", exact=True).click()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(timeout=15000)
            dialog.locator(".js-plotly-plot").wait_for(timeout=15000)
            assert dialog.locator(".js-plotly-plot").count() == 1
            page.screenshot(path=str(output / f"large-{width}.png"))
            dialog.get_by_role("button", name="Close", exact=True).click()
            figure = page.locator(".js-plotly-plot").first
            figure.scroll_into_view_if_needed()
            drag_box = figure.locator(".nsewdrag").bounding_box()
            old_range = figure.evaluate("e => [...e._fullLayout.xaxis.range]")
            page.mouse.move(drag_box["x"] + drag_box["width"] / 2, drag_box["y"] + drag_box["height"] / 2)
            page.mouse.wheel(0, -250)
            page.wait_for_function("before => { const e=document.querySelector('.js-plotly-plot');return e && Math.abs(e._fullLayout.xaxis.range[1]-e._fullLayout.xaxis.range[0]) < before; }", arg=old_range[1]-old_range[0])
            before_pan = figure.evaluate("e => e._fullLayout.xaxis.range[0]")
            page.mouse.down()
            page.mouse.move(drag_box["x"] + drag_box["width"] / 2 + 45, drag_box["y"] + drag_box["height"] / 2, steps=5)
            page.mouse.up()
            page.wait_for_function("before => { const e=document.querySelector('.js-plotly-plot');return e && Math.abs(e._fullLayout.xaxis.range[0]-before)>0.01; }", arg=before_pan)
            page.get_by_role("button", name="新建空会话", exact=True).click()
            page.get_by_text("从一个问题开始探索", exact=True).wait_for(timeout=15000)
            assert not page_errors, page_errors
            checks.append({"width": width, "geometry": geometry, "graph_selection": "pass", "zoom_pan": "pass", "large_view": "pass", "new_session": "pass", "page_errors": page_errors})
            print(f"PASS {width}px: geometry, assets, graph selection, large view, new session", flush=True)
            page.close()
        browser.close()
    (output / "browser-results.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
