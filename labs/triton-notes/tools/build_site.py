#!/usr/bin/env python3
"""Build the basic and advanced Triton Notes pages from Markdown.

No dependencies. Run from the repo root:

    python3 tools/build_site.py

Reads 01.md, renders it to 01.html. A diagram is placed by writing its
filename on its own line, wrapped in double braces:

    {{01-host-device-flow.html}}

right where it should appear in the reading order — no separate table
mapping headings to files to keep in sync by hand. The diagram's <title>
and an optional `<!-- fig-height: NNN -->` comment (see figure_embed) are
read from the file itself, so the notes only ever need the filename.
The advanced source is retained but hidden (not in PAGES below); add an
entry there and drop `{{name.html}}` markers into ADVANCED.md to turn it on.
"""

from __future__ import annotations

import html
import os
import re
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = "assets/01"

PAGES = (
    {
        "source": "01.md",
        "output": "01.html",
        "description": "Working notes on writing GPU kernels with Triton — tiles, program ids, offsets, masking, and the launch grid, with interactive figures.",
        "active": "basic",
        "diagram_dir": "assets/01/diagrams",
    },
)

CACHE_BUST = "57"




SHOW_PASTED_IMAGES = False




KEYWORDS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
    "del", "elif", "else", "except", "finally", "for", "from", "global", "if",
    "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
    "return", "try", "while", "with", "yield", "True", "False", "None",
}
BUILTINS = {
    "print", "range", "len", "int", "float", "str", "bool", "list", "dict",
    "tuple", "set", "self", "super", "isinstance", "enumerate", "zip", "min",
    "max", "sum", "abs", "type", "torch", "triton", "tl", "np", "os",
}

CONSTANTS = {"True", "False", "None"}

PY_TOKEN = re.compile(
    r"""(?P<comment>\#[^\n]*)
      | (?P<string>'''(?:.|\n)*?'''|\"\"\"(?:.|\n)*?\"\"\"|'[^'\n]*'|\"[^\"\n]*\")
      | (?P<decorator>@[A-Za-z_][\w.]*)
      | (?P<def>\b(?:def|class)\s+[A-Za-z_]\w*)
      | (?P<number>\b\d+\.?\d*(?:e-?\d+)?\b)
      | (?P<word>[A-Za-z_]\w*)
    """,
    re.VERBOSE,
)


def highlight_python(code: str) -> str:
    out, last = [], 0
    for m in PY_TOKEN.finditer(code):
        out.append(html.escape(code[last:m.start()]))
        kind = m.lastgroup
        text = m.group()
        if kind == "def":
            head, name = text.split(None, 1)

            name_cls = "t-nc" if head == "class" else "t-f"
            out.append(
                f'<span class="t-k">{head}</span> '
                f'<span class="{name_cls}">{html.escape(name)}</span>'
            )
        elif kind == "word":
            if text in CONSTANTS:
                cls = "t-n"
            elif text in KEYWORDS:
                cls = "t-k"
            elif text in BUILTINS:
                cls = "t-b"
            else:
                cls = None
            out.append(f'<span class="{cls}">{text}</span>' if cls else text)
        else:
            cls = {"comment": "t-c", "string": "t-s", "decorator": "t-d", "number": "t-n"}[kind]
            out.append(f'<span class="{cls}">{html.escape(text)}</span>')
        last = m.end()
    out.append(html.escape(code[last:]))
    return "".join(out)


LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
FIGURE_MARKER_RE = re.compile(r"^\{\{\s*([\w.-]+\.html)\s*\}\}$")


FIGURE_MARKER_NEAR_RE = re.compile(r"\{\{\s*[\w.-]+\.html\s*\}\}")
BARE_URL_RE = re.compile(r"(?<![\"'=(\w])(https?://[^\s<>)\]]+[^\s<>)\].,;:])")
BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
ITAL_RE = re.compile(r"(?<![\w*])[_*](?=[^\s_*])(.+?)(?<=[^\s_*])[_*](?![\w*])")



CURRENT_DIAGRAM_DIR = ""

DEFAULT_FIGURE_HEIGHT = 400
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_FIG_HEIGHT_RE = re.compile(r"<!--\s*fig-height:\s*(\d+)\s*-->")
_diagram_meta_cache: dict[str, tuple[str, int]] = {}


