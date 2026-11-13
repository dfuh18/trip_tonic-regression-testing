#!/usr/bin/env python3
"""Read-only access to the thesis manuscript (.docx).

Claude Code cannot open .docx files. This extracts named sections, tables and
search hits from the manuscript so a session can read section 3.4 without
pulling two hundred pages through its context window.

The manuscript is NEVER written to. Nothing in the thesis folder is modified.

Usage
  python tools/manuscript.py --outline
  python tools/manuscript.py --section 3.4
  python tools/manuscript.py --section 4.2.2 --section 4.3
  python tools/manuscript.py --tables
  python tools/manuscript.py --table 11
  python tools/manuscript.py --search "state reset"
  python tools/manuscript.py --which          # which file is being read

Resolution order for the manuscript path:
  1. $MA_MANUSCRIPT (a full path to a .docx)
  2. $MA_MANUSCRIPT_DIR/MA_Thesis_*.docx  -> newest by filename

Both are read from the environment or from this subtree's .env. There is no
built-in default: the manuscript lives in a private folder on the author's
machine, and its path does not belong in the repository.

Filenames end in a date (..._260917.docx), so "newest by filename" is "latest
revision". Pin an exact file with $MA_MANUSCRIPT when a result must be
reproducible against one revision.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ElementTree

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
MANUSCRIPT_GLOB = "MA_Thesis_*.docx"

# WordprocessingML is parsed as a tree, not with regexes over the markup.
# Regex block-splitting is wrong here for two reasons this manuscript exercises:
# a self-closing <w:p w14:paraId="..."/> matches an opening tag that never
# closes, and a figure paragraph nests another <w:p> inside a text box, so a
# non-greedy match ends on the inner close and spills raw XML into the output.
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
HEADING = re.compile(r"^Heading([1-9])$")
# "3.4 Implementation" / "2.6.1 Where testing applies"
NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
TABLE_CAPTION = re.compile(r"Table\s*(\d+)")


def resolve_path():
    try:  # the same .env the pipeline reads; never overrides the environment
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass
    explicit = os.environ.get("MA_MANUSCRIPT")
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit("MA_MANUSCRIPT is set but not a file: " + explicit)
        return explicit
    folder = os.environ.get("MA_MANUSCRIPT_DIR")
    if not folder:
        sys.exit("Set MA_MANUSCRIPT (a .docx) or MA_MANUSCRIPT_DIR (the folder holding "
                 + MANUSCRIPT_GLOB + ") in the environment or in .env.")
    hits = sorted(glob.glob(os.path.join(folder, MANUSCRIPT_GLOB)))
    if not hits:
        sys.exit(
            "No " + MANUSCRIPT_GLOB + " found in " + folder + "\n"
            "Set MA_MANUSCRIPT to the manuscript path, or MA_MANUSCRIPT_DIR "
            "to the folder holding it."
        )
    return hits[-1]


def clean(raw):
    return re.sub(r"\s+", " ", raw).strip()


def collect_text(el, into):
    """Depth-first text collection, skipping mc:Fallback.

    A drawing is stored twice, as mc:Choice and mc:Fallback. Taking both would
    print every figure's text a second time.
    """
    for child in el:
        if child.tag == MC + "Fallback":
            continue
        if child.tag == W + "t" and child.text:
            into.append(child.text)
        elif child.tag in (W + "tab",):
            into.append(" ")
        elif child.tag in (W + "br", W + "cr"):
            into.append(" ")
        else:
            collect_text(child, into)


def para_text(block):
    parts = []
    collect_text(block, parts)
    return clean("".join(parts))


def is_table(block):
    return block.tag == W + "tbl"


def table_markdown(block):
    rows = []
    for tr in block.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            cells.append(clean(" ".join(para_text(p) for p in tc.findall(W + "p"))))
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def load_blocks(path):
    """Top-level paragraphs and tables of the document body, in order."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    body = root.find(W + "body")
    if body is None:
        sys.exit("No <w:body> in " + path)
    return [el for el in body if el.tag in (W + "p", W + "tbl")]


def para_style(block):
    ppr = block.find(W + "pPr")
    if ppr is None:
        return ""
    style = ppr.find(W + "pStyle")
    return style.get(W + "val", "") if style is not None else ""


def headings(blocks):
    """(block index, level, number, title) for every heading."""
    found = []
    for i, b in enumerate(blocks):
        if is_table(b):
            continue
        lvl = HEADING.match(para_style(b))
        if not lvl:
            continue
        text = para_text(b)
        num = NUMBERED.match(text)
        if num:
            found.append((i, int(lvl.group(1)), num.group(1), num.group(2)))
        elif text:
            found.append((i, int(lvl.group(1)), "", text))
    return found


