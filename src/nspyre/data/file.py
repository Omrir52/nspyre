import json
import logging
import os
import pickle
import threading
import time
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

import numpy as np

from .server import DATASERV_PORT
from .sink import DataSink

_logger = logging.getLogger(__name__)


class _NumpyEncoder(json.JSONEncoder):
    """For converting numpy arrays to python lists so that they can be written to JSON:
    https://stackoverflow.com/questions/26646362/numpy-array-is-not-json-serializable
    """

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_json(filename: Union[str, Path], data: Any):
    """Save data to a json file.

    Args:
        filename: File to save to.
        data: Python object to save.
    """
    with open(filename, 'w') as f:
        json.dump(data, f, cls=_NumpyEncoder, indent=4)


def save_pickle(filename: Union[str, Path], data: Any):
    """Save data to a python pickle file.

    Args:
        filename: File to save to.
        data: Python object to save.
    """
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


class AutoSaver:
    """Automatically save a data set in the data server to a pickle file.

    A background thread continuously pops the data set (so the data server
    doesn't drop the sink for falling behind) and overwrites the file with the
    most recent data at most every :code:`min_interval` seconds. The saved
    object is exactly what the :py:class:`~nspyre.data.source.DataSource`
    pushed, so the file can be loaded with :py:func:`load_pickle`.

    Whatever the data set contains when :py:meth:`start` is called (e.g. data
    from a previous experiment that used the same data set name) is ignored -
    only data pushed after :py:meth:`start` returns is saved. A final save is
    performed when :py:meth:`stop` is called.
    """

    def __init__(
        self,
        data_set: str,
        filename: Union[str, Path],
        min_interval: float = 30,
        addr: str = 'localhost',
        port: int = DATASERV_PORT,
    ):
        """
        Args:
            data_set: Data set name in the data server to save.
            filename: File to save to.
            min_interval: Minimum time (s) interval to save data.
            addr: Network address of the data server.
            port: Port of the data server.
        """
        self.data_set = data_set
        self.filename = Path(filename)
        self.min_interval = min_interval
        self.last_save_time: Optional[float] = None
        """:code:`time.time()` of the most recent successful save, or :code:`None`."""
        # no auto_reconnect so that start() fails instead of blocking forever if
        # the data server isn't running
        self._sink = DataSink(data_set, addr=addr, port=port)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # whether the sink has received data that hasn't been saved yet
        self._dirty = False

    def start(self):
        """Connect to the data server, discard the current contents of the data
        set, and start autosaving in a background thread. Blocks for ~1 s while
        discarding the stale data, so call it before starting the experiment."""
        self._sink.start()
        # the server sends the current (stale) contents of the data set to every
        # new sink - pop it so that only data pushed from now on is saved
        self._drain(first_timeout=1.0)
        self._dirty = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _logger.info(f'Autosaving data set [{self.data_set}] to [{self.filename}].')

    def stop(self):
        """Request a final save and shut down the background thread. Returns
        immediately - use :py:meth:`join` to wait for the final save."""
        self._stop_event.set()

    def join(self, timeout: Optional[float] = None):
        """Wait for the background thread to finish."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        """Return True if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def _pop(self, timeout: float) -> bool:
        """Pop from the sink. Return True if new data was received."""
        try:
            self._sink.pop(timeout=timeout)
        except TimeoutError:
            return False
        self._dirty = True
        return True

    def _drain(self, first_timeout: float, max_time: float = 5.0):
        """Pop until no more data is immediately available."""
        t_end = time.monotonic() + max_time
        timeout = first_timeout
        while time.monotonic() < t_end and self._pop(timeout):
            timeout = 0.2

    def _save(self):
        """Overwrite the file with the latest data. Writes to a temporary file
        first so that a crash mid-write never corrupts the previous save."""
        if not self._dirty or self._sink.data is None:
            return
        tmp = self.filename.with_name(self.filename.name + '.tmp')
        try:
            self.filename.parent.mkdir(parents=True, exist_ok=True)
            save_pickle(tmp, self._sink.data)
            os.replace(tmp, self.filename)
        except Exception as err:
            # e.g. the file is open in another program - try again next interval
            _logger.warning(f'Autosave to [{self.filename}] failed: {err}')
        else:
            self._dirty = False
            self.last_save_time = time.time()
            _logger.info(f'Autosaved data set [{self.data_set}] to [{self.filename}].')

    def _run(self):
        """Background thread main loop."""
        last_save = time.monotonic()
        try:
            while not self._stop_event.is_set():
                try:
                    self._pop(timeout=0.5)
                except Exception as err:
                    # lost the data server connection - save what we have and quit
                    _logger.warning(f'Autosave sink error: {err}')
                    break
                if time.monotonic() - last_save >= self.min_interval:
                    self._save()
                    last_save = time.monotonic()
            # pick up any data still in flight from the experiment, then save
            try:
                self._drain(first_timeout=1.0)
            except Exception as err:
                _logger.warning(f'Autosave sink error: {err}')
            self._save()
        finally:
            self._sink.stop()
            if self.last_save_time is None:
                _logger.info(
                    f'Stopped autosaving data set [{self.data_set}] - no data was '
                    'received, so nothing was saved.'
                )
            else:
                _logger.info(
                    f'Stopped autosaving data set [{self.data_set}]. Final save: '
                    f'[{self.filename}].'
                )


def load_json(filename: Union[str, Path]) -> Any:
    """Load data from a JSON file.

    Args:
        filename: File to load from.

    Returns:
        A Python object loaded from the file.
    """
    with open(filename, 'r') as f:
        data = json.load(f)
        return data


def load_pickle(filename: Union[str, Path]) -> Any:
    """Load data from a Python pickle file.

    Args:
        filename: File to load from.

    Returns:
        A Python object loaded from the file.
    """
    with open(filename, 'rb') as f:
        data = pickle.load(f)
        return data
