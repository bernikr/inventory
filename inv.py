import cmd
import contextlib
import os
import uuid
from enum import Enum
from pathlib import Path
from typing import assert_never

from dotenv import load_dotenv

from common.base import Item, display_uuid, flatten, parse_uuid, print_tree, update_parents
from common.parser import parse_inventory_file, save_inventory_file


def search_item(s: str | uuid.UUID, tree: Item, *, uuid_only: bool = False) -> Item:
    with contextlib.suppress(ValueError):
        s = parse_uuid(s)

    if isinstance(s, uuid.UUID):
        try:
            return next(i for i in flatten(tree) if i.uuid == s)
        except StopIteration:
            msg = "uuid not found"
            raise ValueError(msg) from None

    uuid_candidates = [i for i in flatten(tree) if str(i.uuid).startswith(s.lower())]
    if len(uuid_candidates) == 1:
        return uuid_candidates[0]

    name_candidates = [i for i in flatten(tree) if i.name.lower().startswith(s.lower())]
    if not uuid_only and len(name_candidates) == 1 and len(s) > 4:  # noqa: PLR2004: require at least 4 chars to match to assume selection was intended
        return name_candidates[0]

    msg = f"{len(uuid_candidates)} uuids and {len(name_candidates)} names starting with '{s}' found"
    raise ValueError(msg)


class CliMode(Enum):
    ADD = "add"
    CHECKOUT = "checkout"
    NEW_UUID = "new uuid"
    DEFAULT = ""
    MOVE = "move"


def move(item: Item, into: Item) -> None:
    into.children.append(item)
    if item.parent is not None:
        item.parent.children.remove(item)


class InventoryCli(cmd.Cmd):
    prompt = "> "
    mode: CliMode = CliMode.DEFAULT
    selected_item: Item | None = None
    tree: Item

    def __init__(self, file: Path | str) -> None:
        super().__init__()
        self.file = Path(file)
        self.intro = f"Welcome to the Inventory Management!\nUsing File: {self.file.as_posix()}"

    def precmd(self, line: str) -> str:
        self.tree = parse_inventory_file(self.file)
        if self.selected_item and self.selected_item.uuid:
            self.selected_item = search_item(self.selected_item.uuid, self.tree)
        elif self.selected_item:
            self.selected_item = search_item(self.selected_item.name, self.tree)
        return line

    def postcmd(self, stop: bool, line: str) -> bool:  # noqa: ARG002, FBT001
        selected_text = (
            f"SELECTED: {self.selected_item.name}{display_uuid(self.selected_item.uuid)}\n"
            if self.selected_item
            else ""
        )
        self.prompt = f"{selected_text}{self.mode.value}> "
        update_parents(self.tree)
        save_inventory_file(self.file, self.tree)
        return stop

    def default(self, line: str) -> None:  # noqa: C901: ignore too complex default method
        if self.mode == CliMode.NEW_UUID:
            if self.selected_item is None:
                raise AssertionError
            try:
                uid = parse_uuid(line)
            except ValueError:
                print(f"Invalid UUID: {line}")
                return
            self.selected_item.uuid = uid
            self.mode = CliMode.DEFAULT
            print(f"Changed UUID of {self.selected_item.name} to {str(self.selected_item.uuid)[:8]}")
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
                if not self.selected_item:
                    raise AssertionError
                move(self.selected_item, item)

                self.mode = CliMode.DEFAULT
                print(f"moved {self.selected_item.name} into {item.name}")
            case CliMode.CHECKOUT:
                self._checkout(item)
            case CliMode.ADD:
                if not self.selected_item:
                    raise AssertionError
                move(item, self.selected_item)
            case _ as unreachable:
                assert_never(unreachable)

    def do_move(self, _: str) -> None:
        if self.selected_item:
            self.mode = CliMode.MOVE
        else:
            print("Select an item first")

    def do_setid(self, _: str) -> None:
        if self.selected_item is None:
            print("Select an item first")
            return
        self.mode = CliMode.NEW_UUID

    def do_rmid(self, _: str) -> None:
        if self.selected_item is None:
            print("Select an item first")
            return
        self.selected_item.uuid = None

    def do_hoist(self, _: str) -> None:
        if self.selected_item is None:
            print("Select an item first")
            return
        self.selected_item.hoisted = True

    def do_unhoist(self, _: str) -> None:
        if self.selected_item is None:
            print("Select an item first")
            return
        self.selected_item.hoisted = False

    def do_contents(self, _: str) -> None:
        i = self.selected_item or self.tree
        print_tree(i)

    def do_loc(self, _: str) -> None:
        if self.selected_item:
            locs = []
            i = self.selected_item
            while i.parent is not None:
                locs.append(i)
                i = i.parent
            for i, loc in enumerate(reversed(locs)):
                print("  " * i + loc.name)
        else:
            print("Select an item first")

    def _checkout(self, item: Item) -> None:
        if item.parent is None:
            print("Cannot checkout root")
            return
        item.parent.children.remove(item)
        self.tree.children.append(item)
        print(f"checked out {item.name}")

    def do_checkout(self, _: str) -> None:
        if self.selected_item:
            self._checkout(self.selected_item)
        else:
            self.mode = CliMode.CHECKOUT

    def do_add(self, _: str) -> None:
        if self.selected_item:
            self.mode = CliMode.ADD
        else:
            print("Select an item first")

    def do_exit(self, _: str) -> bool:
        if self.mode != CliMode.DEFAULT:
            self.mode = CliMode.DEFAULT
        elif self.selected_item:
            self.selected_item = None
        else:
            return True
        return False


if __name__ == "__main__":
    load_dotenv()
    INVENTORY_FILE = Path(os.environ["INVENTORY_FILE"])

    InventoryCli(INVENTORY_FILE).cmdloop()
