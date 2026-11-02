# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.64.1"]
# ///
"""Film the widgets and take the stills of the talk from the running Studio view, for build_pptx.py.

Start the view, then run this from the repository's root:

    uvx --with "marimo-studio[deno]==0.4.1" marimo run presentation/presentation_notebook.py --sandbox --port 2800 --headless --no-token
    uv run presentation/record_media.py

It moves the mouse in small steps and takes one screenshot per step, so the videos are sharp and smooth however
slowly the browser renders. Pass names to redo only those: `uv run presentation/record_media.py simulation stills`.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:2800/"
OUTPUT = Path(__file__).parent / "output"
SLIDES = json.loads((Path(__file__).parent / "studio/presentation_notebook/slides/src/slides.json").read_text(encoding="utf-8"))
FPS = 15
# Text the PowerPoint draws itself on top of a video; invisible, so that the slide's layout stays as it is
HIDE_TEXT = ".overlay, .simulation h2, .simulation .points { opacity: 0 !important; }"
POINTER = """
  const pointer = document.createElement('div');
  pointer.id = 'film-pointer';
  pointer.style.cssText = 'position:fixed;z-index:99999;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;'
    + 'background:rgba(214,39,40,.45);border:3px solid #d62728;pointer-events:none;left:-99px;top:-99px';
  document.body.append(pointer);
"""


def slide_number(slide_id):
    return next(i for i, slide in enumerate(SLIDES) if slide["id"] == slide_id)


class Film:
    """Frames of the page, encoded to an MP4, with one of them as the poster"""

    def __init__(self, page, frame, name):
        self.page, self.frame, self.name = page, frame, name
        self.folder = OUTPUT / "frames" / name
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True)
        self.count = 0
        self.poster_at = 0

    def shot(self, hold=1):
        """Take a frame, and show it for hold frames"""
        first = self.folder / f"{self.count:05}.png"
        self.page.screenshot(path=first)
        for i in range(1, hold):
            shutil.copy(first, self.folder / f"{self.count + i:05}.png")
        self.count += hold

    def pointer(self, x, y):
        self.frame.evaluate(f"(p => {{ p.style.left='{x}px'; p.style.top='{y}px'; }})(document.getElementById('film-pointer'))")

    def glide(self, start, end, steps, settle=0.05):
        """Move the pressed or free mouse from start to end, a frame per step"""
        for k in range(1, steps + 1):
            x = start[0] + (end[0] - start[0]) * k / steps
            y = start[1] + (end[1] - start[1]) * k / steps
            self.page.mouse.move(x, y)
            self.pointer(x, y)
            time.sleep(settle)
            self.shot()

    def poster(self):
        """The frame taken now is the poster: what shows until the video plays, and if it can't"""
        self.poster_at = self.count - 1

    def encode(self):
        videos = OUTPUT / "videos"
        videos.mkdir(exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(self.folder / "%05d.png"),
             "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
             str(videos / f"{self.name}.mp4")],
            check=True,
        )
        shutil.copy(self.folder / f"{self.poster_at:05}.png", videos / f"{self.name}.png")
        shutil.rmtree(self.folder)
        print(self.name, f"{self.count / FPS:.1f} s, {(videos / f'{self.name}.mp4').stat().st_size / 1e6:.1f} MB", flush=True)


def go_to(frame, slide_id, wait=2):
    frame.evaluate(f"location.hash='#/{slide_number(slide_id)}'")
    time.sleep(wait)


def film_data(page, frame):
    """GeoTOP's voxels among the 3D BAG: in closer, and around to the side where the layers show"""
    go_to(frame, "data", wait=30)
    film = Film(page, frame, "data")
    film.shot(hold=FPS)
    middle = (960, 540)
    page.mouse.move(*middle)
    film.pointer(*middle)
    for _ in range(40):
        page.mouse.wheel(0, -60)
        time.sleep(0.15)
        film.shot()
    page.mouse.down()
    film.glide(middle, (1500, 380), 110, settle=0.15)
    page.mouse.up()
    film.poster()
    film.shot(hold=FPS)
    film.encode()


