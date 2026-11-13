import asyncio, json, sys, threading, time, uvicorn
from pathlib import Path
from playwright.async_api import async_playwright
from tollgate.server_v1 import app

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=48931, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start(); time.sleep(2)
CH = sys.argv[2]

async def dismiss_onboarding(pg):
    if await pg.locator("#obSkip").is_visible():
        await pg.locator("#obSkip").click()
        await pg.locator("#onboard").wait_for(state="hidden")

async def main():
    res = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CH)
        for lang in ["de", "en"]:
            for w in [1360, 940]:
                ctx = await b.new_context(color_scheme="dark")
                pg = await ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                await pg.set_viewport_size({"width": w, "height": 900})
                await pg.goto(f"http://127.0.0.1:48931/dashboard?lang={lang}")
                await pg.wait_for_selector('[data-app-id="tollgate"][data-state="confirmed"]', timeout=8000)
                await dismiss_onboarding(pg)
                html_lang = await pg.evaluate("document.documentElement.lang")
                summary_label = await pg.locator("#headerMore > summary").get_attribute("aria-label")
                brand_alt = await pg.locator(".brand-mark").get_attribute("alt")
                header = await pg.locator("header").evaluate("e => e.getBoundingClientRect().height")
                center = await pg.evaluate("""() => {
                  const r = document.querySelector('.np-appbar-host').getBoundingClientRect();
                  return Math.abs((r.left + r.right) / 2 - innerWidth / 2);
                }""")
                buttons = await pg.locator(".np-appbar-button").count()
                target = await pg.locator(".np-appbar-button").first.evaluate(
                    "e => ({w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height})")
                over = await pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                wordmark = await pg.locator(".brand-mark").evaluate("e => e.naturalWidth > 0")
                card = await pg.locator(".card").first.evaluate("e => getComputedStyle(e).borderTopColor")

                # Keyboard: reach the Plus, open, tab through every secondary tool.
                await pg.keyboard.press("Tab")
                for _ in range(8):
                    if await pg.locator("#headerMore > summary").evaluate(
                        "e => document.activeElement === e"):
                        break
                    await pg.keyboard.press("Tab")
                focused = await pg.locator("#headerMore > summary").evaluate(
                    "e => document.activeElement === e")
                focus_width = await pg.locator("#headerMore > summary").evaluate(
                    "e => getComputedStyle(e).outlineWidth")
                await pg.keyboard.press("Enter")
                opened = await pg.locator("#headerMore").evaluate("e => e.open")
                tools_total = await pg.locator(
                    "#headerMore .more-panel a, #headerMore .more-panel button, "
                    "#headerMore .more-panel input").count()
                lang_hrefs = await pg.locator("#headerMore .more-panel a").evaluate_all(
                    "els => els.map(e => e.getAttribute('href'))")
                # Every previous secondary tool must be reachable by keyboard,
                # starting from the Plus summary in DOM order.
                await pg.locator("#headerMore > summary").focus()
                seen = set()
                for _ in range(tools_total + 2):
                    await pg.keyboard.press("Tab")
                    label = await pg.evaluate("""() => {
                      const e = document.activeElement;
                      return e.closest('#headerMore .more-panel') ? (e.textContent || e.id || e.tagName) : null;
                    }""")
                    if label is not None:
                        seen.add(label)
                    if len(seen) == tools_total:
                        break
                tools_reachable = len(seen) == tools_total
                # The key field is operable without touching any provider.
                await pg.locator("#apiKey").fill("probe-key")
                key_operable = await pg.locator("#apiKey").input_value() == "probe-key"
                await pg.locator("#apiKey").fill("desk")
                # Setup is one of the previous secondary tools and must still open.
                await pg.locator("#btnSetup").focus()
                await pg.keyboard.press("Enter")
                setup_open = await pg.locator("#onboard").is_visible()
                if setup_open:
                    await dismiss_onboarding(pg)
                # Escape closes the disclosure and returns focus to the Plus.
                if not await pg.locator("#headerMore").evaluate("e => e.open"):
                    await pg.locator("#headerMore > summary").focus()
                    await pg.keyboard.press("Enter")
                await pg.locator("#headerMore > summary").focus()
                await pg.keyboard.press("Escape")
                closed = await pg.locator("#headerMore").evaluate("e => !e.open")
                returned = await pg.locator("#headerMore > summary").evaluate(
                    "e => document.activeElement === e")

                await pg.screenshot(path=str(out / f"dashboard-{lang}-{w}.png"))
                row = dict(lang=lang, html_lang=html_lang, width=w, header=round(header, 2),
                           center=round(center, 2), buttons=buttons, target=target,
                           hscroll=over, wordmark=wordmark, card_border=card,
                           focus=focused, focus_width=focus_width, disclosure_open=opened,
                           tools_total=tools_total, tools_reachable=tools_reachable,
                           lang_hrefs=lang_hrefs, key_operable=key_operable,
                           disclosure_closed=closed, focus_returned=returned,
                           setup_opens=setup_open, errors=list(errs))
                res.append(row)
                assert abs(header - 64) <= 0.6, row
                assert center <= 1, row
                assert buttons == 5 and target["w"] >= 43.5 and target["h"] >= 43.5, row
                assert not over and wordmark, row
                assert card == "rgb(53, 57, 64)", row
                assert focused and focus_width == "2px", row
                assert opened and closed and returned, row
                assert tools_total == 6 and tools_reachable, row
                assert key_operable and setup_open, row
                assert html_lang == lang, row
                assert summary_label == ("Weitere Werkzeuge" if lang == "de" else "More tools"), row
                assert brand_alt == "TOLLGATE", row
                assert any("lang=de" in (href or "") for href in lang_hrefs[0:2]), row
                assert any("lang=en" in (href or "") for href in lang_hrefs[0:2]), row
                assert all("mode=" in (href or "") for href in lang_hrefs[2:4]), row
                await ctx.close()

            # Appbar buttons keep the shared 2-px keyboard focus ring.
            ctx = await b.new_context(color_scheme="dark")
            pg = await ctx.new_page()
            await pg.set_viewport_size({"width": 1360, "height": 900})
            await pg.goto(f"http://127.0.0.1:48931/dashboard?lang={lang}")
            await pg.wait_for_selector('[data-app-id="tollgate"][data-state="confirmed"]', timeout=8000)
            await pg.keyboard.press("Tab")
            await pg.locator('.np-appbar-button').first.focus()
            focus_ok = await pg.locator('.np-appbar-button').first.evaluate(
                "e => e === document.activeElement && getComputedStyle(e).outlineWidth === '2px'")
            assert focus_ok, lang
            await ctx.close()
        await b.close()
    (out / "browser-checks.json").write_text(
        json.dumps({"status": "passed", "checks": res}, indent=1))
    print("passed", len(res))

asyncio.run(main())
srv.should_exit = True