def diagram_meta(name: str, diagram_dir: str) -> tuple[str, int]:
    """A figure's title and initial height come from the diagram file itself
    — its <title> tag, and an optional `<!-- fig-height: NNN -->` comment —
    so a `{{name.html}}` marker in the notes never needs a companion table
    kept in sync by hand. No fig-height comment just means one extra layout
    jump while ds.js reports the real height on load (see figure_embed)."""
    key = f"{diagram_dir}/{name}"
    if key in _diagram_meta_cache:
        return _diagram_meta_cache[key]
    path = os.path.join(ROOT, diagram_dir, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing diagram: {diagram_dir}/{name}")
    with open(path, encoding="utf-8") as fh:
        head = fh.read(2000)
    title_m = _TITLE_RE.search(head)
    title = title_m.group(1).strip() if title_m else name
    height_m = _FIG_HEIGHT_RE.search(head)
    height = int(height_m.group(1)) if height_m else DEFAULT_FIGURE_HEIGHT
    _diagram_meta_cache[key] = (title, height)
    return title, height


def inline(text: str, _slots: list[str] | None = None) -> str:
    """Render inline markdown. Code spans and links are parked as sentinels so
    later passes cannot reach inside them. A link label can itself contain a
    code span, so the recursive call for it shares this call's slots rather
    than starting a fresh list — otherwise the label's sentinel indices are
    resolved against the wrong (empty) list."""
    top_level = _slots is None
    slots: list[str] = _slots if _slots is not None else []

    def park(fragment: str) -> str:
        slots.append(fragment)
        return f"\x00{len(slots) - 1}\x00"

    def code_span(m: re.Match) -> str:
        return park(f"<code>{html.escape(m.group(1))}</code>")

    text = re.sub(r"`([^`\n]+)`", code_span, text)

    def embed(m: re.Match) -> str:
        return park(image_tag(m.group(1)))

    text = EMBED_RE.sub(embed, text)

    def link(m: re.Match) -> str:
        label, href = m.group(1), html.escape(m.group(2), quote=True)
        return park(f'<a href="{href}" target="_blank" rel="noopener">{inline(label, slots)}</a>')

    text = LINK_RE.sub(link, text)
    text = html.escape(text)

    def bare(m: re.Match) -> str:
        url = m.group(1)
        return park(f'<a href="{url}" target="_blank" rel="noopener">{shorten_url(url)}</a>')

    text = BARE_URL_RE.sub(bare, text)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITAL_RE.sub(r"<em>\1</em>", text)

    if not top_level:
        return text



    resolved = None
    while resolved != text:
        resolved = text
        text = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)
    return text


def shorten_url(url: str) -> str:
    """Long bare URLs wreck a text column; show host + tail instead."""
    display = re.sub(r"^https?://(www\.)?", "", url)
    if len(display) <= 48:
        return html.escape(display)
    host, _, rest = display.partition("/")
    tail = rest.rstrip("/").rsplit("/", 1)[-1]
    return html.escape(f"{host}/…/{tail[:32]}") if tail else html.escape(host)


def image_tag(name: str) -> str:
    name = name.strip()
    is_logo = name == "triton.png"
    if not SHOW_PASTED_IMAGES and not is_logo:
        return ""
    path = os.path.join(ROOT, IMAGE_DIR, name)
    if not os.path.exists(path):
        print(f"  · skipped missing image: {name}", file=sys.stderr)
        return ""
    src = html.escape(f"{IMAGE_DIR}/{name}".replace(" ", "%20"), quote=True)
    if is_logo:
        return (
            '<figure class="article-logo">'
            f'<img src="{src}" alt="Triton logo" decoding="async">'
            "</figure>"
        )
    return (
        f'<figure class="shot"><a href="{src}" target="_blank" rel="noopener">'
        f'<img src="{src}" alt="" loading="lazy" decoding="async"></a></figure>'
    )


def slugify(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text).strip("-")





@dataclass
class Heading:
    level: int
    text: str
    slug: str


@dataclass
class Section:
    heading: Heading | None
    blocks: list[str] = field(default_factory=list)


