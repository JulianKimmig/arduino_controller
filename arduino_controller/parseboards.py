import glob
import importlib.util
import inspect
import os
from os.path import basename

BOARDS = {}

BOARD_SOURCES = []


class BoardSource:
    def __init__(self, prefix=""):
        self.prefix = prefix

    def board_by_firmware(self, firmware):
        pass


class PathBoardSource(BoardSource):
    def __init__(self, path, prefix=""):
        super().__init__(prefix)
        self.path = path

    def board_by_firmware(self, firmware):
        self._find_boards()
        return BOARDS.get(firmware, None)

    def _find_boards(self, path=None, prefix=None):
        if path is None:
            path = self.path
        if prefix is None:
            prefix = self.prefix

        boardsfolders = [
            p
            for p in glob.glob(path + "/*")
            if os.path.isdir(p) and not p.endswith("__")
        ]
        prefix = prefix + os.path.basename(path) + "."
        for boardfolder in boardsfolders:
            boardpy = os.path.join(boardfolder, "board.py")
            if os.path.exists(boardpy):
                spec = importlib.util.spec_from_file_location(
                    "_board." + prefix + basename(boardfolder),
                    os.path.join(boardfolder, "board.py"),
                )
                foo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(foo)
                for name, obj in inspect.getmembers(foo):
                    if inspect.isclass(obj):
                        try:
                            fw = getattr(obj, "FIRMWARE")
                            add_board(obj)
                        except:
                            pass
            else:
                self._find_boards(boardfolder, prefix)


class WebBoardSource(PathBoardSource):
    def __init__(self, download_path, by_firmware_request, prefix="downloaded"):
        super().__init__(path=download_path, prefix=prefix)
        self.by_firmware_request = by_firmware_request

    def board_by_firmware(self, firmware):
        # webrequest
        import zipfile
        import requests
        import io

        response = requests.get(
            self.by_firmware_request.format(firmware), allow_redirects=True
        )
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(self.path)
        super().board_by_firmware(firmware)


def board_by_firmware(firmware):
    board = BOARDS.get(firmware, None)
    for source in BOARD_SOURCES:
        board = source.board_by_firmware(firmware)
        if board is not None:
            return board
    return board


def parse_path_for_boards(path, prefix=""):
    global BOARD_SOURCES
    BOARD_SOURCES.append(PathBoardSource(path, prefix=prefix))


def add_board(board_class):
    global BOARDS
    if board_class.FIRMWARE not in BOARDS:
        BOARDS[board_class.FIRMWARE] = {
            "firmware": board_class.FIRMWARE,
            "classcaller": board_class,
            "name": board_class.CLASSNAME,
        }
