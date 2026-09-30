# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.63.0", "aiohttp>=3.9"]
# ///
"""Drive Grok Imagine (grok.com) in a dedicated, logged-in Chrome over CDP.

A local daemon starts a separate Chrome profile with a debugging port (no permission
prompts, isolated from the user's everyday browser), holds one CDP connection and one
tab, and runs jobs one at a time. The page makes its own requests (including its own
anti-bot signing); the daemon only operates the UI and reads what the page receives.

  login    wait until the user has logged in to grok.com in the dedicated Chrome
  status   login state and quota (starts the daemon if needed)
  image    generate images from a prompt
  video    generate a video (text-to-video, or image-to-video with --image)
  serve    run the daemon in the foreground (127.0.0.1 only)
  stop     stop the daemon

Environment overrides: GROK_BRIDGE_HOME (default ~/.grok-bridge), GROK_BRIDGE_PORT (daemon,
default 8765), GROK_CDP_PORT (dedicated Chrome, default 9333), GROK_CHROME (Chrome binary),
GROK_CDP_URL (attach to some other Chrome instead of launching one).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOME = Path(os.environ.get("GROK_BRIDGE_HOME", Path.home() / ".grok-bridge"))
OUTPUT_DIR = HOME / "outputs"
PROFILE_DIR = HOME / "chrome-profile"
TAB_FILE = HOME / "tab.json"
PID_FILE = HOME / "daemon.pid"
LOG_FILE = HOME / "daemon.log"
PORT = int(os.environ.get("GROK_BRIDGE_PORT", "8765"))
CDP_PORT = int(os.environ.get("GROK_CDP_PORT", "9333"))
IMAGINE_URL = "https://grok.com/imagine"
ASSETS_BASE = "https://assets.grok.com/"

log = logging.getLogger("grok-imagine")


class BridgeError(Exception):
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


def chrome_binary() -> str:
    if os.environ.get("GROK_CHROME"):
        return os.environ["GROK_CHROME"]
    if platform.system() == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if found := shutil.which(name):
            return found
    raise BridgeError("Chrome not found; set GROK_CHROME to the Chrome binary")


def cdp_get(path: str, method: str = "GET"):
    with urlopen(Request(f"http://127.0.0.1:{CDP_PORT}{path}", method=method), timeout=2) as r:
        return json.loads(r.read())


def ensure_chrome() -> None:
    """Start the dedicated Chrome if needed, and make sure it has a window to attach to."""
    try:
        cdp_get("/json/version")
    except OSError:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        # Launched outside LaunchServices, macOS Chrome may not get its Keychain key and then
        # keeps cookies in memory only, so the login is lost on every restart. The mock
        # keychain uses a fixed key and lets cookies persist in this dedicated profile.
        subprocess.Popen(
            [chrome_binary(), f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={PROFILE_DIR}",
             "--no-first-run", "--no-default-browser-check", "--use-mock-keychain", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        for _ in range(60):
            time.sleep(0.25)
            try:
                cdp_get("/json/version")
                break
            except OSError:
                continue
        else:
            raise BridgeError(f"dedicated Chrome did not open debugging port {CDP_PORT}")
    # On macOS Chrome keeps running after its last window closes; CDP attach then fails.
    if not any(t["type"] == "page" for t in cdp_get("/json/list")):
        cdp_get("/json/new?about:blank", method="PUT")


# ---------------------------------------------------------------- daemon side

# The results grid asks for more images on its own (`input_scroll`) as soon as the first
# batch renders, silently spending quota. Drop those frames; count them for the report.
SUPPRESS_SCROLL_JS = """() => {
  if (window.__grokBridgePatched) return;
  window.__grokBridgePatched = true;
  window.__grokBridgeSuppressed = 0;
  const send = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    if (typeof data === 'string' && this.url.includes('/ws/imagine/') && data.includes('"input_scroll"')) {
      window.__grokBridgeSuppressed++;
      return;
    }
    return send.call(this, data);
  };
}"""

# Index of the file input that belongs to the prompt bar. The page has others (e.g. the
# "Text Edit" card below the bar), so walk up from the textbox and stay within the bar.
PROMPT_BAR_INPUT_JS = """() => {
  let el = document.querySelector('[contenteditable=true], textarea');
  while (el && !el.querySelector('input[type=file]')) el = el.parentElement;
  if (!el || el.getBoundingClientRect().height > 400) return -1;
  return [...document.querySelectorAll('input[type=file]')].indexOf(el.querySelector('input[type=file]'));
}"""

PROMPT_BAR_IMAGE_COUNT_JS = """() => {
  let el = document.querySelector('[contenteditable=true], textarea');
  while (el && !el.querySelector('input[type=file]')) el = el.parentElement;
  return el ? el.querySelectorAll('img').length : 0;
}"""


def radio(page, *names: str):
    return page.get_by_role("radio", name=re.compile("^(" + "|".join(map(re.escape, names)) + ")$"))


class Bridge:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.pw = None
        self.browser = None
        self.page = None
        self._ws_sink = None  # collector for the current job's WebSocket frames

    async def _connect(self):
        from playwright.async_api import async_playwright

        if self.browser and self.browser.is_connected():
            return
        self.pw = self.pw or await async_playwright().start()
        self.page = None
        if os.environ.get("GROK_CDP_URL"):
            endpoint = os.environ["GROK_CDP_URL"]
        else:
            await asyncio.to_thread(ensure_chrome)
            endpoint = f"http://127.0.0.1:{CDP_PORT}"
        self.browser = await self.pw.chromium.connect_over_cdp(endpoint, timeout=60_000)

    async def _target_id(self, page) -> str:
        cdp = await page.context.new_cdp_session(page)
        try:
            return (await cdp.send("Target.getTargetInfo"))["targetInfo"]["targetId"]
        finally:
            await cdp.detach()

    async def _page(self):
        """The bridge's own tab: reused across jobs and daemon restarts, never closed."""
        await self._connect()
        if self.page and not self.page.is_closed():
            return self.page
        saved = json.loads(TAB_FILE.read_text()).get("target_id") if TAB_FILE.exists() else None
        page = None
        if saved:
            for ctx in self.browser.contexts:
                for p in ctx.pages:
                    if await self._target_id(p) == saved:
                        page = p
        if page is None:
            page = await self.browser.contexts[0].new_page()
            HOME.mkdir(parents=True, exist_ok=True)
            TAB_FILE.write_text(json.dumps({"target_id": await self._target_id(page)}))
        page.on("websocket", self._on_ws)
        self.page = page
        return page

    def _on_ws(self, ws):
        if "/ws/imagine/" not in ws.url:
            return
        ws.on("framesent", lambda p: self._ws_sink and self._ws_sink("sent", p))
        ws.on("framereceived", lambda p: self._ws_sink and self._ws_sink("recv", p))

    async def _open_imagine(self):
        page = await self._page()
        await page.goto(IMAGINE_URL, wait_until="domcontentloaded")
        await page.get_by_role("textbox").first.wait_for(timeout=30_000)
        await page.evaluate(SUPPRESS_SCROLL_JS)
        return page

    async def _reset(self, page):
        # Reloading closes the job's WebSocket and leaves the tab on a usable page.
        try:
            await page.goto(IMAGINE_URL, wait_until="domcontentloaded")
        except Exception:
            log.warning("reset navigation failed", exc_info=True)

    async def status(self) -> dict:
        async with self.lock:
            page = await self._page()
            if page.url in ("", "about:blank"):
                await page.goto(IMAGINE_URL, wait_until="domcontentloaded")
            # Uses the browser's cookies without touching the tab, so a login in progress is safe.
            req = page.context.request
            user = await req.get("https://grok.com/rest/auth/get-user")
            quota = await req.post("https://grok.com/rest/media/imagine/quota_info", data="{}",
                                   headers={"content-type": "application/json"})
            return {"logged_in": user.status == 200, "quota": await quota.json() if quota.ok else None}

    async def _set_aspect_ratio(self, page, ratio: str | None):
        if not ratio:
            return
        trigger = page.get_by_role("button", name=re.compile("Aspect Ratio|宽高比|比例")).first
        # In video mode a mouse click does not open this menu; keyboard activation works in both modes.
        await trigger.focus()
        await page.keyboard.press("Enter")
        await page.get_by_role("menuitemradio", name=re.compile(rf"^{re.escape(ratio)}(\s|$)", re.I)).first.click()
        label = (await trigger.inner_text()).strip()
        if label != ratio and ratio.lower() != "auto":
            raise BridgeError(f"aspect ratio not applied: wanted {ratio}, button shows {label!r}")

    async def _submit(self, page, prompt: str):
        box = page.get_by_role("textbox").first
        await box.click()
        await box.fill(prompt)
        await page.keyboard.press("Enter")

    @staticmethod
    def _dir(out: str | None, *parts: str) -> Path:
        d = (Path(out) if out else OUTPUT_DIR / time.strftime("%Y%m%d")).joinpath(*parts)
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def image(self, prompt: str, aspect_ratio: str | None = None, out: str | None = None,
                    timeout: float = 180) -> dict:
        async with self.lock:
            page = await self._open_imagine()
            await radio(page, "Image", "图片").click()
            await self._set_aspect_ratio(page, aspect_ratio)

            state = {"rid": None, "jobs": {}, "images": {}, "leaked": 0}
            done = asyncio.Event()

            def sink(kind, payload):
                if isinstance(payload, bytes):
                    return
                try:
                    msg = json.loads(payload)
                except ValueError:
                    return
                if kind == "sent":
                    for c in msg.get("item", {}).get("content", []):
                        if c.get("type") == "input_text" and state["rid"] is None:
                            state["rid"] = c.get("requestId")
                        elif c.get("type") == "input_scroll":
                            state["leaked"] += 1  # should stay 0 while SUPPRESS_SCROLL_JS works
                    return
                if msg.get("type") == "json" and msg.get("request_id") == state["rid"]:
                    state["jobs"][msg["job_id"]] = msg
                elif msg.get("type") == "image" and msg.get("blob"):
                    # Later frames for the same job replace earlier (preview) ones.
                    state["images"][msg.get("job_id") or msg.get("image_id") or msg.get("id")] = msg
                jobs = state["jobs"].values()
                if jobs and all(j.get("current_status") == "completed" or j.get("moderated") for j in jobs):
                    done.set()

            self._ws_sink = sink
            try:
                await self._submit(page, prompt)
                try:
                    await asyncio.wait_for(done.wait(), timeout)
                except TimeoutError:
                    if not state["jobs"]:
                        raise BridgeError("timed out with no generation jobs (logged out or quota exhausted?)", 504)
                await asyncio.sleep(1.0)  # the final image frame may trail the completed status
                suppressed = await page.evaluate("window.__grokBridgeSuppressed || 0")
            finally:
                self._ws_sink = None
                await self._reset(page)

            d = self._dir(out, state["rid"] or uuid.uuid4().hex)
            results = []
            for i, (job_id, job) in enumerate(sorted(state["jobs"].items(), key=lambda kv: kv[1].get("order") or 0)):
                item = {"job_id": job_id, "status": job.get("current_status"), "moderated": job.get("moderated"),
                        "width": job.get("width"), "height": job.get("height")}
                img = state["images"].get(job_id)
                if img and not job.get("moderated"):
                    path = d / f"{i:02d}_{job_id}.jpg"
                    path.write_bytes(base64.b64decode(img["blob"]))
                    item["path"] = str(path)
                results.append(item)
            return {"request_id": state["rid"], "prompt": prompt, "suppressed_batches": suppressed,
                    "extra_batches_sent": state["leaked"], "images": results}

    async def video(self, prompt: str, aspect_ratio: str | None = None, duration: int | None = None,
                    resolution: str | None = None, image_paths: list[str] | None = None, out: str | None = None,
                    timeout: float = 900) -> dict:
        async with self.lock:
            page = await self._open_imagine()
            try:
                await radio(page, "Video", "视频").click()
                if image_paths:
                    k = await page.evaluate(PROMPT_BAR_INPUT_JS)
                    if k < 0:
                        raise BridgeError("prompt-bar image input not found (UI changed?)")
                    # The prompt bar's input takes several files at once; each becomes a reference image.
                    await page.locator("input[type=file]").nth(k).set_input_files(image_paths)
                    try:
                        await page.wait_for_function(f"() => ({PROMPT_BAR_IMAGE_COUNT_JS})() >= {len(image_paths)}",
                                                     timeout=30_000)
                    except Exception:
                        n = await page.evaluate(PROMPT_BAR_IMAGE_COUNT_JS)
                        raise BridgeError(f"only {n} of {len(image_paths)} images attached to the prompt bar; "
                                          "nothing was submitted") from None
                    await page.wait_for_timeout(2000)  # let the uploads finish before submitting
                if resolution:
                    await radio(page, resolution).click()
                if duration:
                    await radio(page, f"{duration}s").click()
                await self._set_aspect_ratio(page, aspect_ratio)

                async with page.expect_response(
                    lambda r: "/rest/app-chat/conversations/new" in r.url and r.request.method == "POST",
                    timeout=60_000,
                ) as resp_info:
                    await self._submit(page, prompt)
                resp = await resp_info.value
                media_input = list((json.loads(resp.request.post_data or "{}").get("mediaGenInput") or {}).keys())
                if resp.status != 200:
                    raise BridgeError(f"generation request failed HTTP {resp.status}: {(await resp.text())[:300]}", 502)
                body = await asyncio.wait_for(resp.text(), timeout)
            finally:
                await self._reset(page)

            final, conversation_id = None, None
            for line in body.splitlines():
                try:
                    res = json.loads(line).get("result", {})
                except ValueError:
                    continue
                conversation_id = conversation_id or res.get("conversation", {}).get("conversationId")
                if v := res.get("response", {}).get("streamingVideoGenerationResponse"):
                    final = v
            if not final:
                raise BridgeError("no video result in response: " + body[-300:], 502)
            if final.get("moderated"):
                return {"video_id": final.get("videoId"), "moderated": True, "prompt": prompt}
            if not final.get("videoUrl"):
                raise BridgeError(f"video not finished, progress {final.get('progress')}", 502)

            data = await page.context.request.get(ASSETS_BASE + final["videoUrl"])
            if not data.ok:
                raise BridgeError(f"video download failed HTTP {data.status}", 502)
            path = self._dir(out) / f"{final['videoId']}.mp4"
            path.write_bytes(await data.body())
            return {"video_id": final["videoId"], "conversation_id": conversation_id, "path": str(path),
                    "input": media_input,
                    "resolution": final.get("resolutionName"), "prompt": prompt, "moderated": False}


