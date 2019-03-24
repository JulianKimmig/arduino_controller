import time

import logging
import serial
import threading
from json_dict.json_dict import JsonDict
from websocket_communication_server.messagetemplates import commandmessage, levelmessage, datapointmessage
from websocket_communication_server.socketclient import WebSocketClient
from websocket_communication_server.socketserver import connect_to_first_free_port

from arduino_controller.parseboards import board_by_firmware
from arduino_controller.portrequest import validate_buffer
from arduino_controller.serialdetector import get_avalable_serial_ports
from basicboard.board import ArduinoBasicBoard

AUTOCHECKPORTS=True
PORTCHECKTIME = 4
PORTREADTIME = 0.01
connected_ports = set()
ignored_port = set()
permanently_ignored_port = set()
deadports = set()
BAUDRATES = (
    9600,
    115200,
    #   19200,
    #   38400,
    #   57600,
    #    230400,
    #    460800,
    #    500000,
    #    576000,
    #    921600,
    #    1000000,
    #    1152000,
    #    1500000,
    #    2000000,
    #    2500000,
    #    3000000,
    #    3500000,
    #    4000000,
)


class SerialPort(serial.Serial):
    def __init__(self, config, port, baudrate=9600, host="ws://127.0.0.1:8888", **kwargs):
        self.data_targets = {"gui"}
        self.logger = logging.getLogger("serialreader " + port)

        self.board: ArduinoBasicBoard = None
        self.workthread = None
        self.updatethread = None
        self.readbuffer = []
        self.config = config

        try:
            super().__init__(port, baudrate=baudrate, timeout=0, **kwargs)
        except Exception as e:
            deadports.add(port)
            self.logger.exception(e)
            return
        self.logger.info("port found " + self.port)
        connected_ports.add(self)
        self.ws = WebSocketClient(name=port,logger=self.logger,host=host)
        self.ws.add_cmd_function("update",self.update)

        def add_data_target(data_target=None):
            if data_target is not None:
                self.data_targets.add(data_target)
        self.ws.add_cmd_function("add_data_target",add_data_target)

        def remove_data_target(data_target):
            if data_target in self.data_targets:
                self.data_targets.remove(data_target)
        self.ws.add_cmd_function("remove_data_target",remove_data_target)

        self.to_write = []
        self.start_read()

        newb = board_by_firmware(config.get("portdata", self.port, "fw", default=0))
        if newb is not None:
            self.set_board(newb["classcaller"])
        else:
            self.set_board(ArduinoBasicBoard)

    def data_to_socket(self, key, y, x=None):
        t = time.time() - self.ws.time
        if x is None:
            x = t
        self.ws.write_to_socket(
            datapointmessage(
                sender=self.port, key=key, x=x, y=y, t=t, target=list(self.data_targets)
            )
        )

    def add_data_target(self,target=None):
        if target is not None:
            self.data_targets.add(target)

    def set_board(self, BoardClass):
        self.board = BoardClass()
        self.board.set_serial_port(self)
        self.board.identify()

        if not self.board.identified:
            self.stop_read()
            ignored_port.add(self.port)
            raise ValueError("unable to identify " + self.port)

        if self.board.FIRMWARE != self.board.fw:
            newb = board_by_firmware(self.board.fw)
            if newb is not None:
                return self.set_board(newb["classcaller"])
            else:
                raise ValueError("firmware not found " + str(self.board.fw))

        self.board.specific_identification()
        if not self.board.identified:
            self.stop_read()
            ignored_port.add(self.port)
            raise ValueError(
                "unable to specificidentify "
                + self.port
                + "with fw:"
                + str(self.board.fw)
            )

        self.logger.info(str(self.port) + " identified ")

        self.config.put("portdata", self.port, "baud", value=self.baudrate)
        self.config.put("portdata", self.port, "fw", value=self.board.fw)
        self.board.restore(self.config.get("boarddata", self.board.id, default={}))
        self.board.get_portcommand_by_name("identify").sendfunction(True)
        return True

    def board_updater(self):
        while self.is_open:
            if self.board is not None:
                self.send_board_data()
                time.sleep(self.board.updatetime)

    def send_board_data(self, **kwargs):
        if self.board is not None:
            if self.board.identified:
                data = self.board.save()
                self.config.put("boarddata", self.board.id, value=data)
                msg = commandmessage(
                    target=list(self.data_targets),
                    cmd="boardupdate",
                    boarddata=data,
                    sender=str(self.port),
                    **kwargs,
                )
                self.logger.info(msg)
                self.ws.write_to_socket(msg)

    def work_port(self):
        while self.is_open:
            try:
                while len(self.to_write) > 0:
                    t = self.to_write.pop()
                    self.logger.debug("write to " + self.port + ": " + str(t))
                    super().write(t)
                c = self.read()

                while len(c) > 0:
                    self.readbuffer.append(c)
                    validate_buffer(self)
                    c = self.read()
            except Exception as e:
                self.logger.exception(e)
                break
            time.sleep(PORTREADTIME)
        self.logger.error("work_port stopped")
        self.stop_read()

    def start_read(self):
        self.logger.info("port opened " + self.port)
        self.ws.write_to_socket(
            levelmessage(
                sender=self.port, content="port opened", title=None, target=["gui"]
            )
        )

        if not self.is_open:
            self.open()
        self.workthread = threading.Thread(target=self.work_port)
        self.updatethread = threading.Thread(target=self.board_updater)
        self.workthread.start()
        self.updatethread.start()

    def write(self, data):
        self.to_write.append(data)

    def stop_read(self):
        self.close()
        try:
            self.workthread.join()
        except:
            pass
        self.workthread = None
        try:
            self.updatethread.join()
        except:
            pass
        self.close()
        self.updatethread = None
        if self in connected_ports:
            connected_ports.remove(self)
        self.logger.info("port closed " + self.port)
        self.ws.write_to_socket(
            levelmessage(
                sender=self.port,
                content="port closed",
                title=None,
                level="error",
                target=["gui"],
            )
        )
        self.ws.close()
        del self


    def update(self,**kwargs):
        if self.board is not None:
            if self.board.id is not None:
                self.board.restore(**kwargs)
                self.send_board_data(force_update=True)


