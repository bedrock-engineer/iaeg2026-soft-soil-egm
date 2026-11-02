# /// script
# requires-python = ">=3.12"
# dependencies = ["lxml", "pillow", "python-pptx==1.0.2"]
# ///
"""Build the talk as a PowerPoint on the IAEG 2026 format, from the view's text, the speaker notes and the media
that record_media.py made.

    uv run presentation/build_pptx.py [path to "IAEG 2026 Powerpoint Format.pptx"]
"""

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).parent
OUTPUT = HERE / "output"
TEMPLATE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "IAEG 2026 Powerpoint Format.pptx"
SLIDES = json.loads((HERE / "studio/presentation_notebook/slides/src/slides.json").read_text(encoding="utf-8"))
SITE_URL = "bedrock-engineer.github.io/iaeg2026-soft-soil-egm"
NAVY = RGBColor(0x1B, 0x14, 0x64)
WIDTH, HEIGHT = 20, 11.25
TITLE_PT, BODY_PT = 44, 30
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def speaker_notes():
    """The text under each `## id` of presentation_speaker_notes.md"""
    text = (HERE / "presentation_speaker_notes.md").read_text(encoding="utf-8")
    parts = re.split(r"^## (\S+)\s*$", text, flags=re.MULTILINE)
    return {slide_id: body.strip() for slide_id, body in zip(parts[1::2], parts[2::2])}


def write(frame, lines, size, bold=False, bullet=False):
    """Fill a text frame, one paragraph per line, with real bullets if asked for"""
    frame.word_wrap = True
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = NAVY
        if bullet:
            properties = paragraph._p.get_or_add_pPr()
            properties.set("marL", str(Inches(0.45)))
            properties.set("indent", str(-Inches(0.45)))
            etree.SubElement(properties, qn("a:buChar"), char="•")
            paragraph.space_after = Pt(18)


def fit(path, x, y, w, h):
    """The position and size of an image at its aspect in a box, centered"""
    with Image.open(path) as image:
        aspect = image.width / image.height
    width = min(w, h * aspect)
    height = width / aspect
    return x + (w - width) / 2, y + (h - height) / 2, width, height


def place_title(slide, text, x=0.75, y=0.35, w=15.8, h=1.7, size=TITLE_PT, backdrop=False):
    title = slide.shapes.title
    title.left, title.top, title.width, title.height = Inches(x), Inches(y), Inches(w), Inches(h)
    frame = title.text_frame
    frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.clear()
    write(frame, [text], size, bold=True)
    frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    if backdrop:
        title.fill.solid()
        title.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def place_points(slide, points, x, y, w, h):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    write(box.text_frame, points, BODY_PT, bullet=True)


def place_image(slide, path, x, y, w, h, alt):
    left, top, width, height = fit(path, x, y, w, h)
    picture = slide.shapes.add_picture(str(path), Inches(left), Inches(top), Inches(width), Inches(height))
    picture.name = alt
    picture._element.nvPicPr.cNvPr.set("descr", alt)
    return picture


class Format:
    """The art of the IAEG format's one slide, which each slide of the talk gets a copy of"""

    def __init__(self, presentation):
        self.slide = presentation.slides[0]
        self.group = next(s for s in self.slide.shapes if s.name == "Group 2")._element
        self.art = next(s for s in self.slide.shapes if s.name == "Freeform 5")._element
        self.images = {rel.rId: rel.target_part for rel in self.slide.part.rels.values() if "image" in rel.reltype}

    def _copy(self, slide, element):
        """A copy of the element on the slide, with its images related to the slide"""
        copied = copy.deepcopy(element)
        for node in copied.iter():
            for attribute in (f"{{{R}}}embed",):
                old = node.get(attribute)
                if old in self.images:
                    node.set(attribute, slide.part.relate_to(self.images[old], self.slide.part.rels[old].reltype))
        slide.shapes._spTree.append(copied)
        return copied

    def full(self, slide):
        """The landscape and the logos as they are in the format"""
        self._copy(slide, self.art)
        self._copy(slide, self.group)

    def small(self, slide):
        """Small logos at the top right, and a strip of the landscape's ground along the bottom"""
        group = self._copy(slide, self.group)
        transform = group.find(qn("p:grpSpPr")).find(qn("a:xfrm"))
        off, ext = transform.find(qn("a:off")), transform.find(qn("a:ext"))
        width = Inches(2.6)
        ratio = int(ext.get("cy")) / int(ext.get("cx"))
        off.set("x", str(Inches(WIDTH - 0.4) - width))
        off.set("y", str(Inches(0.3)))
        ext.set("cx", str(width))
        ext.set("cy", str(int(width * ratio)))

        strip = self._copy(slide, self.art)
        properties = strip.find(qn("p:spPr"))
        transform = properties.find(qn("a:xfrm"))
        transform.find(qn("a:off")).set("y", str(Inches(HEIGHT - 0.45)))
        transform.find(qn("a:ext")).set("cy", str(Inches(0.45)))
        fill = properties.find(qn("a:blipFill"))
        blip = fill.find(qn("a:blip"))
        for extension in blip.findall(qn("a:extLst")):
            blip.remove(extension)  # A cropped SVG is not worth the risk: the PNG does
        crop = etree.Element(qn("a:srcRect"), t="72000", b="18000")
        blip.addnext(crop)
        # The strip stays behind everything else on the slide
        tree = slide.shapes._spTree
        tree.remove(strip)
        tree.insert(2, strip)


