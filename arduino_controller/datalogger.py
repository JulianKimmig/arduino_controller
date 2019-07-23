import os
import sys
import threading
import time

import pandas as pd
import numpy as np

class DataLogger:
    def __init__(self):
        self._df = pd.DataFrame()
        self._min_y_diff={}
        self._last_added_data={}
        self._last_not_added_data={}


    def set_min_y_diff(self,key,delta):
        self._min_y_diff[key]=delta

    def get_serializable_data(self,key=None):
        data = self.get_data(key=key)
        return data.to_dict()

    def get_data(self,key=None):
        if key is None:
            return self._df.copy()
        else:
            if key not in self._df.columns:
                return pd.DataFrame()
            return self._df[key].copy()

    def clear_data(self):
        self._df = pd.DataFrame()
        self._last_added_data={}
        self._last_not_added_data={}

    def add_datapoint(self, key, y, x=None):
        if x is None:
            x = int(time.time()*1000)

        if key not in self._df.columns:
            self._df[key] = np.nan
            self._last_not_added_data[key] = None
            self._last_added_data[key] = None
            self._min_y_diff[key] = 0

        add_data=True
        if self._last_added_data[key] is not None:
            if abs(y-self._last_added_data[key][1])<self._min_y_diff[key]:
                self._last_not_added_data[key] = (x,y)
                add_data = False
            else:
                if self._last_not_added_data[key] is not None:
                    if self._last_not_added_data[key][0] not in self._df.index:
                        self._df.loc[self._last_not_added_data[key][0]] = np.nan
                    self._df[key][self._last_not_added_data[key][0]] = self._last_not_added_data[key][1]

        if add_data:
            if x not in self._df.index:
                self._df.loc[x] = np.nan
            self._df[key][x] = y
            self._last_added_data[key] = (x,y)
            self._last_not_added_data[key] = None
            return key,x,y

        return None,None,None

class DataLogger2:
    def __init__(self, rolling_data=False, rolling_size=1000,autosave_path=None,auosave_name="data",autosave=False):
        self._rolling_size = rolling_size
        self._max_save_size = None
        self._min_save_size = None
        self._min_save_time = None
        self._max_save_time = None
        self._save_check_time = None
        self._savename = None
        self._save_path = None
        self._autosave = False
        self._last_save_time = 0.0
        self.starttime = 0.0
        self._min_save_size = 50
        self.autosave_files = set()
        self.__autosave_thread: threading.Thread = None

        self._df = pd.DataFrame()
        self._df_rolling = None
        if rolling_data:
            self._df_rolling = pd.DataFrame()

        if autosave_path is not None and autosave:
            self.start_autosave(autosave_path,auosave_name)

    def start_autosave(
        self,
        path,
        savename,
        save_check_time=20,
        max_save_time=60 * 10,
        max_save_size=5 * 10 ** 6,
        min_save_size=50,
    ):
        self.stop_autosave()
        self.autosave_files=set()
        self._df = pd.DataFrame()
        self._min_save_size = min_save_size
        self._max_save_size = max_save_size
        self._max_save_time = max_save_time
        self._save_check_time = save_check_time
        self._savename = savename
        self._save_path = path
        self.starttime = time.time()
        self._autosave = True
        self.__autosave_thread = threading.Thread(target=self._autosaver)
        self.__autosave_thread.start()

    def stop_autosave(self, mergedata=False):
        if self.__autosave_thread is not None:
            self._autosave = False
            try:
                self.__autosave_thread.join()
            except:
                pass
            self.__autosave_thread = None
            s = sys.getsizeof(self._df)
            if s > self._min_save_size:
                self._do_autosave()

        if mergedata:
            li = []
            fullname = os.path.join(self._save_path, self._savename +"_" + str(int(self.starttime))+"_" + str(int(self._last_save_time)) + ".csv")
            for file in sorted(list(self.autosave_files)):
                df = pd.read_csv(file, index_col=0)
                li.append(df)

            try:
                df = pd.DataFrame(pd.concat(li, axis=0))
                df.to_csv(fullname)
                for file in self.autosave_files:
                    try:
                        os.remove(file)
                    except:
                        pass
            except ValueError:
                return None
            self.autosave_files = set()
            return fullname
        return self.autosave_files

    def _do_autosave(self):
        self._last_save_time = time.time()
        savedf = pd.DataFrame()
        savedf, self._df = self._df, savedf
        savename=self._savename + "_" + str(int(self._last_save_time)) + ".csv"
        savefile = os.path.join(self._save_path,savename,)
        self.autosave_files.add(savefile)
        savedf.to_csv(savefile)

    def _autosaver(self):
        while self._autosave:
            dt = time.time() - self._last_save_time
            s = sys.getsizeof(self._df)
            if dt > self._max_save_time or s > self._max_save_size:
                if s > self.\
                        _min_save_size:
                    self._do_autosave()
            time.sleep(1)
        self.stop_autosave()

    def add_datapoint(self, key, x, y):
        if key not in self._df.columns:
            self._df[key] = np.nan

        if x not in self._df.index:
            self._df.loc[x] = np.nan
        self._df[key][x] = y

        if self._df_rolling is not None:
            if key not in self._df_rolling.columns:
                self._df_rolling[key] = np.nan
            if x not in self._df_rolling.index:
                self._df_rolling.loc[x] = np.nan
            self._df_rolling[key][x] = y

            if self._df_rolling.shape[0] > self._rolling_size:
                self._df_rolling = self._df_rolling.iloc[-self._rolling_size :]

    def get_last_valid_values(self):
        last_valid = {}
        for key in self._df.columns:
            x = self._df[key].last_valid_index()
            if x is not None:
                y = self._df[key][x]
                last_valid[key] = (x, y)
        return last_valid
