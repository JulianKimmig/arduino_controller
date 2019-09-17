import logging
import os
import threading
import time

import filter_dict
from json_dict import JsonDict
from ..serialreader import serialdetector

AUTO_CHECK_PORTS = True
PORT_CHECK_TIME = 2
DATAPOINT_RESOLUTION = 200


class SerialReaderDataTarget:
    def __init__(self):
        pass

    def set_ports(
        self, available_ports, ignored_ports, connected_ports, identified_ports
    ):
        pass

    def port_identified(self, port):
        pass

    def port_opened(self, port, baud):
        pass

    def port_closed(self, port):
        pass


class SerialReader:
    def __init__(
        self,
        auto_check_ports=AUTO_CHECK_PORTS,
        port_check_time=PORT_CHECK_TIME,
        start_in_background=False,
        config: JsonDict = None,
        logger=None,
        permanently_ignored_ports=None,
        # datalogger: DataLogger = None,
    ):
        self.data_targets = set()

        self.ignored_ports = set()
        self.dead_ports = set()
        self.connected_ports = set()
        self.available_ports = set()
        self.identified_ports = set()
        self.running = False
        self.read_thread = None
        # self.datalogger = DataLogger() if datalogger is None else datalogger

        self.config = (
            JsonDict(
                os.path.join(
                    os.path.expanduser("~"), ".arduino_controller", "portdata.json"
                )
            )
            if config is None
            else config
        )

        if permanently_ignored_ports is None:
            permanently_ignored_ports = []

        self.port_check_time = port_check_time
        self.auto_check_ports = auto_check_ports
        self.permanently_ignored_ports = set(permanently_ignored_ports)

        # self.set_communicator(python_communicator.PythonCommunicator() if communicator is None else communicator)

        self.logger = logging.getLogger("SerialReader") if logger is None else logger

        if start_in_background:
            self.run_in_background()

    def get_identified_by_port(self, port):
        for sp in self.identified_ports:
            if sp.port == port:
                return sp
        return None

    def run_in_background(self):
        if self.read_thread is not None:
            self.stop()
        self.read_thread = threading.Thread(target=self.read_forever,)
        self.read_thread.start()

    def __del__(self):
        self.stop()

    def reactivate_port(self, port=None):
        if port is None:
            return
        try:
            self.ignored_ports.remove(port)
        except:
            pass
        try:
            self.permanently_ignored_ports.remove(port)
        except:
            pass
        try:
            self.dead_ports.remove(port)
        except:
            pass

    def deactivate_port(self, port=None):
        if port is None:
            return
        self.ignored_ports.add(port)
        self._communicator.cmd_out(targets=[port], cmd="stop_read")

    # def set_communicator(self, communicator: python_communicator.PythonCommunicator):
    #     self._communicator = communicator
    #     self._communicator.add_node("serialreader", self)

    # def get_communicator(self):
    #    return self._communicator

    # communicator = property(get_communicator, set_communicator)

    def add_data_target(self, data_target=None):
        if data_target is not None:
            self.data_targets.add(data_target)

    def remove_data_target(self, data_target):
        if data_target in self.data_targets:
            self.data_targets.remove(data_target)

    def send_ports(self, data_target=None):
        if data_target is None:
            data_target = self.data_targets

        if not isinstance(data_target, set):
            data_target = set(data_target)

        for data_target in data_target:
            filter_dict.call_method(
                target=data_target.set_ports,
                kwargs=dict(
                    available_ports=list(self.available_ports),
                    ignored_ports=list(
                        self.ignored_ports | self.permanently_ignored_ports
                    ),
                    connected_ports=[
                        dict(port=sp.port, baudrate=sp.baudrate)
                        for sp in self.connected_ports
                    ],
                    identified_ports=[
                        dict(port=sp.port, baudrate=sp.baudrate)
                        for sp in self.identified_ports
                    ],
                ),
            )

    get_ports = send_ports

    def stop(self):
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=2*self.port_check_time)
            self.read_thread = None
        for port in self.connected_ports.union(self.identified_ports):
            port.stop_read()

    def read_forever(self):
        self.running = True
        while self.running:
            if self.auto_check_ports:
                self.available_ports, self.ignored_ports = serialdetector.get_avalable_serial_ports(
                    ignore=self.ignored_ports
                    | self.permanently_ignored_ports  # | set(
                    # [sp.port for sp in self.connected_ports])
                )
                self.dead_ports = self.available_ports.intersection(self.dead_ports)
                newports = self.available_ports - (
                    self.ignored_ports
                    | self.dead_ports
                    | self.permanently_ignored_ports
                )
                self.logger.debug(
                    "available Ports: "
                    + str(self.available_ports)
                    + "; new Ports: "
                    + str(newports)
                    + "; ignored Ports: "
                    + str(self.ignored_ports | self.permanently_ignored_ports)
                    + "; connected Ports: "
                    + str([sp.port for sp in self.connected_ports])
                    + "; identified Ports: "
                    + str([sp.port for sp in self.identified_ports])
                )

                self.send_ports()
                for port in newports.copy():
                    try:
                        self.open_port(port)
                    except Exception as e:
                        self.logger.exception(e)
                        pass
            time.sleep(self.port_check_time)

    def get_port(self, port):
        for sp in self.identified_ports:
            if sp.port == port:
                return sp
        for sp in self.connected_ports:
            if sp.port == port:
                return sp
        return None

    def open_port(self, port):
        self.reactivate_port(port)

        from ..serialport import open_serial_port

        t = threading.Thread(
            target=open_serial_port,
            kwargs={
                **{
                    "serial_reader": self,
                    "config": self.config,
                    "port": port,
                    "baudrate": self.config.get("portdata", port, "baud", default=9600),
                }
            },

        )
        t.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sr = SerialReader()
    sr.read_forever()
