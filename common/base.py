from __future__ import annotations

import base64
import uuid
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    uuid: uuid.UUID | None = None
    children: list[Item] = field(default_factory=list)
    parent: Item | None = None
    hoisted: bool = False


def parse_uuid(ref: str | uuid.UUID) -> uuid.UUID:
    if isinstance(ref, uuid.UUID):
        return ref

    ref = ref.removeprefix("uuid:")

    if len(ref) == 36:  # noqa: PLR2004: 35 is length of normal formated uuid
        return uuid.UUID(ref)
    if len(ref) == 22:  # noqa: PLR2004: 22 is length of base64 encoded uuid
        return uuid.UUID(bytes=base64.urlsafe_b64decode(ref + "=="))
    msg = f"Invalid UUID: {ref}"
    raise ValueError(msg)


def display_uuid(uuid: uuid.UUID | None) -> str:
    return f" ({str(uuid)[:8]})" if uuid is not None else ""


def print_tree(tree: Item, level: int = 0) -> None:
    print(f"{'  ' * level}{'*' if tree.hoisted else ''}{tree.name}{display_uuid(tree.uuid)}")
    for e in tree.children:
        print_tree(e, level + 1)


def flatten(tree: Item, *, depth_first: bool = False) -> list[Item]:
    q: deque[Item] = deque()
    q.append(tree)
    res = []
    while q:
        e = q.pop() if depth_first else q.popleft()
        res.append(e)
        q.extend(reversed(e.children) if depth_first else e.children)
    return res


def update_parents(i: Item) -> None:
    for c in i.children:
        c.parent = i
        update_parents(c)
