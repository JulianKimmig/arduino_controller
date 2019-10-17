import logging
import os
import time

from json_dict import JsonDict
from arduino_controller.controller import ArduinoController

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('-c', '--config', dest="config",
                   default=os.path.join(os.path.expanduser("~"), ".ArduinoController", "controller_config.json"))

    kwargs = vars(p.parse_args())

    kwargs['config'] = JsonDict(kwargs['config'])

    logging_fmt = (
        "%(asctime)s %(filename)s %(lineno)d %(name)s %(levelname)-8s  %(message)s"
    )
    logging.basicConfig(level=logging.DEBUG, format=logging_fmt, datefmt="(%H:%M:%S)")

    try:
        import coloredlogs

        coloredlogs.install(level="DEBUG", fmt=logging_fmt)
    except:
        pass

    ac = ArduinoController(**kwargs, start_in_background=True)
    while ac._running:
        time.sleep(2)