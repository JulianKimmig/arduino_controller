import time

from typing import Set, Any

import json
import os

import logging
import threading

import filter_dict
from arduino_controller.serialport import SerialPortDataTarget

from arduino_controller.serialreader.serialreader import SerialReaderDataTarget

from arduino_controller import parseboards
from json_dict import JsonDict


def api_function(visible=True, **kwargs):
    def func_wrap(func):
        def api_func_warper(*args,api_function_blocking=False, **kwargs):
            if not api_function_blocking:
                threading.Thread(target=func, args=args, kwargs=kwargs).start()
            else:
                return func(*args,**kwargs)

        api_func_warper.api_function = True
        api_func_warper.visible = visible
        for n, t in kwargs.items():
            setattr(api_func_warper, n, t)
        return api_func_warper

    return func_wrap


class BoardApi(SerialReaderDataTarget, SerialPortDataTarget):
    required_boards = []

    def __init__(self, serial_reader=None, config=None):
        """
        :type serial_reader: SerialReader
        """
        super().__init__()
        self._ws_targets = set()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("start API {}".format(self.__class__.__name__))
        self._serial_reader = None
        self.config = (
            JsonDict(
                os.path.join(
                    os.path.expanduser("~"),
                    ".{}".format(self.__class__.__name__),
                    "portdata.json",
                )
            )
            if config is None
            else config
        )
        self.possible_boards = [[] for board in self.required_boards]
        if (
            self.config.get("api_name", default=self.__class__.__name__)
            != self.__class__.__name__
        ):
            self.config.data = {}
            self.config.put("api_name", value=self.__class__.__name__)
            self.config.put(
                "linked_boards", value=[None for board in self.required_boards]
            )

        self.linked_boards = [None for board in self.required_boards]
        if len(self.config.get("linked_boards", default=self.linked_boards)) != len(
            self.linked_boards
        ):
            self.config.put(
                "linked_boards", value=[None for board in self.required_boards]
            )

        for board in self.required_boards:
            parseboards.add_board(board)
        self.serial_reader = serial_reader

    def __str__(self):
        return self.__class__.__name__

    def get_serial_reader(self):
        return self._serial_reader

    def set_serial_reader(self, serial_reader):
        """
        :type serial_reader: SerialReader
        """
        if self._serial_reader is not None:
            self._serial_reader.remove_data_target(self)
        if serial_reader is not None:
            serial_reader.add_data_target(self)

        self._serial_reader = serial_reader

    serial_reader = property(get_serial_reader, set_serial_reader)

    def set_ports(
        self, available_ports, ignored_ports, connected_ports, identified_ports
    ):
        proposed_linked_boards = [int(b) for b in self.config.get(
            "linked_boards", default=self.linked_boards,
        )]

        identified_ports = [
            self.serial_reader.get_port(identified_port["port"])
            for identified_port in identified_ports
        ]
        change = False
        for identified_port in identified_ports:
            board = identified_port.board
            # skip if alreay linked
            if board in self.linked_boards:
                continue
            # link all already proposed  boards
            for i in range(len(proposed_linked_boards)):
                if self.linked_boards[i] is not None:
                    continue
                print(proposed_linked_boards,board.id)
                if proposed_linked_boards[i] == board.id:
                    self.link_board(i, board)
                    change = True
            # link to free boards
            for i in range(len(self.required_boards)):
                if board.__class__ == self.required_boards[i]:
                    if board not in self.possible_boards[i]:
                        self.possible_boards[i].append(board)
                        change = True
                    # if already linked skip
                    if self.linked_boards[i] is not None:
                        continue
                    # if already reserved for another board
                    if proposed_linked_boards[i] is not None:
                        continue
                    # if matching board
                    self.link_board(i, board)
                    change = True

        # unlink unavailable ports
        for i in range(len(self.linked_boards)):
            if self.linked_boards[i] is not None:
                if self.linked_boards[i].serial_port not in identified_ports:
                    self.unlink_board(i)
                    change = True
        if change:
            for target in self._ws_targets:
                target.send_boards(self)

    def link_possible_board(self,index,possible_index):
        try:
            print(self.possible_boards)
            print(index,possible_index)
            self.link_board(index,self.possible_boards[index][possible_index])
        except Exception as e:
            self.logger.exception(e)

    def link_board(self, i, board):
        """
        :param i: int
        :type board: ArduinoBoard
        """
        assert board.__class__ == self.required_boards[i], "the board you try o link({}) is not of the required type ({})".format(board,self.required_boards[i])
        if board is None:
            return self.unlink_board(i)
        linked_boards = self.config.get("linked_boards", default=self.linked_boards)
        linked_boards[i] = board.id
        self.linked_boards[i] = board
        self.logger.info(
            "link board {}({}) to index {}".format(
                board.id, board.__class__.__name__, i
            )
        )
        self.config.put("linked_boards", value=linked_boards)

    def unlink_board(self, i):
        linked_boards = self.config.get("linked_boards", default=self.linked_boards)
        board = self.linked_boards[i]
        if board is None:
            return
        linked_boards[i] = None
        self.linked_boards[i] = None
        self.logger.info("unlink board from index {}".format(i))
        self.config.put("linked_boards", value=linked_boards)

        # remove from board possibilities
        for i in range(len(self.possible_boards)):
            if board in self.possible_boards[i]:
                self.possible_boards[i].remove(board)

    def get_possibilities_index(self, i):
        return self.possible_boards[i]

    def get_possibilities_board_class(self, board_class):
        for i in range(len(self.required_boards)):
            if board_class == self.required_boards[i]:
                return self.get_possibilities_index(i)
        return []

    def get_possibilities_board(self, board):
        return self.get_possibilities_board_class(board.__class__)

    get_board_alternatives = get_possibilities_board

    def add_ws_target(self, receiver):
        self._ws_targets.add(receiver)

    def remove_ws_target(self, receiver):
        if receiver in self._ws_targets:
            self._ws_targets.remove(receiver)

    def get_boards(self):
        return dict(
            required_boards=[b.__name__ for b in self.required_boards],
            possible_boards=self.possible_boards,
            linked_boards=self.linked_boards,
        )

    def get_status(self):
        status = True
        print("a",self.linked_boards)
        if None in self.linked_boards:
            return dict(status=False, reason="not all boards linked")
        return dict(status=True)

    def get_functions(self):
        functions = {}
        for method in dir(self):
            try:
                m = getattr(self, method)
                if m.api_function:
                    functions[method] = m.__dict__
            except AttributeError:
                pass
        return functions


