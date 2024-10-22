from __future__ import annotations

import argparse
import base64
import os
import uuid
from collections import deque
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

import markdown
from bs4 import BeautifulSoup, Tag, NavigableString
from dotenv import load_dotenv
from markdown import Extension
from markdown.inlinepatterns import InlineProcessor


@dataclass
class Item:
    name: str
    uuid: uuid.UUID = None
    children: list[Item] = field(default_factory=list)
    parent: Item = None
    hoisted: bool = False


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


def update_parents(i: Item):
    for c in i.children:
        c.parent = i
        update_parents(c)


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


def parse_uuid(ref: str) -> uuid.UUID:
    if ref.startswith("uuid:"):
        ref = ref[5:]

    if len(ref) == 36:
        return uuid.UUID(ref)
    elif len(ref) == 22:
        return uuid.UUID(bytes=base64.urlsafe_b64decode(ref + "=="))
    else:
        raise NotImplementedError(f"Invalid UUID: {ref}")


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


def print_tree(tree: Item, level=0):
    print(
        f"{"  "*level}{"*" if tree.hoisted else ""}{tree.name}{f" ({str(tree.uuid)[:8]})" if tree.uuid is not None else ""}"
    )
    for e in tree.children:
        print_tree(e, level + 1)


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


def hoists_search(root: Item, bfs: bool = True) -> list[Item]:
    q: deque[Item] = deque()
    q.append(root)
    res = []
    while q:
        e = q.popleft() if bfs else q.pop()
        if e.hoisted:
            res.append(e)
        q.extend(e.children if bfs else reversed(e.children))
    return res


def save_inventory_file(file: str, root: Item):
    with open(file, "w", encoding="utf-8") as f:
        for i in root.children:
            render_item(f, i)
        for h in hoists_search(root):
            f.write(f"\n# {h.name}\n")
            for i in h.children:
                render_item(f, i)


def collect_uuids(root: Item) -> dict[uuid.UUID, Item]:
    def _coll(i: Item, d: dict[uuid.UUID, Item]):
        if i.uuid:
            d[i.uuid] = i
        for c in i.children:
            _coll(c, d)

    res = {}
    _coll(root, res)
    return res


def search_uuid(s: str, tree: Item) -> Item:
    candidates = [
        item for id, item in collect_uuids(tree).items() if str(id).startswith(s)
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(f"{len(candidates)} uuids starting with '{s}' found")


def hoist(args, tree: Item) -> bool:
    i = search_uuid(args.uuid, tree)
    i.hoisted = True
    return True


def unhoist(args, tree: Item) -> bool:
    i = search_uuid(args.uuid, tree)
    i.hoisted = False
    return True


def move(args, tree: Item) -> bool:
    item = search_uuid(args.item, tree)
    into = search_uuid(args.into, tree)
    into.children.append(item)
    item.parent.children.remove(item)
    update_parents(tree)
    return True


if __name__ == "__main__":
    load_dotenv()
    INVENTORY_FILE = os.environ["INVENTORY_FILE"]

    p = argparse.ArgumentParser()
    sps = p.add_subparsers()

    format_p = sps.add_parser("format")
    format_p.set_defaults(func=lambda *a, **b: True)

    hoist_p = sps.add_parser("hoist")
    hoist_p.add_argument("uuid")
    hoist_p.set_defaults(func=hoist)

    unhoist_p = sps.add_parser("unhoist")
    unhoist_p.add_argument("uuid")
    unhoist_p.set_defaults(func=unhoist)

    move_p = sps.add_parser("move")
    move_p.add_argument("item")
    move_p.add_argument("into")
    move_p.set_defaults(func=move)

    args = p.parse_args()
    tree = parse_inventory_file(INVENTORY_FILE)
    if args.func(args, tree):
        save_inventory_file(INVENTORY_FILE, tree)
