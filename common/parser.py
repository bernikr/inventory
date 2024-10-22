from __future__ import annotations

import uuid
from xml.etree.ElementTree import Element

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag
from markdown import Extension
from markdown.inlinepatterns import InlineProcessor

from common.base import Item, flatten, parse_uuid, update_parents


class HoistLinkInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        el = Element("ref")
        el.text = m.group(1)
        return el, m.start(0), m.end(0)


class HoistLinkLinkExtension(Extension):
    def extendMarkdown(self, md):
        HOIST_PATTERN = r"\[\[#(.+)\]\]"
        md.inlinePatterns.register(
            HoistLinkInlineProcessor(HOIST_PATTERN, md), "hoist", 175
        )


def parse_inventory_file(file: str) -> Item:
    with open(file, "r", encoding="utf-8") as f:
        inp = f.read()
    html = markdown.markdown(inp, extensions=[HoistLinkLinkExtension(), "nl2br"])
    html = "".join(
        line.strip() for line in html.split("\n")
    )  # remove html formating whitespace for simpler soup
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
                raise NotImplementedError(f"Unknown first level child: {type(e)}: {e}")
    update_parents(root)
    return root


def parse_list_item(li: Tag, hoists: dict[str, Item]) -> Item:
    strings: list[str] = [e for e in li.contents if isinstance(e, NavigableString)]
    sublists: list[Tag] = [
        e for e in li.contents if isinstance(e, Tag) and e.name == "ul"
    ]
    refs: list[str] = [
        e.text for e in li.contents if isinstance(e, Tag) and e.name == "ref"
    ]
    uuids: list[uuid.UUID] = [
        parse_uuid(e.attrs["href"])
        for e in li.contents
        if isinstance(e, Tag) and e.name == "a"
    ]

    if len(refs) == 1:
        item = Item(refs[0].strip(), hoisted=True)
        hoists[item.name] = item
    elif len(strings) == 1:
        item = Item(strings[0].strip())
    else:
        raise NotImplementedError(f"Unknown li: {type(li)}: {li}")

    if len(sublists) > 1:
        raise NotImplementedError(f"Too many sublists: {type(li)}: {li}")
    if sublists:
        item.children = parse_list(sublists[0], hoists)

    if len(uuids) > 1:
        raise NotImplementedError(f"Too many uuids: {type(li)}: {li}")
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
                raise NotImplementedError(f"Unknown list child: {type(e)}: {e}")
    return children


def render_item(f, i: Item, depth=0):
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


def save_inventory_file(file: str, root: Item):
    with open(file, "w", encoding="utf-8") as f:
        for i in root.children:
            render_item(f, i)
        for h in (h for h in flatten(root) if h.hoisted):
            f.write(f"\n# {h.name}\n")
            for i in h.children:
                render_item(f, i)
