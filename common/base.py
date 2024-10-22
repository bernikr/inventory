from __future__ import annotations

import base64
import uuid
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    uuid: uuid.UUID = None
    children: list[Item] = field(default_factory=list)
    parent: Item = None
    hoisted: bool = False


def parse_uuid(ref: str) -> uuid.UUID:
    if ref.startswith("uuid:"):
        ref = ref[5:]

    if len(ref) == 36:
        return uuid.UUID(ref)
    elif len(ref) == 22:
        return uuid.UUID(bytes=base64.urlsafe_b64decode(ref + "=="))
    else:
        raise ValueError(f"Invalid UUID: {ref}")


def print_tree(tree: Item, level=0):
    print(
        f"{"  "*level}{"*" if tree.hoisted else ""}{tree.name}{f" ({str(tree.uuid)[:8]})" if tree.uuid is not None else ""}"
    )
    for e in tree.children:
        print_tree(e, level + 1)


def flatten(tree: Item, depth_first: bool = False) -> list[Item]:
    q: deque[Item] = deque()
    q.append(tree)
    res = []
    while q:
        e = q.pop() if depth_first else q.popleft()
        res.append(e)
        q.extend(reversed(e.children) if depth_first else e.children)
    return res


def update_parents(i: Item):
    for c in i.children:
        c.parent = i
        update_parents(c)
