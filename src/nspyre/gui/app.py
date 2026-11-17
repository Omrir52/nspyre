"""
nspyre application Qt GUI settings.
"""
import faulthandler
import gc
import logging
import sys
import threading
import traceback
from pathlib import Path

from pyqtgraph import _connectCleanup
from pyqtgraph import setConfigOptions
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtGui
from pyqtgraph.Qt import QtWidgets

from .style._style import nspyre_font
from .style._style import nspyre_palette
from .style._style import nspyre_style_sheet

_logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent

# keep the faulthandler file open for the life of the process
_fault_file = None


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    """sys.excepthook that logs instead of letting PyQt abort the process.

    PyQt5 >= 5.5 calls qFatal() (killing the GUI without notice) when an
    exception escapes a Python slot, unless a custom sys.excepthook is set.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _logger.error(
        'Unhandled exception:\n'
        + ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    )


def _log_unhandled_thread_exception(args):
    """threading.excepthook that logs exceptions from Python threads."""
    if args.exc_type is SystemExit:
        return
    _logger.error(
        f'Unhandled exception in thread [{getattr(args.thread, "name", None)}]:\n'
        + ''.join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
    )


def _qt_message_handler(mode, context, message):
    """Route Qt warnings (e.g. 'QThread: Destroyed while thread is still
    running', which precedes a fatal abort) into the nspyre log."""
    if mode == QtCore.QtMsgType.QtDebugMsg:
        _logger.debug(f'Qt: {message}')
    elif mode == QtCore.QtMsgType.QtInfoMsg:
        _logger.info(f'Qt: {message}')
    elif mode == QtCore.QtMsgType.QtWarningMsg:
        _logger.warning(f'Qt: {message}')
    else:
        _logger.critical(f'Qt: {message}')
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass


def _enable_crash_reporting():
    """Install exception hooks and dump native crashes (segfaults, aborts) to a
    file next to the nspyre log file, or to stderr if there is no log file."""
    global _fault_file
    sys.excepthook = _log_unhandled_exception
    threading.excepthook = _log_unhandled_thread_exception
    QtCore.qInstallMessageHandler(_qt_message_handler)

    if faulthandler.is_enabled():
        return
    log_dir = None
    for handler in logging.getLogger().handlers:
        base_filename = getattr(handler, 'baseFilename', None)
        if base_filename:
            log_dir = Path(base_filename).parent
            break
    try:
        if log_dir is not None:
            crash_path = log_dir / 'faulthandler.log'
            _fault_file = open(crash_path, 'a')
            faulthandler.enable(file=_fault_file, all_threads=True)
            _logger.info(f'Native crash tracebacks will be written to [{crash_path}].')
        elif sys.stderr is not None:
            faulthandler.enable(all_threads=True)
    except Exception as err:
        _logger.warning(f'Could not enable faulthandler: {err}')


class nspyreApp(QtWidgets.QApplication):
    """Create a Qt application object with the default nspyre settings.

    Typical usage example:

    .. code-block:: python

        from nspyre import nspyreApp

        app = nspyreApp()
        some_widget = SomeWidget()
        some_widget.show()
        app.exec()

    """

    def __init__(
        self,
        app_name: str = 'nspyre',
        palette: QtGui.QPalette = nspyre_palette,
        font: QtGui.QFont = nspyre_font,
    ):
        """
        Args:
            app_name: Display name of the application.
            palette: Qt palette.
            font: QFont to use for the application.
        """
        # for high DPI displays in Qt5
        if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
            QtCore.QCoreApplication.setAttribute(
                QtCore.Qt.AA_EnableHighDpiScaling, True
            )
        if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

        super().__init__(sys.argv)

        # log errors that would otherwise silently kill the GUI
        _enable_crash_reporting()

        self.setApplicationName(app_name)
        # dock icon
        icon_path = _HERE / 'images' / 'favicon.ico'
        self.setWindowIcon(QtGui.QIcon(str(icon_path)))

        # make sure pyqtgraph gets cleaned up properly
        _connectCleanup()
        # enable plot antialiasing
        setConfigOptions(antialias=True)

        # appearance settings for nspyre
        self.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
        self.setPalette(palette)
        self.setStyleSheet(nspyre_style_sheet)
        self.setFont(font)

    def exec(self, *args, **kwargs):
        """Run the GUI event loop."""
        try:
            super().exec(*args, **kwargs)
        except AttributeError:
            super().exec_(*args, **kwargs)
        # invoke garbage collector to make sure we don't get any false leak reports
        gc.collect()
        # report Qt leaks
        leaked_widgets = self.allWidgets()
        if leaked_widgets:
            leaked_str = f'Leaked {len(leaked_widgets)} Qt widgets:\n'
            for w in leaked_widgets:
                leaked_str += repr(w) + '\n'
            _logger.debug(leaked_str)
        else:
            _logger.debug('No Qt widgets leaked.')