def render(blocks, start, end):
    out = []
    for b in blocks[start:end]:
        if is_table(b):
            md = table_markdown(b)
            if md:
                out.append(md)
            continue
        name = para_style(b)
        text = para_text(b)
        if not text:
            continue
        lvl = HEADING.match(name)
        if lvl:
            out.append("#" * min(int(lvl.group(1)) + 1, 6) + " " + text)
        elif name == "Caption":
            out.append("*" + text + "*")
        else:
            out.append(text)
    return "\n\n".join(out)


def cmd_outline(blocks):
    for _, lvl, num, title in headings(blocks):
        label = (num + " " + title).strip() if num else title
        print("  " * (lvl - 1) + label)


def cmd_section(blocks, wanted):
    hs = headings(blocks)
    target = None
    for pos, entry in enumerate(hs):
        if entry[2] == wanted:
            target = (pos,) + entry
            break
    if target is None:
        sys.exit(
            "No section numbered " + wanted + ". Run --outline to see what exists."
        )
    pos, idx, lvl, num, _title = target
    end = len(blocks)
    for nidx, nlvl, nnum, _ in hs[pos + 1:]:
        # A section ends at the next heading not nested beneath it.
        if nnum and not nnum.startswith(num + "."):
            end = nidx
            break
        if not nnum and nlvl <= lvl:
            end = nidx
            break
    print(render(blocks, idx, end))


def table_captions(blocks):
    found = {}
    for i, b in enumerate(blocks):
        if is_table(b) or para_style(b) != "Caption":
            continue
        text = para_text(b)
        cap = TABLE_CAPTION.match(text)
        if cap:
            found[int(cap.group(1))] = (i, text)
    return found


def cmd_tables(blocks, which):
    captions = table_captions(blocks)
    if which is None:
        for n in sorted(captions):
            print(captions[n][1])
        return
    n = int(which)
    if n not in captions:
        sys.exit("No Table " + str(n) + ". Run --tables to list them.")
    cap_idx, cap_text = captions[n]
    # Captions follow their table in this manuscript; the forward scan is a
    # fallback in case a revision ever puts the caption first.
    order = list(range(cap_idx - 1, max(cap_idx - 6, -1), -1))
    order += list(range(cap_idx + 1, min(cap_idx + 6, len(blocks))))
    for j in order:
        if is_table(blocks[j]):
            print("*" + cap_text + "*\n")
            print(table_markdown(blocks[j]))
            return
    sys.exit("Found the caption for Table " + str(n) + " but no table beside it.")


def cmd_search(blocks, pattern):
    rx = re.compile(pattern, re.I)
    hs = headings(blocks)
    for i, b in enumerate(blocks):
        text = table_markdown(b) if is_table(b) else para_text(b)
        if not text or not rx.search(text):
            continue
        where = ""
        for idx, _lvl, num, title in hs:
            if idx <= i:
                where = (num + " " + title).strip()
        print("[" + where + "] " + text[:300])


def main():
    # The manuscript contains Greek letters and diacritics; the Windows console
    # is cp1252 and raises UnicodeEncodeError on them mid-section.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(
        description="Read-only extraction from the thesis manuscript.",
    )
    ap.add_argument("--outline", action="store_true", help="list every heading")
    ap.add_argument("--section", action="append", default=[], metavar="N",
                    help="print a numbered section, e.g. 3.4")
    ap.add_argument("--tables", action="store_true", help="list table captions")
    ap.add_argument("--table", metavar="N", help="print one table as markdown")
    ap.add_argument("--search", metavar="REGEX", help="print matching paragraphs")
    ap.add_argument("--which", action="store_true", help="print the file being read")
    args = ap.parse_args()

    path = resolve_path()
    if args.which:
        print(path)
        return
    if not any([args.outline, args.section, args.tables, args.table, args.search]):
        ap.print_help()
        return

    blocks = load_blocks(path)
    print("<!-- source: " + os.path.basename(path) + " -->\n")
    if args.outline:
        cmd_outline(blocks)
    for s in args.section:
        cmd_section(blocks, s)
        print()
    if args.tables:
        cmd_tables(blocks, None)
    if args.table:
        cmd_tables(blocks, args.table)
    if args.search:
        cmd_search(blocks, args.search)


if __name__ == "__main__":
    main()
