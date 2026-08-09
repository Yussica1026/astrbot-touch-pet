from playwright.sync_api import sync_playwright
from pathlib import Path


with sync_playwright() as playwright:
    edge = next(path for path in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ) if path.is_file())
    browser = playwright.chromium.launch(headless=True, executable_path=str(edge))
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.add_init_script("localStorage.setItem('touchPetPairToken', 'test-token')")
    captured = {}

    def chat_route(route):
        captured.update(route.request.post_data_json)
        route.fulfill(status=200, content_type="application/json", body='{"ok":true,"status":"delivered","cooldown_seconds":30}')

    page.route("**/api/chat", chat_route)
    page.goto((Path(__file__).resolve().parents[1] / "index.html").as_uri(), wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("#chatInput")
    page.locator("#chatInput").fill("测试文字消息")
    page.locator("#chatSend").click()
    page.wait_for_timeout(300)
    assert captured["message"] == "测试文字消息"
    assert len(captured["request_id"]) >= 8
    assert page.locator("#chatInput").is_disabled()
    assert page.locator("#chatSend").is_disabled()
    assert not errors, errors
    browser.close()

print("mobile chat smoke passed")