def run(config, **kwargs):
    logger = logging.getLogger("serialreader")
    def open_port(port):
        global available_ports, ignored_port, permanently_ignored_port
        try:
            available_ports.remove(port)
        except:
            pass
        try:
            ignored_port.remove(port)
        except:
            pass
        try:
            permanently_ignored_port.remove(port)
        except:
            pass
        t = threading.Thread(
            target=SerialPort,
            kwargs={
                **{
                    "config": config,
                    "port": port,
                    "baudrate": config.get("portdata", port, "baud", default=115200),
                },
                **kwargs,
            },
        )
        t.start()

    def sendports(data_target="gui"):
        ws.write_to_socket(
            commandmessage(
                cmd="set_ports",
                sender="serialreader",
                target=data_target,
                available_ports=list(available_ports),
                ignored_port=list(ignored_port | permanently_ignored_port),
                connected_ports=[sp.port for sp in connected_ports],
            )
        )

    def close_port(port, permanently=True):
        global permanently_ignored_port
        for p in connected_ports.copy():
            if p.port == port:
                if permanently:
                    permanently_ignored_port.add(p.port)
                p.stop_read()
        sendports()

    def set_autocheckport(autocheckport=True):
        global AUTOCHECKPORTS
        AUTOCHECKPORTS = autocheckport

    ws = WebSocketClient( name="serialreader",logger=logger,host=kwargs.get("host", "ws://127.0.0.1:8888"))
    ws.add_cmd_function("set_autocheckport",set_autocheckport)
    ws.add_cmd_function("close_port",close_port)
    ws.add_cmd_function("open_port",open_port)
    ws.add_cmd_function("get_ports",sendports)

    while 1:
        if AUTOCHECKPORTS:
            global ignored_port, deadports
            available_ports, ignored_port = get_avalable_serial_ports(
                ignore=ignored_port | permanently_ignored_port
            )
            deadports = available_ports.intersection(deadports)
            newports = available_ports - (
                    ignored_port | deadports | permanently_ignored_port
            )
            logger.debug(
                "available Ports: "
                + str(available_ports)
                + "; new Ports: "
                + str(newports)
                + "; ignored Ports: "
                + str(ignored_port | permanently_ignored_port)
            )
            sendports()
            for port in newports.copy():
                try:
                    open_port(port)
                except:
                    pass
        time.sleep(PORTCHECKTIME)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    serialportconfig = JsonDict("portdata.json")
    serialportconfig.autosave = True

    socketserver = connect_to_first_free_port()
    threading.Thread(
        target=socketserver.run_forever
    ).start()  # runs server forever in background
    time.sleep(1)
    run(config=serialportconfig,host=socketserver.ws_adress)