async def serve(port: int):
    from aiohttp import web

    bridge = Bridge()

    async def run(fn):
        try:
            return web.json_response(await fn(), dumps=lambda o: json.dumps(o, ensure_ascii=False))
        except BridgeError as e:
            return web.json_response({"error": str(e)}, status=e.status)
        except Exception as e:  # UI changes etc.; surface as-is for debugging
            log.exception("request failed")
            return web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500)

    async def ping(request):
        return web.json_response({"ok": True, "pid": os.getpid()})

    async def health(request):
        return await run(bridge.status)

    async def images(request):
        b = await request.json()
        return await run(lambda: bridge.image(b["prompt"], b.get("aspect_ratio"), b.get("out")))

    async def videos(request):
        b = await request.json()
        return await run(lambda: bridge.video(b["prompt"], b.get("aspect_ratio"), b.get("duration"),
                                              b.get("resolution"), b.get("image_paths"), b.get("out")))

    app = web.Application()
    app.router.add_get("/ping", ping)
    app.router.add_get("/health", health)
    app.router.add_post("/v1/images", images)
    app.router.add_post("/v1/videos", videos)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    HOME.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    log.info("listening on http://127.0.0.1:%d (outputs: %s)", port, OUTPUT_DIR)
    await asyncio.Event().wait()


