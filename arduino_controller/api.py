import logging
import os
import time

from json_dict import JsonDict
from websocket_communication_server.messagetemplates import commandmessage, datapointmessage
from websocket_communication_server.socketclient import WebSocketClient


class ArduinoControllerAPI():
    def __init__(self, name="arduinocontrollerapi", sockethost=8888,basedir=os.getcwd()):
        self.basedir = basedir
        self.name = name
        self.data = {}
        self.dataupdate = 1
        self.lastupdate = 0

        self.logger = logging.getLogger(self.name)
        self.ws = WebSocketClient(
            logger=self.logger, name=self.name, host=sockethost
        )
        self.config = JsonDict(
            file=os.path.join(basedir, "config.json"), createfile=True
        )
        self.config.autosave = True

        self.sensor_ports = set([])

        self.ws.add_cmd_function("set_ports", self.set_ports)
        self.ws.add_cmd_function("add_sensor_port", self.add_sensor_port)
        self.ws.add_cmd_function("get_data", self.get_data)
        self.ws.add_message_type("data", self.data_validator)
        self.ws.add_cmd_function("boardupdate", self.boardupdate)

    def set_ports(self, connected_ports=None):
        if connected_ports is None:
            connected_ports = []
        for port in connected_ports:
            if port not in self.sensor_ports:
                self.add_sensor_port(port)

    def add_sensor_port(self, port=None):
        if port is not None:
            self.sensor_ports.add(port)
            self.ws.write_to_socket(
                commandmessage(
                    cmd="add_data_target",
                    sender=self.name,
                    target=port,
                    data_target=self.name,
                )
            )
            self.ws.write_to_socket(
                commandmessage(
                    cmd="remove_data_target",
                    sender=self.name,
                    target=port,
                    data_target="gui",
                )
            )

    def data_validator(self, message):
        if not message["data"]["key"] in self.data:
            self.data[message["data"]["key"]] = []
        self.data[message["data"]["key"]].append([message["data"]["x"], message["data"]["y"], message["data"]["t"]])

        t = time.time()
        if t - self.lastupdate > self.dataupdate:
            self.lastupdate = t
            for key, dates in self.data.items():
                self.ws.write_to_socket(
                    datapointmessage(
                        sender=self.name,
                        x=dates[-1][0],
                        y=dates[-1][1],
                        key=key,
                        target="gui",
                        t=dates[-1][2],
                        as_string=True,
                    )
                )
            return True
        return False

    def get_data(self, data_target=None, timestep=None):
        if data_target is None: return
        self.ws.write_to_socket(
            commandmessage(
                sender=self.name,
                cmd="set_data",
                target=data_target,
                as_string=True,
                data=self.data,
            )
        )

    def boardupdate(self, boarddata=None):
        if boarddata is None:
            return

    def ask_for_ports(self):
        self.ws.write_to_socket(
            commandmessage(
                cmd="get_ports",
                sender=self.name,
                target="serialreader",
                data_target=self.name,
            )
        )

    def start(self):
        while 1:
            self.ask_for_ports()
            time.sleep(3)

