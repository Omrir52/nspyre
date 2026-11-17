import functools
import logging
from typing import Callable
from typing import Dict

from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtWidgets

_logger = logging.getLogger(__name__)


class _ObjectOnMainThread(QtCore.QObject):
    # emitted if an error is raised in the function running in the main thread
    _error = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()
        # move self to main thread
        self.moveToThread(QtWidgets.QApplication.instance().thread())
        self._error.connect(self._handle_error)

    def _handle_error(self, err: Exception):
        """Thread error handler."""
        raise err

    def run(self, fun: Callable, args: tuple, kwargs: Dict, blocking: bool):
        if blocking:
            ret = QtCore.QMetaObject.invokeMethod(
                self,
                '_run',
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                QtCore.Q_RETURN_ARG(list),
                QtCore.Q_ARG(object, fun),
                QtCore.Q_ARG(tuple, args),
                QtCore.Q_ARG(dict, kwargs),
            )
            if len(ret) == 0:
                # the function exitted prematurely
                return
            elif len(ret) == 1:
                # exited normally with return value
                return ret[0]
        else:
            QtCore.QMetaObject.invokeMethod(
                self,
                '_run',
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(object, fun),
                QtCore.Q_ARG(tuple, args),
                QtCore.Q_ARG(dict, kwargs),
            )

    @QtCore.pyqtSlot(object, tuple, dict, result=list)
    def _run(self, fun: Callable, args: tuple, kwargs: Dict) -> list:
        try:
            result = fun(*args, **kwargs)
        except Exception as err:
            self._error.emit(err)
            return []
        # wrap the result in a list in order to have a standardized return type
        return [result]


def run_threadsafe(blocking=False):
    """Decorate QThreadSafeObject sublass methods with this in order to automatically
    run them using run_safe.

    Usage Example:

    .. code-block:: python

        from nspyre import QThreadSafeObject
        from nspyre import run_threadsafe

        class DataBackend(QThreadSafeObject):
            @run_threadsafe()
            def doSomethingThreadSafe(self, arg):
                # this will be run in the QThreadSafeObject thread
                return arg

    Args:
        blocking: see run_safe().

    """

    def wrapped_again_run_safe(func):
        @functools.wraps(func)
        def wrapped_run_safe(self, *args, **kwargs):
            return self.run_safe(func, self, *args, blocking=blocking, **kwargs)

        return wrapped_run_safe

    return wrapped_again_run_safe


class QThreadSafeObject(QtCore.QObject):
    """Qt object associated with a new QThread. Implements several methods to
    make it easier to work with data in a thread-safe way."""

    # emitted if an error is raised in a function running in the thread
    _error = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()
        self.mutex = QtCore.QMutex()
        """Mutex to lock access to instance variables."""

        # object that belongs to main thread
        self.main_obj = _ObjectOnMainThread()

        self.thread = QtCore.QThread()
        """Thread to manage access requests for this object."""

        # set to true if a stop is requested
        self.stopped = False

        # move this object to the new thread
        self.moveToThread(self.thread)

        self._error.connect(self._handle_error)

    def _handle_error(self, err: Exception):
        """Thread error handler."""
        raise err

    def start(self):
        """Start the internal thread to handle requests."""
        self.thread.start()

    def stop(self):
        """Quit the internal thread."""
        self.stopped = True
        # Request interruption first to give running tasks a chance to stop.
        try:
            self.thread.requestInterruption()
        except Exception:
            pass

        # Ask the thread to quit its event loop.
        self.thread.quit()

        # Wait in short intervals while allowing the main event loop to process
        # pending events. This avoids a long blocking wait that can deadlock
        # when worker threads are waiting for GUI callbacks.
        total_wait_ms = 5000
        interval_ms = 100
        waited = 0
        app = None
        try:
            app = QtWidgets.QApplication.instance()
        except Exception:
            app = None

        while self.thread.isRunning() and waited < total_wait_ms:
            # process GUI events to allow any queued callbacks to run
            if app is not None:
                app.processEvents()
            self.thread.wait(interval_ms)
            waited += interval_ms

        if self.thread.isRunning():
            # if the owner is deleted now, Qt aborts the whole GUI with
            # 'QThread: Destroyed while thread is still running'
            _logger.error(
                f'{type(self).__name__} thread did not stop within '
                f'{total_wait_ms / 1000:g} s - a blocking call (e.g. a long '
                'sink.pop() timeout) is likely holding it.'
            )

    def run_main(self, fun, *args, blocking=False, **kwargs):
        """Run the given function on the main thread.

        Args:
            fun: Function to run.
            args: Arguments to the function.
            kwargs: Keyword arguments to the function.
            blocking: If true, block until the function returns. Non-blocking
                calls cannot return anything.

        Returns:
            Return value of the function.
        """
        return self.main_obj.run(fun, args, kwargs, blocking=blocking)

    def run_safe(self, fun: Callable, *args, blocking=False, **kwargs):
        """Run a given function on the thread of this object.

        Args:
            fun: Function to run.
            args: Arguments to the function.
            kwargs: Keyword arguments to the function.
            blocking: If true, block until the function returns. Non-blocking
                calls cannot return anything.

        Returns:
            Return value of the function.
        """
        if blocking:
            try:
                ret = QtCore.QMetaObject.invokeMethod(
                    self,
                    '_run_safe',
                    QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                    QtCore.Q_RETURN_ARG(list),
                    QtCore.Q_ARG(object, fun),
                    QtCore.Q_ARG(tuple, args),
                    QtCore.Q_ARG(dict, kwargs),
                )
            except Exception as err:
                if self.stopped:
                    return
                else:
                    raise err
            if len(ret) == 0:
                # the function exitted prematurely
                return
            elif len(ret) == 1:
                # exited normally with return value
                return ret[0]
        else:
            try:
                QtCore.QMetaObject.invokeMethod(
                    self,
                    '_run_safe',
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(object, fun),
                    QtCore.Q_ARG(tuple, args),
                    QtCore.Q_ARG(dict, kwargs),
                )
            except Exception as err:
                if self.stopped:
                    return
                else:
                    raise err

    @QtCore.pyqtSlot(object, tuple, dict, result=list)
    def _run_safe(self, fun: Callable, args: tuple, kwargs: dict) -> list:
        try:
            result = fun(*args, **kwargs)
        except Exception as err:
            if not self.stopped:
                self._error.emit(err)
            return []
        # wrap the result in a list in order to have a standardized return type
        return [result]

    def get_safe(self, attrs: list[str]) -> tuple:
        """Retrieve object attributes in a thread-safe way by accessing them
        while holding the internal mutex.

        Args:
            attrs: Object attribute names.

        Returns:
            tuple of object attributes.
        """
        if QtCore.QThread.currentThread() == self.thread:
            return tuple(self._get_safe(attrs))
        else:
            return tuple(
                QtCore.QMetaObject.invokeMethod(
                    self,
                    '_get_safe',
                    QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                    QtCore.Q_RETURN_ARG(list),
                    QtCore.Q_ARG(list, attrs),
                )
            )

    @QtCore.pyqtSlot(list, result=list)
    def _get_safe(self, attrs: list[str]) -> list:
        """Helper for get_safe()."""
        with QtCore.QMutexLocker(self.mutex):
            ret = []
            for i in attrs:
                ret.append(getattr(self, i))
            return ret