LIST_RE = re.compile(r"^(\s*)(?:([-*+])|(\d+)[.)])\s+(.*)$")
FENCE_RE = re.compile(r"^\s*```\s*(\S*)(?:[ \t]+(\S.*?))?\s*$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
CALLOUT_RE = re.compile(r"^\s*\[!(\w+)\]\s*(.*)$", re.I)


def indent_level(prefix: str) -> int:
    return prefix.count("\t") + (len(prefix.replace("\t", "")) // 2)


def render_blocks(lines: list[str]) -> list[str]:
    """Turn a list of markdown lines into a list of top-level HTML blocks."""
    blocks: list[str] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        fence = FENCE_RE.match(line)
        if fence:
            lang = fence.group(1).lower()
            title = fence.group(2) or ""
            i += 1
            body: list[str] = []
            while i < n and not FENCE_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(code_block("\n".join(body), lang, title))
            continue

        head = HEAD_RE.match(line)
        if head:
            level, text = len(head.group(1)), head.group(2)
            slug = slugify(text)
            blocks.append(
                f'<h{level} id="{slug}" class="anchored">'
                f'<a class="anchor" href="#{slug}" aria-label="Link to this section">#</a>'
                f"{inline(text)}</h{level}>"
            )
            i += 1
            continue

        if QUOTE_RE.match(line):
            quoted: list[str] = []
            while i < n:
                m = QUOTE_RE.match(lines[i])
                if not m:


                    lazy = lines[i].strip() and not HEAD_RE.match(lines[i]) \
                        and not FENCE_RE.match(lines[i]) and not LIST_RE.match(lines[i])
                    if not (quoted and lazy):
                        break
                quoted.append(m.group(1) if m else lines[i].strip())
                i += 1
            blocks.append(quote_block(quoted))
            continue

        if LIST_RE.match(line):
            consumed, html_list = render_list(lines, i)
            blocks.append(html_list)
            i = consumed
            continue

        para: list[str] = []
        while i < n and lines[i].strip() and not FENCE_RE.match(lines[i]) \
                and not HEAD_RE.match(lines[i]) and not QUOTE_RE.match(lines[i]) \
                and not LIST_RE.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        text = " ".join(para)
        marker = FIGURE_MARKER_RE.match(text.strip())
        if marker:
            name = marker.group(1)
            title, height = diagram_meta(name, CURRENT_DIAGRAM_DIR)
            blocks.append(figure_embed(name, title, height, CURRENT_DIAGRAM_DIR))
        elif EMBED_RE.fullmatch(text.strip()):
            embedded = inline(text.strip())
            if embedded.strip():
                blocks.append(embedded)
        else:



            if FIGURE_MARKER_NEAR_RE.search(text):
                print(
                    f"  · WARNING: figure marker not alone on its line, so it is "
                    f"rendered as text, not a figure:\n      {text.strip()}",
                    file=sys.stderr,
                )
            rendered = inline(text)
            if rendered.strip():
                blocks.append(f"<p>{rendered}</p>")

    return blocks


def code_block(code: str, lang: str, title: str = "") -> str:
    """Render a fence. A fence may carry a filename after the language
    (```python kernels/matmul.py); it names the block in the title bar,
    falling back to the language when absent."""
    code = code.rstrip("\n")
    dedent = min(
        (len(l) - len(l.lstrip("\t")) for l in code.split("\n") if l.strip()),
        default=0,
    )
    if dedent:
        code = "\n".join(l[dedent:] if l.startswith("\t" * dedent) else l for l in code.split("\n"))
    is_py = lang in ("python", "py")
    body = highlight_python(code) if is_py else html.escape(code)
    label = "python" if is_py else (lang or "text")


    if not (is_py or lang):
        return (
            '<figure class="code code--sketch">'
            '<div class="code-body"><div class="code-scroll">'
            f"<pre><code>{body}</code></pre></div></div></figure>"
        )

    gutter = "".join(f"<span>{i}</span>" for i in range(1, code.count("\n") + 2))
    return (
        '<figure class="code code--code">'
        '<figcaption>'
        '<span class="lights" aria-hidden="true"><i></i><i></i><i></i></span>'
        f'<span class="lang">{html.escape(title or label)}</span>'
        '<button class="copy" type="button" data-copy>Copy</button>'
        '</figcaption>'
        '<div class="code-body">'
        f'<div class="gutter" aria-hidden="true">{gutter}</div>'
        f'<div class="code-scroll"><pre><code>{body}</code></pre></div>'
        '</div></figure>'
    )


def quote_block(lines: list[str]) -> str:
    title, kind = None, "note"
    if lines:
        m = CALLOUT_RE.match(lines[0])
        if m:
            kind = m.group(1).lower()
            title = m.group(2).strip() or m.group(1).capitalize()
            lines = lines[1:]
    inner = "\n".join(render_blocks(lines))
    if title is None:
        return f"<blockquote>{inner}</blockquote>"
    head = f'<p class="callout-title">{inline(title)}</p>'
    return f'<aside class="callout callout--{html.escape(kind)}">{head}{inner}</aside>'


def render_list(lines: list[str], start: int) -> tuple[int, str]:
    """Render one (possibly nested) list starting at `start`."""
    i, n = start, len(lines)
    items: list[tuple[int, bool, int | None, str]] = []
    while i < n:
        m = LIST_RE.match(lines[i])
        if not m:
            if not lines[i].strip():
                nxt = i + 1
                if nxt < n and LIST_RE.match(lines[nxt]):
                    i += 1
                    continue
            break
        if m.group(4).strip():
            ordinal = int(m.group(3)) if m.group(3) is not None else None
            items.append((indent_level(m.group(1)), ordinal is not None, ordinal, m.group(4)))
        i += 1

    if not items:
        return i, ""

    def build(pos: int, level: int) -> tuple[int, str]:
        ordered = items[pos][1]
        ordinal = items[pos][2]
        if ordered and ordinal != 1:
            out = [f'<ol start="{ordinal}">']
        else:
            out = ["<ol>" if ordered else "<ul>"]
        while pos < len(items) and items[pos][0] >= level:
            lvl, is_ord, _, text = items[pos]
            if lvl > level:
                pos, nested = build(pos, lvl)
                out[-1] = out[-1][:-5] + nested + "</li>"
                continue
            if is_ord != ordered:
                break
            out.append(f"<li>{inline(text)}</li>")
            pos += 1
        out.append("</ol>" if ordered else "</ul>")
        return pos, "".join(out)

    _, markup = build(0, items[0][0])
    return i, markup





def figure_embed(name: str, title: str, height: int, diagram_dir: str) -> str:
    return (
        '<div class="figure" data-figure>'
        f'<iframe src="{diagram_dir}/{name}?v={CACHE_BUST}" title="{html.escape(title, quote=True)}" '
        f'height="{height}" loading="lazy" scrolling="no"></iframe>'
        "</div>"
    )


def split_sections(blocks: list[str]) -> list[Section]:
    sections = [Section(None)]
    for block in blocks:
        m = re.match(r'<h([1-6]) id="([^"]+)"', block)
        if m:
            text = re.sub(r"<[^>]+>", "", block)
            sections.append(Section(Heading(int(m.group(1)), text.lstrip("#"), m.group(2))))
        sections[-1].blocks.append(block)
    return sections


def uniquify_heading_ids(blocks: list[str]) -> list[str]:
    """Give repeated headings stable, GitHub-style suffixed anchors."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    for block in blocks:
        match = re.match(r'<h[1-6] id="([^"]+)"', block)
        if not match:
            unique.append(block)
            continue

        base = match.group(1)
        occurrence = seen.get(base, 0)
        seen[base] = occurrence + 1
        if occurrence:
            slug = f"{base}-{occurrence}"
            block = block.replace(f'id="{base}"', f'id="{slug}"', 1)
            block = block.replace(f'href="#{base}"', f'href="#{slug}"', 1)
        unique.append(block)
    return unique


def build_toc(sections: list[Section]) -> str:
    out = ['<nav class="toc" aria-label="Table of contents"><ol class="toc-list">']
    for section in sections:
        h = section.heading
        if not h or h.level > 3:
            continue
        out.append(
            f'<li class="toc-item toc-item--h{h.level}">'
            f'<a href="#{h.slug}" data-toc="{h.slug}">{html.escape(h.text)}</a></li>'
        )
    out.append("</ol></nav>")
    return "".join(out)


def read_time(markdown: str) -> int:
    words = len(re.findall(r"\b[\w'-]+\b", re.sub(r"```.*?```", "", markdown, flags=re.S)))
    return max(1, round(words / 210))


def page_nav(active: str) -> str:
    return ""


def build_page(spec: dict) -> None:
    global CURRENT_DIAGRAM_DIR
    source = os.path.join(ROOT, spec["source"])
    output = os.path.join(ROOT, spec["output"])
    CURRENT_DIAGRAM_DIR = spec["diagram_dir"]

    with open(source, encoding="utf-8") as fh:
        raw = fh.read()

    lines = raw.replace("\r\n", "\n").split("\n")

    title = "Triton Notes"
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]

    blocks = uniquify_heading_ids(render_blocks(lines))
    sections = split_sections(blocks)
    slugs = [s.heading.slug for s in sections if s.heading]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise RuntimeError(f"duplicate heading ids in {spec['source']}: {', '.join(duplicates)}")

    article = "\n".join(block for section in sections for block in section.blocks)
    placed = article.count('class="figure" data-figure')
    toc = build_toc(sections)
    minutes = read_time(raw)
    chapters = sum(1 for s in sections if s.heading and s.heading.level == 1)

    with open(os.path.join(ROOT, "site", "page.html"), encoding="utf-8") as fh:
        template = fh.read()

    page = (
        template.replace("{{TITLE}}", html.escape(title))
        .replace("{{SITE_TITLE}}", "Triton Notes")
        .replace("{{DESCRIPTION}}", html.escape(spec["description"], quote=True))
        .replace("{{PAGE_NAV}}", page_nav(spec["active"]))
        .replace("{{TOC}}", toc)
        .replace("{{ARTICLE}}", article)
        .replace("{{READ_TIME}}", str(minutes))
        .replace("{{FIGURES}}", str(placed))
        .replace("{{CHAPTERS}}", str(chapters))
        .replace("{{V}}", CACHE_BUST)
    )

    with open(output, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"built {os.path.relpath(output, ROOT)} — {placed} figures, {minutes} min read")


def main() -> int:
    for spec in PAGES:
        build_page(spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
