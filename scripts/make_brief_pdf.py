"""Lay out docs/funding_brief.md as an A4 PDF (needs pymupdf). Returns the page count."""
from __future__ import annotations

import html
import re
from pathlib import Path

import pymupdf

CSS = """
body { font-family: sans-serif; font-size: 8.3pt; line-height: 1.22; }
h1 { font-size: 12.5pt; margin: 0 0 3pt 0; }
h2 { font-size: 9.6pt; margin: 6pt 0 2pt 0; }
p { margin: 0 0 3pt 0; }
ul { margin: 0 0 3pt 0; }
li { margin: 0 0 1.5pt 0; }
table { border-collapse: collapse; margin: 2pt 0 4pt 0; }
td, th { border: 0.5pt solid #888; padding: 1.2pt 3pt; font-size: 7.3pt; }
"""


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<i>\1</i>", t)
    return re.sub(r"`(.+?)`", r"<tt>\1</tt>", t)


def to_html(md: str) -> str:
    out, lines, k = [], md.splitlines(), 0
    while k < len(lines):
        ln = lines[k]
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("|"):
            rows = []
            while k < len(lines) and lines[k].startswith("|"):
                rows.append([c.strip() for c in lines[k].strip().strip("|").split("|")])
                k += 1
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[2:])
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>" + body
                       + "</table>")
            continue
        elif ln.startswith("- "):
            items = []
            while k < len(lines) and lines[k].startswith("- "):
                items.append(f"<li>{inline(lines[k][2:])}</li>")
                k += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        k += 1
    return "".join(out)


def make(md_path: Path, pdf_path: Path) -> int:
    story = pymupdf.Story(html=to_html(md_path.read_text(encoding="utf-8")), user_css=CSS)
    page = pymupdf.paper_rect("a4")
    where = page + (42, 40, -42, -40)
    writer = pymupdf.DocumentWriter(str(pdf_path))
    more, pages = 1, 0
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        pages += 1
    writer.close()
    return pages
