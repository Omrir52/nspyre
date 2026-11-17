import logging
import queue
import subprocess
import threading
import time
from datetime import datetime
from functools import partial
from importlib import reload
from multiprocessing import Queue
from pathlib import Path
from types import ModuleType
from typing import Dict
from typing import Optional
from typing import Union

from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtWidgets

from ...data.file import AutoSaver
from ...misc.misc import ProcessRunner
from ...misc.misc import run_experiment
from .params import ParamsWidget

AUTOSAVE_DIR = Path.home() / 'Documents' / 'autosave'
"""Default directory for experiment autosave files."""


class ExperimentWidget(QtWidgets.QWidget):
    """Qt widget for automatically generating a GUI for a simple experiment.
    Parameters can be entered by the user in a
    :py:class:`~nspyre.gui.widgets.params.ParamsWidget`. Buttons are
    generated for the user to run, stop, and kill the experiment process.
    """

    def __init__(
        self,
        params_config: dict,
        module: ModuleType,
        cls: str,
        fun_name: str,
        constructor_args: Optional[list] = None,
        constructor_kwargs: Optional[dict] = None,
        fun_args: Optional[list] = None,
        fun_kwargs: Optional[dict] = None,
        title: Optional[str] = None,
        kill: bool = False,
        layout: QtWidgets.QLayout = None,
        pyro_reboot: bool = False,
        stop_timeout: float = 5.0,
        autosave: bool = False,
        autosave_interval: float = 30,
        autosave_dir: Optional[Union[str, Path]] = None,
    ):
        """
        Args:
            params_config: Dictionary that is passed to the constructor of
                :py:class:`~nspyre.gui.widgets.params.ParamsWidget`.
            module: Python module that contains cls.
            cls: Python class name as a string. An instance of this class will
                be created in a subprocess when the user presses the 'Run' button.
                The :code:`__enter__` and :code:`__exit__` methods will be called
                if implemented. In addition, if the class constructor takes
                keyword arguments :code:`queue_to_exp` and/or :code:`queue_from_exp`,
                multiprocessing :code:`Queue` objects will be passed in that can
                be used to communicate with the GUI.
            fun_name: Name of function within cls to run. All of the values from
                the ParamsWidget will be passed as keyword arguments to this function.
            constructor_args: Args to pass to cls.
            constructor_kwargs: Keyword arguments to pass to cls.
            fun_args: Args to pass to :code:`cls.fun`.
            fun_kwargs: Keyword arguments to pass to :code:`cls.fun`.
            title: Window title.
            kill: Add a kill button to allow the user to forcibly kill the subprocess
                running the experiment function.
            layout: Additional Qt layout to place between the parameters and
                run/stop/kill buttons.
            pyro_reboot: Enable timeout-based stopping with automatic pyro daemon
                restart if the process doesn't stop gracefully.
            stop_timeout: With pyro_reboot, seconds to wait after Stop before
                force-killing the experiment process.
            autosave: Automatically save the experiment's data set (the
                :code:`dataset` keyword argument passed to the experiment
                function) to a pickle file while the experiment runs. Each run
                gets its own file, named with the experiment class, data set,
                and start time, which is overwritten with the latest data.
            autosave_interval: Minimum time (s) between autosaves.
            autosave_dir: Directory for autosave files. A subdirectory is
                created for each day. Defaults to :py:data:`AUTOSAVE_DIR`.
        """
        super().__init__()

        if title is not None:
            self.setWindowTitle(title)

        self.module = module
        self.cls = cls
        self.fun_name = fun_name
        self.pyro_reboot = pyro_reboot
        self.stop_timeout = stop_timeout
        self.autosave = autosave
        self.autosave_interval = autosave_interval
        self.autosave_dir = Path(autosave_dir) if autosave_dir else AUTOSAVE_DIR
        self._autosaver: Optional[AutoSaver] = None

        if constructor_args is not None:
            self.constructor_args = constructor_args
        else:
            self.constructor_args = []

        if constructor_kwargs is not None:
            self.constructor_kwargs = constructor_kwargs
        else:
            self.constructor_kwargs = {}

        if fun_args is not None:
            self.fun_args = fun_args
        else:
            self.fun_args = []

        if fun_kwargs is not None:
            self.fun_kwargs = fun_kwargs
        else:
            self.fun_kwargs = {}

        self.params_widget = ParamsWidget(params_config)

        # run button
        run_button = QtWidgets.QPushButton('Run')
        self.run_proc = ProcessRunner()
        run_button.clicked.connect(self.run)

        self.queue_to_exp: Queue = Queue()
        """multiprocessing Queue to pass to the experiment subprocess and use
        for sending messages to the subprocess."""
        self.queue_from_exp: Queue = Queue()
        """multiprocessing Queue to pass to the experiment subprocess and use
        for receiving messages from the subprocess."""

        # notes area
        notes_label = QtWidgets.QLabel('Notes')
        self.notes_textbox = QtWidgets.QTextEdit('')

        # stop button
        stop_button = QtWidgets.QPushButton('Stop')
        stop_button.clicked.connect(self.stop)
        # use a partial because the stop function may already be destroyed by the time
        # this is called
        self.destroyed.connect(partial(self.stop, log=False))

        # kill button
        if kill:
            kill_button = QtWidgets.QPushButton('Kill')
            kill_button.clicked.connect(self.kill)

        # Qt layout that arranges the params and button vertically
        params_layout = QtWidgets.QVBoxLayout()
        params_layout.addWidget(self.params_widget)
        if layout is not None:
            params_layout.addLayout(layout)
        params_layout.addWidget(notes_label)
        params_layout.addWidget(self.notes_textbox)
        params_layout.addWidget(run_button)
        params_layout.addWidget(stop_button)
        if kill:
            params_layout.addWidget(kill_button)

        # time of the last autosave (the file name is logged to the terminal)
        self.autosave_label = QtWidgets.QLabel('')
        self.autosave_label.setVisible(autosave)
        params_layout.addWidget(self.autosave_label)
        # polls the experiment process so the autosave can be finalized when it ends
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setInterval(500)
        self._autosave_timer.timeout.connect(self._check_autosave)
        self.destroyed.connect(lambda *_: self._stop_autosave())

        self.setLayout(params_layout)

    def additional_constructor_kwargs(self) -> Dict:
        """Users can override this function to provide additional kwargs to
        the experiment class constructor.

        Returns:
            A dict containing any additional kwargs to be passed to the
            experiment class constructor.
        """
        return {}

    def additional_fun_kwargs(self) -> Dict:
        """Users can override this function to provide additional kwargs to
        the experiment function. It is called when the user clicks the
        'Run' button.

        Returns:
            A dict containing any additional kwargs to be passed to the
            experiment function.
        """
        ret = {
            'notes': self.notes_textbox.toPlainText(),
            'queue_to_exp': self.queue_to_exp,
            'queue_from_exp': self.queue_from_exp,
        }
        return ret

    def run(self):
        """Run the experiment function in a subprocess."""

        if self.run_proc.running():
            logging.info(
                'Not starting the experiment process because it is still running.'
            )
            return

        # reload the module at runtime in case any changes were made to the code
        reload(self.module)
        # get the experiment class
        exp_cls = getattr(self.module, self.cls)
        # add the queues to the constructor kwargs
        constructor_kwargs = dict(
            **self.constructor_kwargs, **self.additional_constructor_kwargs()
        )
        # add the params and notes to the function kwargs
        fun_kwargs = dict(
            **self.fun_kwargs,
            **self.additional_fun_kwargs(),
        )
        if self.autosave:
            self._start_autosave(fun_kwargs.get('dataset'))
        # call the function in a new process
        self.run_proc.run(
            run_experiment,
            exp_cls=exp_cls,
            fun_name=self.fun_name,
            constructor_args=self.constructor_args,
            constructor_kwargs=constructor_kwargs,
            fun_args=self.fun_args,
            fun_kwargs=fun_kwargs,
        )

    def _start_autosave(self, dataset: Optional[str]):
        """Start a new autosave file for the experiment that is about to run."""
        # finish the previous run's final save so it can't pick up the new run's data
        self._stop_autosave()
        if not dataset:
            logging.warning('Not autosaving because the experiment has no dataset.')
            return
        start = datetime.now()
        safe_dataset = ''.join(c if c.isalnum() or c in '-_' else '_' for c in dataset)
        filename = (
            self.autosave_dir
            / start.strftime('%Y-%m-%d')
            / f'{self.cls}_{safe_dataset}_{start.strftime("%Y%m%d_%H%M%S")}.pickle'
        )
        try:
            self._autosaver = AutoSaver(
                dataset, filename, min_interval=self.autosave_interval
            )
            self._autosaver.start()
        except Exception as err:
            logging.warning(f'Failed to start autosave: {err}')
            self._autosaver = None
            self.autosave_label.setText('Autosave failed')
            return
        self.autosave_label.setText('')
        self._autosave_timer.start()

    def _stop_autosave(self, timeout: float = 5):
        """Do the final autosave and wait for it to finish."""
        if self._autosaver is not None:
            self._autosaver.stop()
            self._autosaver.join(timeout=timeout)

    def _check_autosave(self):
        """Show the last autosave time, and finalize the autosave once the
        experiment process has ended."""
        autosaver = self._autosaver
        if autosaver is None:
            self._autosave_timer.stop()
            return
        if not self.run_proc.running():
            # final save happens in the autosave thread
            autosaver.stop()
        if autosaver.last_save_time is not None:
            t = datetime.fromtimestamp(autosaver.last_save_time).strftime('%H:%M:%S')
            self.autosave_label.setText(f'Autosaved {t}')
        if not autosaver.is_alive():
            self._autosave_timer.stop()

    def stop(self, log: bool = True):
        """Request the experiment subprocess to stop by sending the string :code:`stop`
        to :code:`queue_to_exp`.

        Args:
            log: if True, log when stop is called but the process isn't running.
        """
        if not self.run_proc.running():
            if log:
                logging.info(
                    'Not stopping the experiment process because it is not running.'
                )
            return

        # Always send stop signal first (preserve base functionality)
        self.queue_to_exp.put('stop')

        if self.pyro_reboot:
            # Use timeout-based monitoring with pyro reboot
            self._monitor_stop_with_reboot()

    def _monitor_stop_with_reboot(self):
        """Monitor stop process and restart pyro daemon if force kill is needed."""
        def force_kill_after_timeout():
            """Kill the process if it doesn't stop gracefully within timeout."""
            check_interval = 0.5  # Check every 0.5 seconds
            max_checks = max(1, int(round(self.stop_timeout / check_interval)))

            for check_count in range(max_checks):
                time.sleep(check_interval)
                if not self.run_proc.running():
                    # Process stopped gracefully, no need to kill
                    return

            # Process still running after all checks, force kill
            if self.run_proc.running():
                print(f"Process didn't stop gracefully after {max_checks * check_interval}s, forcing kill...")
                self.run_proc.kill()

                # Restart pyro daemon after force kill
                self._restart_rfsoc_daemon()

        # Start the timeout monitor in a separate thread
        threading.Thread(target=force_kill_after_timeout, daemon=True).start()

    def _restart_rfsoc_daemon(self):
        """Restart the Pyro daemon on the RFSoC via SSH."""
        try:
            # Try to import RFSoC configuration
            from compton_nspyre.config import ip_addrs, rfsoc_user, rfsoc_pwd

            rfsoc_ip = ip_addrs['rfsoc']  
            username = rfsoc_user         
            password = rfsoc_pwd

            # Combined command to kill, wait, then start
            combined_command = f"echo '{password}' | sudo -S pkill -9 python; sleep 2; echo '{password}' | sudo -S bash -c 'source /etc/profile && cd /qick-spin/pyro4 && nohup python pyro_service.py > pyro.log 2>&1 &'"
            
            print("Attempting to restart RFSoC Pyro daemon...")
            
            # Try using plink (PuTTY) first if available on Windows
            try:
                # First try to cache the host key automatically
                self._cache_host_key(rfsoc_ip, username, password)
                
                plink_cmd = [
                    "plink", "-ssh", "-batch", "-pw", password,
                    f"{username}@{rfsoc_ip}",
                    combined_command
                ]
                
                result = subprocess.run(
                    plink_cmd,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
                
                if result.returncode == 0:
                    print("RFSoC Pyro daemon restart completed using plink")
                else:
                    print(f"plink command failed: {result.stderr}")
                    
            except FileNotFoundError:
                # plink not available, use standard SSH with combined command
                print("plink not found, using standard SSH...")
                
                ssh_cmd = [
                    "ssh", 
                    "-o", "StrictHostKeyChecking=no",  # Accept unknown host keys
                    "-o", "UserKnownHostsFile=/dev/null",  # Don't save host keys
                    f"{username}@{rfsoc_ip}",
                    combined_command
                ]
                
                result = subprocess.run(
                    ssh_cmd,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
                
                if result.returncode == 0:
                    print("RFSoC Pyro daemon restart completed")
                else:
                    print(f"SSH command failed: {result.stderr}")
                
        except ImportError:
            print("RFSoC configuration not available, skipping daemon restart")
        except subprocess.TimeoutExpired:
            print("SSH command timed out")
        except Exception as e:
            print(f"Error restarting RFSoC daemon: {e}")

    def _cache_host_key(self, host_ip, username, password):
        """Cache the host key for future connections."""
        try:
            print("Attempting to cache host key...")
            
            # Use plink to cache the host key by connecting and immediately exiting
            # The 'echo y' will automatically accept the host key prompt
            cache_cmd = [
                "cmd", "/c", 
                f'echo y | plink -ssh -pw {password} {username}@{host_ip} "exit"'
            ]
            
            result = subprocess.run(
                cache_cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            # plink may return non-zero even on success when just caching keys
            if "The server's host key is not cached" in result.stderr or result.returncode == 0:
                print("Host key cached successfully")
            else:
                print(f"Host key caching result: {result.stderr}")
                
        except Exception as e:
            print(f"Error caching host key: {e}")

    def kill(self):
        """Kill the experiment subprocess."""
        if self.run_proc.running():
            self.run_proc.kill()
        else:
            logging.info(
                'Not killing the experiment process because it is not running.'
            )

def experiment_widget_process_queue(msg_queue) -> Optional[str]:
    """Reads messages sent/received to/from a multiprocessing :code:`Queue` by \
    :py:class:`~nspyre.gui.widgets.experiment.ExperimentWidget`.

    Args:
        msg_queue: multiprocessing Queue object.

    Returns:
        The message received from the experiment subprocess.
    """
    # check for messages from the GUI
    if msg_queue is not None:
        try:
            # try to get a message from the queue
            o = msg_queue.get_nowait()
        except queue.Empty:
            # no message was available so we can continue
            return None
        else:
            return o
    else:
        return None