class ArduinoAPIWebsocketConsumer:
    apis = list()
    active_consumer = None
    logger = logging.getLogger("ArduinoAPIWebsocketConsumer")
    reset_time = 3
    accepting = True
    @classmethod
    def register_api(cls, api):
        """
        :type api: BoardApi
        """
        if api not in cls.apis:
            cls.apis.append(api)
            if cls.active_consumer is not None:
                if api not in cls.active_consumer.apis:
                    cls.active_consumer.apis.append(api)
                api.add_ws_target(cls.active_consumer)
                cls.active_consumer.to_client(
                    dict(cmd="set_apis", data=cls.active_consumer.get_apis()), type="cmd"
                )

    @classmethod
    def register_at_apis(cls, receiver):
        if not cls.accepting: return False
        cls.accepting = False
        if cls.active_consumer is not None:
            t= time.time()
            cls.active_consumer.status = False
            while cls.active_consumer.status is False and time.time()-t<cls.reset_time:
                cls.active_consumer.to_client(dict(cmd="get_status"),type="cmd")
                time.sleep(0.5)
            if cls.active_consumer.status is False:
                cls.active_consumer.to_client(data=dict(cmd="error",message="client did not respond"), type="cmd")
                cls.active_consumer.close_api_reciever()
                cls.active_consumer = None
            cls.accepting = True
            return False
        else:
            cls.active_consumer = receiver
            for api in cls.apis:
                api.add_ws_target(receiver)
            cls.accepting = True
            return True

    @classmethod
    def unregister_at_apis(cls, receiver):
        try:
            cls.instances.remove(receiver)
        except:
            pass
        for api in cls.apis:
            api.remove_ws_target(receiver)

    def client_to_api(self, textdata):
        data = json.loads(textdata)
        try:
            if data["type"] == "cmd":
                self.parse_command(data["data"])
            else:
                raise ValueError("invalid type: {} ".format(data["type"]))
        except Exception as e:
            self.logger.exception(e)

    def parse_command(self, data):
        if hasattr(self, data["cmd"]) and not "api" in data["data"]:
            answer = filter_dict.call_method(
                getattr(self, data["cmd"]), kwargs=data["data"]
            )
        else:
            api = data["data"]["api"]
            del data["data"]["api"]
            answer = filter_dict.call_method(
                getattr(self.apis[api], data["cmd"]), kwargs=data["data"]
            )
            if answer is not None:
                if not isinstance(answer, dict):
                    answer = {"data": answer}
                answer["api_position"] = api
        if answer is not None:
            self.to_client(
                dict(cmd=data["cmd"].replace("get_", "set_"), data=answer), type="cmd"
            )

    def get_apis(self):
        return self.apis

    def send_boards(self, api):
        data = api.get_boards()
        data["api_position"] = self.apis.index(api)
        self.to_client(dict(cmd="set_boards", data=data), type="cmd")

    def to_client(self, data=None, type=None):
        raise AttributeError("no valid to_client function implemented")

    def get_status(self):
        return [self.apis[i].get_status() for i in range(len(self.apis))]

    def broadcast_status(self):
        try:
            self.to_client(dict(cmd="set_status", data=self.get_status()), type="cmd")
        except:
            pass

    def broadcast(self):
        while self.broadcasting:
            self.broadcast_status()
            time.sleep(3)

    def close_api_reciever(self):
        self.broadcasting = False
        self.unregister_at_apis(self)

    def start_broadcast(self):
        self.broadcasting = True
        threading.Thread(target=self.broadcast).start()