def film_simulation(page, frame):
    """The sections moved through the median qc, then each realization in turn"""
    go_to(frame, "simulation", wait=8)
    film = Film(page, frame, "simulation")
    canvas = frame.locator("marimo-output[value='section_view'] canvas").first
    box = canvas.bounding_box()
    width, height = canvas.evaluate("c => [c.clientWidth, c.clientHeight]")
    # The widget's panels in its own px (see place() in cross_sections.js). It takes the pointer's distance
    # from the canvas's corner for its own px, and the slide's zoom draws those larger: the film's pointer follows
    # what is drawn
    zoom = box["width"] / width
    plan = {"x": 64, "y": 200, "w": width - 264, "h": height - 240}

    def at(x, y):
        return box["x"] + x * zoom, box["y"] + y * zoom

    def drag(start, end, steps):
        page.mouse.move(box["x"] + start[0], box["y"] + start[1])
        film.pointer(*at(*start))
        page.mouse.down()
        for k in range(1, steps + 1):
            x = start[0] + (end[0] - start[0]) * k / steps
            y = start[1] + (end[1] - start[1]) * k / steps
            page.mouse.move(box["x"] + x, box["y"] + y)
            film.pointer(*at(x, y))
            time.sleep(0.05)
            film.shot()
        page.mouse.up()

    film.shot(hold=FPS)
    # In the plan: from among the CPTs to the east, then to the south
    start = (plan["x"] + plan["w"] * 0.3, plan["y"] + plan["h"] * 0.7)
    middle = (plan["x"] + plan["w"] * 0.8, plan["y"] + plan["h"] * 0.45)
    end = (plan["x"] + plan["w"] * 0.55, plan["y"] + plan["h"] * 0.8)
    drag(start, middle, 120)
    drag(middle, end, 80)
    # In the west–east section: the plan's level down into the Pleistocene sand
    drag((plan["x"] + plan["w"] * 0.5, 40), (plan["x"] + plan["w"] * 0.5, 150), 60)
    film.poster()
    film.shot(hold=FPS)
    # Each realization in turn, on the same color scale
    frame.locator("marimo-output[value='realization'] [role='slider']").first.focus()
    for _ in range(10):
        page.keyboard.press("ArrowRight")
        time.sleep(4)
        film.shot(hold=2 * FPS)
    film.encode()


def take_stills(browser_context):
    """Each slide's visual at twice the slide's resolution"""
    stills = OUTPUT / "stills"
    stills.mkdir(exist_ok=True)
    page = browser_context.new_page()
    page.goto(URL, timeout=120000)
    frame = studio_frame(page)
    frame.locator("marimo-output details").evaluate_all("menus => menus.forEach(menu => { menu.style.display = 'none'; })")
    for slide_id in ("pipeline", "domains", "uncertainty", "close-geology", "close-accessible", "close-open", "close-qr"):
        go_to(frame, slide_id, wait=4)
        frame.locator(f"[data-visual='{slide_id}']").screenshot(path=stills / f"{slide_id}.png")
        print("still", slide_id, flush=True)
    page.close()


def studio_frame(page):
    """The frame of the view, once every result on its slides is there"""
    started = time.time()
    while time.time() - started < 600:
        frame = next((f for f in page.frames if "_marimo-studio" in f.url), None)
        if frame:
            states = frame.evaluate("[...document.querySelectorAll('marimo-output')].map(e => e.dataset.state)")
            if states and all(state in ("ready", "error") for state in states):
                assert "error" not in states, states
                return frame
        time.sleep(5)
    raise TimeoutError("The view's results did not arrive")


def main(names):
    OUTPUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        chrome = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win*\chrome.exe"))[0]
        browser = playwright.chromium.launch(
            executable_path=chrome, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
        )
        for name, film in (("data", film_data), ("simulation", film_simulation)):
            if not names or name in names:
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                page.goto(URL, timeout=120000)
                frame = studio_frame(page)
                frame.add_style_tag(content=HIDE_TEXT)
                frame.evaluate(POINTER)
                film(page, frame)
                page.close()
        if not names or "stills" in names:
            take_stills(browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2))
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
