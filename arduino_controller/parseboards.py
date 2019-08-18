import sys

import glob
import importlib.util
import inspect
import os
from os.path import basename


BOARDS = {}


def board_by_firmware(firmware):
    return BOARDS.get(firmware, None)


def parse_path_for_boards(path, prefix=""):
    global BOARDS
    dir_path = path

    boardsfolders = [
        p
        for p in glob.glob(dir_path + "/*")
        if os.path.isdir(p) and not p.endswith("__")
    ]
    loaded_firmwares = set()
    prefix = prefix + os.path.basename(path) + "."
    for boardfolder in boardsfolders:
        boardpy = os.path.join(boardfolder, "board.py")
        if os.path.exists(boardpy):
            spec = importlib.util.spec_from_file_location(
                "board." + prefix + basename(boardfolder),
                os.path.join(boardfolder, "board.py"),
            )
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)
            for name, obj in inspect.getmembers(foo):
                if inspect.isclass(obj):
                    try:
                        fw = getattr(obj, "FIRMWARE")
                        if fw not in loaded_firmwares:
                            BOARDS[fw] = {
                                "firmware": fw,
                                "classcaller": obj,
                                "name": name,
                            }
                            loaded_firmwares.add(fw)
                    except:
                        pass
        else:
            parse_path_for_boards(boardfolder, prefix=prefix)
    # print(path)
    # print(BOARDS)


def add_board(board_class):
    global BOARDS
    if board_class.FIRMWARE not in BOARDS:
        BOARDS[board_class.FIRMWARE] = {
            "firmware": board_class.FIRMWARE,
            "classcaller": board_class,
            "name": board_class.CLASSNAME,
        }
