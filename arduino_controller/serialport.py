import logging
import threading
import time

import serial

import filter_dict
from arduino_controller.serialreader.serialreader import DATAPOINT_RESOLUTION
from .parseboards import board_by_firmware
from .basicboard.board import BasicBoard
from .portrequest import validate_buffer

PORT_READ_TIME = 0.01
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
    #    4000000,
)


class PortIdentifyError(Exception):
    pass


class FirmwareNotFoundError(Exception):
    pass


class SerialPortDataTarget:
    def __init__(self):
        pass

    def port_data_point(self, key, x, y, port, board):
        pass

    def port_identified(self, port):
        pass

    def board_update(self, board_data):
        pass

    def port_opened(self, port, baud):
        pass

    def port_closed(self, port):
        pass

    def set_board(self, port, board):
        pass


class SerialPort(serial.Serial):
    def __init__(
        self, serial_reader, port, config=None, logger=None, baudrate=9600, **kwargs
    ):

        self.serial_reader = serial_reader
        self.data_targets = set([])
        self.datapoint_resolution = DATAPOINT_RESOLUTION
        if logger is None:
            logger = logging.getLogger("serial_reader " + port)
        self.logger = logger

        self.board = None
        self.work_thread = None
        self.update_thread = None
        self.read_buffer = []
        self.time = time.time()

        if config is None:
            config = serial_reader.config
        self.config = config

        try:
            super().__init__(port, baudrate=baudrate, timeout=0, **kwargs)
        except Exception as e:
            serial_reader.deadports.add(port)
            self.logger.exception(e)
            return
        self.logger.info("port found " + self.port)
        serial_reader.connected_ports.add(self)

        self.to_write = []
        self.start_read()

        newb = board_by_firmware(
            config.get("portdata", self.port, "firmware", default=0)
        )
        if newb is not None:
            self.set_board(newb["classcaller"])
        else:
            self.set_board(BasicBoard)

    def add_data_target(self, data_target=None):
        if data_target is not None:
            self.data_targets.add(data_target)

    def remove_data_target(self, data_target):
        if data_target in self.data_targets:
            self.data_targets.remove(data_target)

    def board_function(self, board_cmd, **kwargs):
        # try:
        getattr(self.board, board_cmd)(**kwargs)

    # except A:
    #    self.logger.exception(Exception)

    def set_board_attribute(self, attribute, value):
        try:
            setattr(self.board, attribute, value)
        except:
            self.logger.exception(Exception)

    def add_data_point(self, board, key, y, x=None):

        t = (
            int(1000 * (time.time() - self.time) / self.datapoint_resolution)
            * self.datapoint_resolution
        )
        if x is None:
            x = t
            try:
                for data_target in self.data_targets:
                    filter_dict.call_method(
                        target=data_target.port_data_point,
                        kwargs=dict(key=key, x=x, y=y, port=board.port, board=board.id),
                    )
            except RuntimeError:pass

    def set_board(self, board_class):
        self.board = board_class()
        self.board.set_serial_port(self)
        time.sleep(2)
        self.board.identify()

        if not self.board.identified:
            self.stop_read()
            self.serial_reader.ignored_ports.add(self.port)
            self.logger.error("unable to identify " + self.port)
            raise PortIdentifyError()

        if self.board.FIRMWARE != self.board.firmware:
            self.logger.warning("firmware detected  {}".format(self.board.firmware))
            newb = board_by_firmware(self.board.firmware)
            if newb is not None:
                return self.set_board(newb["classcaller"])
            else:
                self.stop_read()
                self.serial_reader.ignored_ports.add(self.port)
                self.logger.error("firmware not found " + str(self.board.firmware))
                raise FirmwareNotFoundError()

        # self.board.specific_identification()
        if not self.board.identified:
            self.stop_read()
            self.serial_reader.ignored_ports.add(self.port)
            raise ValueError(
                "unable to specificidentify "
                + self.port
                + "with firmware:"
                + str(self.board.firmware)
            )

        self.logger.info(str(self.port) + " identified ")

        self.serial_reader.identified_ports.add(self)

        self.config.put("portdata", self.port, "baud", value=self.baudrate)
        self.config.put("portdata", self.port, "firmware", value=self.board.firmware)
        self.board.restore(self.config.get("board_data", self.board.id, default={}))
        self.board.get_portcommand_by_name("identify").sendfunction(True)

        for data_target in self.serial_reader.data_targets:
            filter_dict.call_method(
                data_target.port_identified, kwargs={"port": self.port}
            )
        return True

    def board_updater(self):
        while self.is_open:
            if self.board is not None:
                self.send_board_data()
                time.sleep(self.board.update_time)

    def send_board_data(self, **kwargs):
        if self.board is not None:
            if self.board.identified:
                data = self.board.save()
                self.config.put("board_data", self.board.id, value=data)
                data["firmware"] = self.board.firmware
                data["id"] = self.board.id
                data["class"] = self.board.CLASSNAME
                msg_d = dict(board_data=data, **kwargs)

                for data_target in self.data_targets:
                    filter_dict.call_method(data_target.board_update, kwargs=msg_d)
                self.logger.debug(msg_d)

    def work_port(self):
        while self.is_open:
            try:
                while len(self.to_write) > 0:
                    t = self.to_write.pop()
                    self.logger.debug("write to " + self.port + ": " + str(t))
                    super().write(t)
                if self.is_open:
                    c = self.read()

                    while len(c) > 0:
                        # print(ord(c),c)
                        self.read_buffer.append(c)
                        validate_buffer(self)
                        if not self.is_open:
                            break
                        c = self.read()
            # except serial.serialutil.SerialException as e:
            #    self.logger.exception(e)
            # except AttributeError:
            #    break
            except Exception as e:
                self.logger.exception(e)
                break
            time.sleep(PORT_READ_TIME)
            # print(self.is_open)
        self.logger.error("work_port stopped")
        self.stop_read()

    def start_read(self):
        self.logger.info("port opened " + self.port)
        for data_target in self.serial_reader.data_targets:
            filter_dict.call_method(
                data_target.port_opened,
                kwargs={"port": self.port, "baud": self.baudrate},
            )

        if not self.is_open:
            self.open()
        self.work_thread = threading.Thread(target=self.work_port)
        self.update_thread = threading.Thread(target=self.board_updater)
        self.work_thread.start()
        self.update_thread.start()

    def write(self, data):
        self.to_write.append(data)

    def stop_read(self):
        self.close()
        try:
            self.work_thread.join()
        except (RuntimeError, AttributeError):
            pass
        self.work_thread = None
        try:
            self.update_thread.join()
        except (RuntimeError, AttributeError):
            pass
        self.close()
        self.update_thread = None
        self.logger.info("port closed " + self.port)
        for data_target in self.serial_reader.data_targets:
            filter_dict.call_method(data_target.port_closed, kwargs={"port": self.port})

        if self in self.serial_reader.connected_ports:
            self.serial_reader.connected_ports.remove(self)
        if self in self.serial_reader.identified_ports:
            self.serial_reader.identified_ports.remove(self)
        del self

    # def update(self, **kwargs):
    #    if self.board is not None:
    #        if self.board.id is not None:
    #            self.board.restore(**kwargs)
    #           self.send_board_data(force_update=True)

    def get_board(self, data_target=None):
        if data_target is None:
            return
        board = self.board.get_board()
        filter_dict.call_method(
            data_target.set_board, kwargs={"port": self.port, "board": board}
        )


def open_serial_port(**kwargs):
    try:
        return SerialPort(**kwargs)
    except (PortIdentifyError, FirmwareNotFoundError):
        return None
