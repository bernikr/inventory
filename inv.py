
from __future__ import annotations

import cmd
import os
import uuid
from enum import Enum

from dotenv import load_dotenv

from common.base import Item, flatten, parse_uuid, print_tree, update_parents
from common.parser import parse_inventory_file, save_inventory_file


def search_item(s: str | uuid.UUID, tree: Item, uuid_only=False) -> Item:
    try:
        uid = parse_uuid(s)
        return next(i for i in flatten(tree) if i.uuid == uid)
    except ValueError:
        pass
    except StopIteration:
        raise ValueError("uuid not found") from None

    uuid_candidates = [i for i in flatten(tree) if str(i.uuid).startswith(s.lower())]
    if len(uuid_candidates) == 1:
        return uuid_candidates[0]

    name_candidates = [i for i in flatten(tree) if i.name.lower().startswith(s.lower())]
    if not uuid_only:
        if len(name_candidates) == 1 and len(s) > 4:
            return name_candidates[0]

    raise ValueError(
        f"{len(uuid_candidates)} uuids and {len(name_candidates)} names starting with '{s}' found"
    )


class CliMode(Enum):
    NEW_UUID = "new uuid"
    DEFAULT = ""
    MOVE = "move"


class InventoryCli(cmd.Cmd):
    prompt = "> "
    mode: CliMode = CliMode.DEFAULT
    selected_item: Item | None = None
    tree: Item = None

    def __init__(self, file):
        super().__init__()
        self.file = file
        self.intro = f"Welcome to the Inventory Management!\nUsing File: {self.file}"

    def precmd(self, line):
        self.tree = parse_inventory_file(self.file)
        if self.selected_item and self.selected_item.uuid:
            self.selected_item = search_item(self.selected_item.uuid, self.tree)
        elif self.selected_item:
            self.selected_item = search_item(self.selected_item.name, self.tree)
        return line

    def postcmd(self, stop, line):
        self.prompt = f"\n{f"SELECTED: {self.selected_item.name}{f" ({str(self.selected_item.uuid)[:8]})" if self.selected_item.uuid else ""}\n" if self.selected_item else "" }{self.mode.value}> "
        update_parents(self.tree)
        save_inventory_file(self.file, self.tree)
        return stop

    def default(self, line):
        if self.mode == CliMode.NEW_UUID:
            try:
                uid = parse_uuid(line)
            except ValueError:
                print(f"Invalid UUID: {line}")
                return
            self.selected_item.uuid = uid
            self.mode = CliMode.DEFAULT
            return

        try:
            item = search_item(line, self.tree)
        except ValueError:
            print(f"Item not found: {line}")
            return

        match self.mode:
            case CliMode.DEFAULT:
                self.selected_item = item
            case CliMode.MOVE:
                item.children.append(self.selected_item)
                self.selected_item.parent.children.remove(self.selected_item)
                self.mode = CliMode.DEFAULT
            case _:
                raise NotImplementedError(f"Unknown mode {self.mode}")

    def do_move(self, _):
        if self.selected_item:
            self.mode = CliMode.MOVE
        else:
            print("Select an item first")

    def do_setid(self, _):
        if self.selected_item:
            self.mode = CliMode.NEW_UUID
        else:
            print("Select an item first")

    def do_rmid(self, _):
        self.selected_item.uuid = None

    def do_hoist(self, _):
        self.selected_item.hoisted = True

    def do_unhoist(self, _):
        self.selected_item.hoisted = False

    def do_unselect(self, _):
        self.selected_item = None

    def do_contents(self, _):
        i = self.selected_item if self.selected_item else self.tree
        print_tree(i)

    def do_loc(self, _):
        if self.selected_item:
            locs = []
            i = self.selected_item
            while i.parent is not None:
                locs.append(i)
                i = i.parent
            for i, loc in enumerate(reversed(locs)):
                print("  "*i + loc.name)
        else:
            print("Select an item first")

    @staticmethod
    def do_exit(_):
        return True



if __name__ == "__main__":
    load_dotenv()
    INVENTORY_FILE = os.environ["INVENTORY_FILE"]

    InventoryCli(INVENTORY_FILE).cmdloop()