# ---------------------------------------------------------------- client side

def call(method: str, path: str, body: dict | None = None, timeout: float = 30):
    req = Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers={"content-type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def ensure_daemon():
    try:
        call("GET", "/ping", timeout=2)
        return
    except (URLError, OSError):
        pass
    HOME.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as logf:
        subprocess.Popen([sys.executable, __file__, "serve", "--port", str(PORT)],
                         stdout=logf, stderr=logf, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        time.sleep(0.5)
        try:
            call("GET", "/ping", timeout=2)
            return
        except (URLError, OSError):
            continue
    raise BridgeError(f"daemon did not start; see {LOG_FILE}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="output directory (default ~/.grok-bridge/outputs/<date>)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("login")
    p.add_argument("--wait", type=float, default=600, help="seconds to wait for the user to log in")
    sub.add_parser("status")
    p = sub.add_parser("image")
    p.add_argument("prompt")
    p.add_argument("--aspect-ratio")
    p = sub.add_parser("video")
    p.add_argument("prompt")
    p.add_argument("--aspect-ratio")
    p.add_argument("--duration", type=int, choices=[6, 10, 15])
    p.add_argument("--resolution", choices=["480p", "720p"])
    p.add_argument("--image", action="append", help="local reference image; repeat for several")
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=PORT)
    sub.add_parser("stop")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        asyncio.run(serve(args.port))
        return 0
    if args.cmd == "stop":
        if PID_FILE.exists():
            try:
                os.kill(int(PID_FILE.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass
            PID_FILE.unlink()
        return 0

    try:
        ensure_daemon()
        out = str(Path(args.out).resolve()) if args.out else None
        if args.cmd in ("status", "login"):
            status, result = call("GET", "/health", timeout=120)
            if args.cmd == "login" and status == 200 and not result.get("logged_in"):
                print(f"Log in to grok.com in the dedicated Chrome window (profile {PROFILE_DIR}); "
                      f"waiting up to {int(args.wait)}s...", file=sys.stderr)
                deadline = time.monotonic() + args.wait
                while status == 200 and not result.get("logged_in") and time.monotonic() < deadline:
                    time.sleep(5)
                    status, result = call("GET", "/health", timeout=120)
        elif args.cmd == "image":
            status, result = call("POST", "/v1/images", {"prompt": args.prompt, "aspect_ratio": args.aspect_ratio,
                                                         "out": out}, timeout=600)
        else:
            images = [str(Path(i).resolve()) for i in args.image or []]
            status, result = call("POST", "/v1/videos", {
                "prompt": args.prompt, "aspect_ratio": args.aspect_ratio, "duration": args.duration,
                "resolution": args.resolution, "image_paths": images, "out": out}, timeout=1200)
    except BridgeError as e:
        status, result = e.status, {"error": str(e)}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if status != 200:
        return 1
    return 2 if result.get("logged_in") is False else 0


if __name__ == "__main__":
    sys.exit(main())
