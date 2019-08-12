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


class BoardApi(SerialReaderDataTarget,SerialPortDataTarget):
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
                    os.path.expanduser("~"), ".{}".format(self.__class__.__name__), "portdata.json"
                )
            )
            if config is None
            else config
        )
        self.possible_boards=[set() for board in self.required_boards]
        if self.config.get('api_name', default=self.__class__.__name__) != self.__class__.__name__:
            self.config.data = {}
            self.config.put('api_name', value=self.__class__.__name__)
            self.config.put('linked_boards', value=[None for board in self.required_boards])

        self.linked_boards = [None for board in self.required_boards]
        if len(self.config.get('linked_boards', default=self.linked_boards)) != len(self.linked_boards):
            self.config.put('linked_boards', value=[None for board in self.required_boards])

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

    def set_ports(self, available_ports, ignored_ports, connected_ports, identified_ports):
        proposed_linked_boards = self.config.get('linked_boards', default=self.linked_boards)
        identified_ports = [self.serial_reader.get_port(identified_port["port"]) for identified_port in identified_ports]
        for identified_port in identified_ports:
            board = identified_port.board
            #skip if alreay linked
            if board in self.linked_boards:
                continue
            #link all already proposed  boards
            for i in range(len(proposed_linked_boards)):
                if self.linked_boards[i] is not None: continue
                if proposed_linked_boards[i] == board.id:
                    self.link_board(i,board)
            #link to free boards
            for i in range(len(self.required_boards)):
                # if already linked skip
                if self.linked_boards[i] is not None: continue
                #if already reserved for another board
                if proposed_linked_boards[i] is not None :continue
                #if matching board
                if board.__class__ == self.required_boards[i]:
                    self.link_board(i,board)

        #unlink unavailable ports
        for i in range(len(self.linked_boards)):
            if self.linked_boards[i] is not None:
                if self.linked_boards[i].serial_port not in identified_ports:
                    self.unlink_board(i)



    def link_board(self, i, board):
        if board is None:
            return self.unlink_board(i)
        linked_boards = self.config.get('linked_boards', default=self.linked_boards)
        linked_boards[i] = board.id
        self.linked_boards[i] = board
        self.logger.info("link board {}({}) to index {}".format(board.id,board.__class__.__name__,i))
        self.config.put('linked_boards',value=linked_boards)
        #add to board_possibilities
        for i in range(len(self.required_boards)):
            if board.__class__ == self.required_boards[i]:
                self.possible_boards[i].add(board)

    def unlink_board(self, i):
        linked_boards = self.config.get('linked_boards', default=self.linked_boards)
        board = self.linked_boards[i]
        if board is None: return
        linked_boards[i] = None
        self.linked_boards[i] = None
        self.logger.info("unlink board from index {}".format(i))
        self.config.put('linked_boards',value=linked_boards)

        #remove from board possibilities
        for i in range(len(self.possible_boards)):
            if board in self.possible_boards[i]:
                self.possible_boards[i].remove(board)

    def get_possibilities_index(self,i):
        return self.possible_boards[i]

    def get_possibilities_board_class(self,board_class):
        for i in range(len(self.required_boards)):
            if board_class == self.required_boards[i]:
                return self.get_possibilities_index(i)
        return []

    def get_possibilities_board(self,board):
        return self.get_possibilities_board_class(board.__class__)

    get_board_alternatives = get_possibilities_board

    def add_ws_target(self, receiver):
        self._ws_targets.add(receiver)

    def remove_ws_target(self, receiver):
        if receiver in self._ws_targets:
            self._ws_targets.remove(receiver)


class ArduinoAPIWebsocketConsumer():
    apis = list()
    instances=set()
    logger = logging.getLogger("ArduinoAPIWebsocketConsumer")
    @classmethod
    def register_api(cls,api):
        """
        :type api: BoardApi
        """
        if api not  in cls.apis:
            cls.apis.append(api)
            for instance in cls.instances:
                api.add_ws_target(instance)
        print("aad",cls.apis)

    @classmethod
    def register_at_apis(cls,receiver):

        cls.instances.add(receiver)
        for api in cls.apis:
            api.add_ws_target(receiver)

    @classmethod
    def unregister_at_apis(cls,receiver):
        try:
            cls.instances.remove(receiver)
        except:
            pass
        for api in cls.apis:
            api.remove_ws_target(receiver)


    def client_to_api(self,textdata):
        data = json.loads(textdata)
        try:
            if data["type"] == "cmd":
                self.parse_command(data["data"])
            else:
                raise ValueError("invalid type: {} ".format(data["type"]))
        except Exception as e:
            self.logger.exception(e)

    def parse_command(self, data):
        if hasattr(self,data['cmd']):
            answer = filter_dict.call_method(getattr(self,data['cmd']),kwargs=data["data"])
        else:
            answer = filter_dict.call_method(getattr(self.apis[data["data"]["api"]],data['cmd']),kwargs=data["data"])
        if answer is not None:
            self.to_client(dict(cmd=data['cmd'].replace("get_","set_"),data=answer),type="cmd")

        print(answer)

    def get_apis(self):
        return self.apis

    def to_client(self,data=None, type=None):
        raise AttributeError("no valid to_client function implemented")
