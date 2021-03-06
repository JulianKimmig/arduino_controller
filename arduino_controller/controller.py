from background_task_manager.runner import BackgroundTaskRunner
from json_dict import JsonDict

from arduino_connection_communicator.communicator import ArduinoConnectionCommunicator
from arduino_connection_watcher.arduino_connection_watcher import ArduinoConnectionWatcher

from arduino_connection_communicator.abstract_communicator import AbstractDataTarget

class ArduinoController(BackgroundTaskRunner,AbstractDataTarget):
    def __init__(self, config: JsonDict, start_in_background=False,usb=True):
        super().__init__(start_in_background=start_in_background)

        self.config = config
        self.connection_watcher = ArduinoConnectionWatcher(config=self.config.getsubdict("connection_watcher"),start_in_background=start_in_background,usb=usb)
        self.connection_communicator = ArduinoConnectionCommunicator(config=self.config.getsubdict("connection_communicator"),start_in_background=start_in_background,usb=usb)
        if usb:
            self.connection_communicator.usb_communicator.add_data_target(self.connection_watcher.usb_watcher)

        self.register_background_task(self.activate_new_arduinos)

    def activate_new_arduinos(self):
        if self.connection_watcher.usb_watcher is not None:
            for port in self.connection_watcher.usb_watcher.available_ports.copy():
                self.connection_communicator.usb_communicator.open_port(port)

