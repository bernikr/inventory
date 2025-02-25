from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TextIO
from xml.etree.ElementTree import Element  # noqa: S405 # xml.etree is unsafe, but this tool is only for personal use

import markdown
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from markdown import Extension
from markdown.inlinepatterns import InlineProcessor

from common.base import Item, flatten, parse_uuid, update_parents

if TYPE_CHECKING:
    import re
    import uuid


class HoistLinkInlineProcessor(InlineProcessor):
    def handleMatch(self, m: re.Match[str], data: str) -> tuple[Element, int, int]:  # noqa: ARG002, N802, PLR6301
        el = Element("ref")
        el.text = m.group(1)
        return el, m.start(0), m.end(0)


class HoistLinkLinkExtension(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:  # noqa: N802, PLR6301
        md.inlinePatterns.register(HoistLinkInlineProcessor(r"\[\[#(.+)\]\]", md), "hoist", 175)


def parse_inventory_file(file: str | Path) -> Item:
    with Path(file).open("r", encoding="utf-8") as f:
        inp = f.read()
    html = markdown.markdown(inp, extensions=[HoistLinkLinkExtension(), "nl2br"])
    html = "".join(line.strip() for line in html.split("\n"))  # remove html formating whitespace for simpler soup
    doc = BeautifulSoup(html, "html.parser")

    hoists = {}
    root = Item("root")
    cur_root = root
    for e in doc.children:
        match e:
            case Tag(name="ul"):
                cur_root.children += parse_list(e, hoists)
            case Tag(name="h1"):
                cur_root = hoists[e.text]
            case _:
                msg = f"Unknown first level child: {type(e)}: {e}"
                raise NotImplementedError(msg)
    update_parents(root)
    return root


def parse_list_item(li: Tag, hoists: dict[str, Item]) -> Item:
    strings: list[str] = [e for e in li.contents if isinstance(e, NavigableString)]
    sublists: list[Tag] = [e for e in li.contents if isinstance(e, Tag) and e.name == "ul"]
    refs: list[str] = [e.text for e in li.contents if isinstance(e, Tag) and e.name == "ref"]
    uuids: list[uuid.UUID] = [
        parse_uuid(str(e.attrs["href"])) for e in li.contents if isinstance(e, Tag) and e.name == "a"
    ]

    if len(refs) == 1:
        item = Item(refs[0].strip(), hoisted=True)
        hoists[item.name] = item
    elif len(strings) == 1:
        item = Item(strings[0].strip())
    else:
        msg = f"Unknown li: {type(li)}: {li}"
        raise NotImplementedError(msg)

    if len(sublists) > 1:
        msg = f"Too many sublists: {type(li)}: {li}"
        raise NotImplementedError(msg)
    if sublists:
        item.children = parse_list(sublists[0], hoists)

    if len(uuids) > 1:
        msg = f"Too many uuids: {type(li)}: {li}"
        raise NotImplementedError(msg)
    if uuids:
        item.uuid = uuids[0]

    return item


def parse_list(ul: Tag, hoists: dict[str, Item]) -> list[Item]:
    children = []
    for e in ul.children:
        match e:
            case Tag(name="li"):
                children.append(parse_list_item(e, hoists))
            case _:
                msg = f"Unknown list child: {type(e)}: {e}"
                raise NotImplementedError(msg)
    return children


def render_item(f: TextIO, i: Item, depth: int = 0) -> None:
    f.write("\t" * depth + "- ")
    if i.hoisted:
        f.write(f"[[#{i.name}]]")
    else:
        f.write(i.name)
    if i.uuid:
        f.write(f" [](uuid:{i.uuid})")
    f.write("\n")
    if not i.hoisted:
        for c in i.children:
            render_item(f, c, depth + 1)


def save_inventory_file(file: str | Path, root: Item) -> None:
    with Path(file).open("w", encoding="utf-8") as f:
        for i in root.children:
            render_item(f, i)
        for h in (h for h in flatten(root) if h.hoisted):
            f.write(f"\n# {h.name}\n")
            for i in h.children:
                render_item(f, i)
