import os
import sys
import threading
import time

import pandas as pd
import numpy as np


class DataLogger:
    def __init__(self):
        self._df = pd.DataFrame()
        self._min_y_diff = {}
        self._last_added_data = {}
        self._last_not_added_data = {}

    def set_min_y_diff(self, key, delta):
        self._min_y_diff[key] = delta

    def get_serializable_data(self, key=None):
        data = self.get_data(key=key)

        for key in data.columns:
            if self._last_not_added_data[key] is not None:
                if self._last_not_added_data[key][0] not in data.index:
                    data.loc[self._last_not_added_data[key][0]] = np.nan
                data[key][
                    self._last_not_added_data[key][0]
                ] = self._last_not_added_data[key][1]
        return data.to_dict()

    def get_data(self, key=None):
        if key is None:
            return self._df.copy()
        else:
            if key not in self._df.columns:
                return pd.DataFrame()
            return self._df[key].copy()

    def clear_data(self):
        self._df = pd.DataFrame()
        self._last_added_data = {}
        self._last_not_added_data = {}

    def add_datapoint(self, key, y, x=None, force=False):
        if x is None:
            x = int(time.time() * 1000)

        if key not in self._df.columns:
            self._df[key] = np.nan
            self._last_not_added_data[key] = None
            self._last_added_data[key] = None
            self._min_y_diff[key] = 0

        add_data = True
        if self._last_added_data[key] is not None:
            if (
                abs(y - self._last_added_data[key][1]) <= self._min_y_diff[key]
                and not force
            ):
                self._last_not_added_data[key] = (x, y)
                add_data = False
            else:
                if self._last_not_added_data[key] is not None:
                    if self._last_not_added_data[key][0] not in self._df.index:
                        self._df.loc[self._last_not_added_data[key][0]] = np.nan
                    self._df[key][
                        self._last_not_added_data[key][0]
                    ] = self._last_not_added_data[key][1]

        if add_data:
            if x not in self._df.index:
                self._df.loc[x] = np.nan
            self._df[key][x] = y
            self._last_added_data[key] = (x, y)
            self._last_not_added_data[key] = None
            return key, x, y

        return None, None, None

    def save(self, file, header_dict={}):
        header = "\n".join(
            ["#{}={}".format(key, value) for key, value in header_dict.items()]
        )
        with open(file, "w+") as f:
            for line in header:
                f.write(line)
            self._df.to_csv(f)
