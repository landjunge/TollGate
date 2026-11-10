import asyncio, json, sys, threading, time, uvicorn
from pathlib import Path
from playwright.async_api import async_playwright
from tollgate.server_v1 import app
out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True)
srv=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=48931,log_level="error"))
threading.Thread(target=srv.run,daemon=True).start(); time.sleep(2)
CH=sys.argv[2]
async def main():
    res=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CH)
        for scheme in ["dark","light"]:
            ctx=await b.new_context(color_scheme=scheme)
            pg=await ctx.new_page(); errs=[]
            pg.on("pageerror",lambda e:errs.append(str(e)))
            for w in [1280,390,320]:
                await pg.set_viewport_size({"width":w,"height":900})
                await pg.goto("http://127.0.0.1:48931/dashboard"); 
                await pg.wait_for_selector('[data-app-id="tollgate"][data-state="confirmed"]',timeout=8000)
                n=await pg.locator(".np-appbar-button").count()
                over=await pg.evaluate("document.documentElement.scrollWidth>innerWidth+1")
                ver=await pg.locator('[data-app-id="tollgate"] .np-appbar-version').inner_text()
                await pg.locator('[data-app-id="threaddesk"]').focus()
                await pg.keyboard.press("Enter"); await pg.locator("dialog[open]").wait_for()
                title=await pg.locator("dialog h2").inner_text()
                await pg.keyboard.press("Escape")
                kept=await pg.locator('[data-app-id="threaddesk"]').evaluate("e=>e===document.activeElement")
                await pg.keyboard.press("Tab")
                nxt=await pg.locator('[data-app-id="4allpass"]').evaluate("e=>e===document.activeElement")
                col=await pg.locator(".card").first.evaluate("e=>getComputedStyle(e).borderTopColor")
                await pg.screenshot(path=str(out/f"dashboard-{scheme}-{w}.png"))
                res.append(dict(scheme=scheme,width=w,buttons=n,hscroll=over,version=ver,dialog=title,focus_return=kept,tab_next=nxt,card_border=col,errors=list(errs)))
                imgs=await pg.evaluate("[...document.querySelectorAll('.np-appbar-button img')].every(i=>i.naturalWidth>0)"); assert imgs and n==5 and not over and kept and nxt and title=="ThreadDesk" and col=="rgb(231, 119, 69)",res[-1]
        await b.close()
    (out/"browser-checks.json").write_text(json.dumps({"status":"passed","checks":res},indent=1))
    print("passed",len(res))
asyncio.run(main()); srv.should_exit=True