def autoplay(slide, movie, milliseconds):
    """Start the video when the slide shows and loop it, without sound, as PowerPoint writes it for 'Automatically'"""
    spid = movie.shape_id
    timing = f"""<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>
<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>
<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>
<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>
<p:par><p:cTn id="5" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="afterEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>
<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="6" dur="{milliseconds}" fill="hold"/><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>
</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>
</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>
<p:video><p:cMediaNode vol="0" mute="1"><p:cTn id="7" repeatCount="indefinite" fill="hold" display="0"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>
</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"""
    element = slide.element
    for existing in element.findall(qn("p:timing")):
        element.remove(existing)
    parsed = parse_xml(timing)
    # After p:clrMapOvr and p:transition, before p:extLst
    extensions = element.find(qn("p:extLst"))
    if extensions is not None:
        extensions.addprevious(parsed)
    else:
        element.append(parsed)


def video_seconds(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout)


def place_video(slide, name):
    """A video over the whole slide, behind its text, with its poster frame. False if it wasn't filmed yet"""
    path, poster = OUTPUT / "videos" / f"{name}.mp4", OUTPUT / "videos" / f"{name}.png"
    if not path.exists():
        return False
    if not poster.exists():  # A video that record_media.py didn't film starts as its first frame
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-frames:v", "1", str(poster)], check=True)
    movie = slide.shapes.add_movie(
        str(path), 0, 0, Inches(WIDTH), Inches(HEIGHT), poster_frame_image=str(poster), mime_type="video/mp4"
    )
    movie.name = f"Video: {name}"
    tree = slide.shapes._spTree
    tree.remove(movie._element)
    tree.insert(2, movie._element)
    autoplay(slide, movie, round(video_seconds(path) * 1000))
    return True


def build():
    presentation = Presentation(str(TEMPLATE))
    assert abs(presentation.slide_width / presentation.slide_height - 16 / 9) < 0.01
    art = Format(presentation)
    title_only = next(layout for layout in presentation.slide_layouts if layout.name == "Title Only")
    notes = speaker_notes()
    stills = OUTPUT / "stills"

    for content in SLIDES:
        slide_id, title, points = content["id"], content["title"], content["points"]
        slide = presentation.slides.add_slide(title_only)
        if slide_id == "title":
            art.full(slide)
            place_title(slide, title, x=0.9, y=1.0, w=13.2, h=3.6, size=54)
            box = slide.shapes.add_textbox(Inches(0.9), Inches(4.9), Inches(13.2), Inches(1.4))
            write(box.text_frame, points, 36)
        elif slide_id in ("data", "bim"):
            if not place_video(slide, slide_id):
                art.small(slide)
                box = slide.shapes.add_textbox(Inches(3), Inches(4.2), Inches(14), Inches(2))
                write(box.text_frame, [f"Placeholder: video '{slide_id}' goes here"], BODY_PT)
            place_title(slide, title, x=0.5, y=0.4, w=min(0.3 * len(title) + 0.6, 19), h=1.0, backdrop=True)
        elif slide_id == "simulation":
            place_video(slide, slide_id)
            place_title(slide, title, x=0.75, y=1.4, w=4.5, h=3.2)
            place_points(slide, points, 0.75, 4.7, 4.5, 4)
        elif slide_id == "pipeline":
            art.small(slide)
            place_title(slide, title)
            place_image(slide, stills / "pipeline.png", 0.75, 2.0, 18.5, 8.6, "The workflow as Data, Process, Data, from public data to a soil type per cell")
        elif slide_id == "uncertainty":
            art.small(slide)
            place_title(slide, title)
            place_image(slide, stills / "uncertainty.png", 0.75, 2.0, 18.5, 8.6, "Realizations at one CPT, and P90 / P10 of qc along a section")
        elif slide_id == "close-qr":
            art.full(slide)
            place_title(slide, title, x=0.9, y=0.7, w=13, h=1.3)
            place_image(slide, stills / "close-qr.png", 0.9, 2.0, 4.8, 4.8, f"QR code to {SITE_URL}")
            box = slide.shapes.add_textbox(Inches(6.2), Inches(3.8), Inches(13), Inches(1.2))
            write(box.text_frame, [SITE_URL], 28)
        else:
            art.small(slide)
            place_title(slide, title)
            place_points(slide, points, 0.75, 2.2, 5.2, 8.2)
            if slide_id == "problem":
                visual, alt = HERE / "public" / "egm_in_bim_context.png", "A building on piles above the sand bodies of a ground model"
            else:
                visual, alt = stills / f"{slide_id}.png", title
            place_image(slide, visual, 6.2, 2.2, 13.2, 8.2, alt)
        slide.notes_slide.notes_text_frame.text = notes[slide_id]

    # The format's own slide served as the source of the art
    slide_ids = presentation.slides._sldIdLst
    first = slide_ids[0]
    presentation.part.drop_rel(first.rId)
    slide_ids.remove(first)

    target = OUTPUT / "IAEG2026_Gevaert_Soft-Soil_EGM.pptx"
    presentation.save(str(target))
    print(target, f"{target.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    build()
