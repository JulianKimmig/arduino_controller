
from ..arduino_variable import arduio_variable


class ArduinoData():

    def __init__(self,board_instance):
        self.board_instance = board_instance

    def definitions(self):
        return {}

    def global_vars(self):
        return {}

    def includes(self):
        return []

    def functions(self):
        return {}

    def setup(self):
        return

    def loop(self):
        return

    def dataloop(self):
        return

    def create(self):
        return {
            "definitions": self.definitions(),
            "global_vars": self.global_vars(),
            "includes": self.includes(),
            "functions": self.functions(),
            "setup": self.setup(),
            "loop": self.loop(),
            "dataloop": self.dataloop(),
        }
