from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from common.base import Item, flatten, parse_uuid, update_parents
from common.parser import parse_inventory_file, save_inventory_file


def search_item(s: str, tree: Item) -> Item:
    try:
        id = parse_uuid(s)
        return next(i for i in flatten(tree) if i.uuid == id)
    except ValueError:
        pass

    uuid_candidates = [i for i in flatten(tree) if str(i.uuid).startswith(s.lower())]
    if len(uuid_candidates) == 1:
        return uuid_candidates[0]

    name_candidates = [i for i in flatten(tree) if i.name.lower().startswith(s.lower())]
    if len(name_candidates) == 1 and len(s) > 4:
        return name_candidates[0]

    raise ValueError(
        f"{len(uuid_candidates)} uuids and {len(name_candidates)} names starting with '{s}' found"
    )


def hoist(args, tree: Item) -> bool:
    i = search_item(args.item, tree)
    i.hoisted = True
    return True


def unhoist(args, tree: Item) -> bool:
    i = search_item(args.item, tree)
    i.hoisted = False
    return True


def find(args, tree: Item) -> bool:
    i = search_item(args.item, tree)  # todo fuzzy search
    while i:
        print(i.name)
        i = i.parent
    return False


def move(args, tree: Item) -> bool:
    item = search_item(args.item, tree)
    into = search_item(args.into, tree)
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
    hoist_p.add_argument("item")
    hoist_p.set_defaults(func=hoist)

    unhoist_p = sps.add_parser("unhoist")
    unhoist_p.add_argument("item")
    unhoist_p.set_defaults(func=unhoist)

    move_p = sps.add_parser("move")
    move_p.add_argument("item")
    move_p.add_argument("into")
    move_p.set_defaults(func=move)

    find_p = sps.add_parser("find")
    find_p.add_argument("item")
    find_p.set_defaults(func=find)

    args = p.parse_args()
    tree = parse_inventory_file(INVENTORY_FILE)
    if args.func(args, tree):
        save_inventory_file(INVENTORY_FILE, tree)
