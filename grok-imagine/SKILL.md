---
name: grok-imagine
description: Generate images and videos with Grok Imagine using the user's own grok.com subscription, by driving a dedicated logged-in Chrome over CDP through a local daemon. Use when the user asks to generate Grok Imagine images/videos, image-to-video with Grok, or wants a local API over their Grok subscription quota. Prefer the official xAI API instead when the user has an xAI API key and wants pay-per-use.
---

# Grok Imagine (subscription bridge)

`scripts/grok_imagine.py` runs a local daemon that starts a dedicated Chrome profile with a debugging port. That Chrome is isolated from the user's everyday browser, and connecting to it raises no permission prompts. The daemon holds one CDP connection and one tab, and runs jobs one at a time. The page makes its own requests and does its own request signing; never extract, replay or forge `x-statsig-id` or other anti-bot tokens. This is unofficial automation of grok.com. It may break when the UI changes and may conflict with xAI's terms; say so when sharing it.

Requirements: `uv` and Google Chrome (override the binary with `GROK_CHROME`). Run every command as `uv run <skill-dir>/scripts/grok_imagine.py ...`.

## First run: login

```bash
uv run scripts/grok_imagine.py login     # starts daemon + dedicated Chrome, waits up to 600s
```

The user logs in to grok.com in the dedicated Chrome window (profile `~/.grok-bridge/chrome-profile`). Never type credentials for them. Waiting only polls cookies and never navigates the tab. The login persists across restarts. The window can be minimized; if it is closed, the next command reopens it.

Do not attach to the user's main Chrome through `chrome://inspect` remote debugging. Chrome asks the user to allow every new connection. If the user explicitly wants that anyway, set `GROK_CDP_URL`, and reuse the daemon's single connection instead of opening new ones.

## Generate

```bash
uv run scripts/grok_imagine.py status                 # exit 2 = not logged in
uv run scripts/grok_imagine.py image "prompt" [--aspect-ratio 2:3|3:2|1:1|9:16|16:9]
uv run scripts/grok_imagine.py video "prompt" [--duration 6|10|15] [--resolution 480p|720p] [--aspect-ratio ...|Auto] [--image a.jpg [--image b.jpg ...]]
uv run scripts/grok_imagine.py --out ./outputs image "prompt"    # save into a task directory
uv run scripts/grok_imagine.py stop                   # stop the daemon, e.g. after editing the script
```

Each command prints JSON with local file paths (default `~/.grok-bridge/outputs/<date>/`).

- `image` returns the batch Grok generates: 8 images in Speed mode, 4 in Quality mode, with the mode taken from the page's current setting. Items with `moderated: true` have no file.
- The page would request extra batches on its own as results render. The daemon drops them and reports `suppressed_batches`; `extra_batches_sent` must stay 0.
- `--image` makes `video` image-to-video; repeat it to attach several reference images, as the page's prompt bar allows. Refer to them in the prompt by order or description ("the man from the first image"). The result's `input` must then not read `["textToVideo"]`; check what it does read.
- The dedicated Chrome runs with `--use-mock-keychain`: launched outside LaunchServices, macOS Chrome may otherwise fail to get its Keychain key and keep cookies in memory only, so the login would be lost on every restart.

Every generation spends the user's subscription quota:

- Only generate what the user asked for, and confirm before large batches.
- Never auto-retry `image` or `video` after a timeout or unclear error, because the job may already have run. Run `status`, then ask.
- Do not run commands in parallel. The daemon queues them anyway.
- Verify outputs before reporting: the files exist, and for video `ffprobe` shows the expected duration and resolution.

## HTTP API

The daemon listens on `127.0.0.1:8765`, with its log in `~/.grok-bridge/daemon.log`:

- `GET /health`
- `POST /v1/images {"prompt","aspect_ratio","out"}`
- `POST /v1/videos {"prompt","duration","resolution","aspect_ratio","image_paths":[...],"out"}`

Paths must be absolute.

## When it breaks

UI selectors live in the script and match English or Chinese labels:

- the mode radios `Image/图片` and `Video/视频`
- `480p`/`720p` and `6s`/`10s`/`15s`
- the `Aspect Ratio` menu, which opens only by keyboard in video mode
- the prompt bar's own file input; the page has others, such as the Text Edit card

If a step times out, look at the bridge tab in the dedicated Chrome and update the selector.

Results come from the `wss://grok.com/ws/imagine/listen` frames for images, and from the streamed `POST /rest/app-chat/conversations/new` response for video. If those change, re-inspect the page's network traffic. After editing the script, run `stop` so the next command starts a fresh daemon.
