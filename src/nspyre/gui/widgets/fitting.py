from typing import Callable, Optional
import numpy as np
from scipy.optimize import curve_fit
from ...data.sink import DataSink
from pyqtgraph.Qt import QtWidgets
import pyqtgraph as pg
from ..style._colors import cyclic_colors

"""
Data fitting utilities and GUI components for nspyre.

This module provides curve fitting functions for common experimental scenarios
(exponential decays, Lorentzian peaks, damped oscillations) and a comprehensive
GUI widget for interactive data fitting and visualization.

The FittingGUI class supports optional data processing via user-supplied functions,
allowing for data filtering, transformation, or other preprocessing before fitting.
"""

# ============================================================================
# Fitting Model Functions
# ============================================================================


def single_exponential_decay(t, amp, decay_time, offset):
    """Single exponential decay function.

    Args:
        t (float or array): Time values.
        amp (float): Amplitude of exponential decay.
        decay_time (float): Characteristic decay time (T_1, T_2, etc.).
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following exponential decay: offset - amp * exp(-t / decay_time).
    """
    return offset - (amp * np.exp(-1 * t / decay_time))


def double_exponential_decay(t, amp_1, decay_time_1, amp_2, decay_time_2, offset):
    """Double exponential decay function.

    Args:
        t (float or array): Time values.
        amp_1 (float): Amplitude of first exponential component.
        decay_time_1 (float): Decay time of first component.
        amp_2 (float): Amplitude of second exponential component.
        decay_time_2 (float): Decay time of second component.
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following double exponential decay.
    """
    return offset - (amp_1 * np.exp(-1 * t / decay_time_1)
                     + amp_2 * np.exp(-1 * t / decay_time_2))


def triple_exponential_decay(t, amp_1, decay_time_1, amp_2, decay_time_2, amp_3,
                             decay_time_3, offset):
    """Triple exponential decay function.

    Args:
        t (float or array): Time values.
        amp_1 (float): Amplitude of first exponential component.
        decay_time_1 (float): Decay time of first component.
        amp_2 (float): Amplitude of second exponential component.
        decay_time_2 (float): Decay time of second component.
        amp_3 (float): Amplitude of third exponential component.
        decay_time_3 (float): Decay time of third component.
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following triple exponential decay.
    """
    return (offset - (amp_1 * np.exp(-1 * t / decay_time_1) + amp_2 * np.exp(-1 * t / decay_time_2)
                      + amp_3 * np.exp(-1 * t / decay_time_3))
            )


def damped_cos_fit(t, amp, freq, decay_time, phi, offset):
    """Exponentially damped cosine function.

    Args:
        t (float or array): Time values.
        amp (float): Amplitude of the oscillation.
        freq (float): Frequency of the cosine oscillation.
        decay_time (float): Exponential decay time constant.
        phi (float): Phase shift in radians.
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following damped cosine: offset + amp * cos(freq * t + phi) * exp(-t / decay_time).
    """
    return offset + (amp * np.cos(freq * t + phi) * np.exp(-1 * t / decay_time))


def single_lorentz_fit(f, amp, freq, hwhm, offset):
    """Single Lorentzian function.

    Args:
        f (float or array): Frequency values.
        amp (float): Amplitude (peak height) of the Lorentzian.
        freq (float): Center frequency of the Lorentzian peak.
        hwhm (float): Half-width at half-maximum.
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following Lorentzian profile: offset + amp * (hwhm² / ((f - freq)² + hwhm²)).
    """
    return offset + amp * ((hwhm**2) / ((f - freq)**2 + hwhm**2))


def double_lorentz_fit(t, amp_1, freq_1, hwhm_1, amp_2, freq_2, hwhm_2, offset):
    """Double Lorentzian function.

    Args:
        t (float or array): Frequency values.
        amp_1 (float): Amplitude of first Lorentzian peak.
        freq_1 (float): Center frequency of first peak.
        hwhm_1 (float): Half-width at half-maximum of first peak.
        amp_2 (float): Amplitude of second Lorentzian peak.
        freq_2 (float): Center frequency of second peak.
        hwhm_2 (float): Half-width at half-maximum of second peak.
        offset (float): Baseline offset of the data.

    Returns:
        float or array: Values following double Lorentzian profile.
    """
    return offset + (amp_1 * ((hwhm_1**2) / ((t - freq_1)**2 + hwhm_1**2))
                     + amp_2 * ((hwhm_2**2) / ((t - freq_2)**2 + hwhm_2**2))
                     )


# ============================================================================
# Data Processing Utilities
# ============================================================================
def data_reading(data_array, units='micro'):
    """Extract and scale time and dependent data arrays.

    Takes input data and returns scaled time and dependent variable arrays.
    Commonly used for converting time units (e.g., seconds to microseconds).

    Args:
        data_array (np.ndarray): 2D array where first row contains time/x-axis data
            and second row contains dependent/y-axis data.
        units (str or float, optional): Scaling factor for time data. 
            - 'micro': Apply microsecond scaling (10^-6)
            - float/int: Custom scaling factor
            Defaults to 'micro'.

    Returns:
        tuple[np.ndarray, np.ndarray]: Scaled time array and dependent variable array.

    Raises:
        TypeError: If units parameter is not a supported type.
    """
    if type(units) == str:
        scale = (10**-6)
    elif type(units) == float:
        scale = units
    elif type(units) == int:
        scale = units
    else:
        raise TypeError("units not set properly")
    t_data = data_array[0] * scale
    y_data = data_array[1]
    return t_data, y_data


# ============================================================================
# High-Level Fitting Functions
# ============================================================================


def exponential_decay_fitting(data_array, fit, save=True):
    """Fit exponential decay models to data.

    Performs single, double, or triple exponential decay fitting with automatic
    parameter bounds and error estimation. Results are printed to console and
    optionally returned as fitted curves.

    Args:
        data_array (np.ndarray): 2D array with time data in first row and 
            signal data in second row.
        fit (str): Type of exponential fit to perform.
            - 'Single': Single exponential decay
            - 'Double': Double exponential decay  
            - 'Triple': Triple exponential decay
        save (bool, optional): Whether to return fitted curve data. Defaults to True.

    Returns:
        list[np.ndarray, np.ndarray] or None: If save=True, returns [time_fit, signal_fit]
            arrays for plotting the fitted curve. Otherwise returns None.

    Raises:
        NameError: If fit parameter is not a valid fit type.

    Note:
        Time units are automatically rescaled to microseconds for display.
        Fit parameters and errors are printed to console.
    """
    # units rescaling for microsecond x-axis
    rescaling = (10**3)
    prefix = 'μ'

    # data extraction
    t_data, y_data = data_reading(data_array, units=1 / rescaling)

    # bound determination
    if y_data[-1] > y_data[1]:
        amp_bound_max = np.inf
        amp_bound_min = 0.00001
    elif y_data[-1] < y_data[1]:
        amp_bound_min = -np.inf
        amp_bound_max = -0.00001
    else:
        amp_bound_min = -np.inf
        amp_bound_max = np.inf

    # Perform curve fitting
    if fit == 'Single':
        bounds = ([amp_bound_min, .00001, y_data[-1] - 500],
                  [amp_bound_max, rescaling * 10**3, y_data[-1] + 500])
        parameters, covariance = curve_fit(single_exponential_decay, t_data,
                                           y_data, bounds=bounds)
        errors = np.sqrt(np.diag(covariance))
        amp, T_1, offset = parameters
        T_1 = T_1 * rescaling
        print("""T1 = {1}{6}s, Err = {4} \namp = {0}, Err = {3}, offset = {2}, 
              Err = {5}""".format(amp, T_1, offset, errors[0], errors[1], errors[2], prefix))

        if save == True:
            t_fit = np.linspace(min(t_data), max(t_data), 1000) * rescaling
            return [t_fit, single_exponential_decay(t_fit, amp, T_1, offset)]

    elif fit == 'Double':
        bounds = ([amp_bound_min, .00001, amp_bound_min, 0.00001, y_data[-1] - 500],
                  [amp_bound_max, rescaling, amp_bound_max, rescaling,
                   y_data[-1] + 500])
        parameters, covariance = curve_fit(double_exponential_decay, t_data,
                                           y_data, bounds=bounds)
        errors = np.sqrt(np.diag(covariance))
        amp_a, T_1_a, amp_b, T_1_b, offset = parameters
        # Redifining T1s so the largest one is T1, second T1'
        T_1_list = [T_1_a, T_1_b]
        T_1 = max(T_1_list) * rescaling
        amp_1 = [amp_a, amp_b][T_1_list.index(T_1 / rescaling)]
        T_1_p = min([T_1_a, T_1_b]) * rescaling
        amp_2 = [amp_a, amp_b][T_1_list.index(T_1_p / rescaling)]
        T_1_error = float(errors[np.where(parameters == T_1 / rescaling)])

        print("""T1 = {1}{6}s, Err = {5}, T1\' = {3}{6}s\namp = {0}, amp\' = {2}, 
              offset = {4}""".format(amp_1, T_1, amp_2, T_1_p, offset, T_1_error, prefix))

        if save == True:
            t_fit = np.linspace(t_data[0], t_data[-1], 1000) * rescaling
            return [t_fit, double_exponential_decay(t_fit, amp_a, T_1, amp_b, T_1_p, offset)]
    elif fit == 'Triple':
        bounds = ([amp_bound_min, .00001, amp_bound_min, 0.00001, amp_bound_min,
                   0.00001, y_data[-1] - 500], [amp_bound_max, rescaling * 10**(-3),
                                                amp_bound_max, rescaling
                                                * 10**(-3),
                                                amp_bound_max, rescaling
                                                * 10**(-3),
                                                y_data[-1] + 500])
        parameters, covariance = curve_fit(triple_exponential_decay, t_data,
                                           y_data, bounds=bounds)
        errors = np.sqrt(np.diag(covariance))
        amp_a, T_1_a, amp_b, T_1_b, amp_c, T_1_c, offset = parameters
        # Redifining T1s so the largest one is T1, second T1', and so on
        T_1_list = [T_1_a, T_1_b, T_1_c]
        T_1 = max([T_1_a, T_1_b, T_1_c]) * rescaling
        amp_1 = [amp_a, amp_b, amp_c][T_1_list.index(T_1 / rescaling)]
        T_1_p = np.median([T_1_a, T_1_b, T_1_c]) * rescaling
        amp_2 = [amp_a, amp_b, amp_c][T_1_list.index(T_1_p / rescaling)]
        T_1_pp = min([T_1_a, T_1_b, T_1_c]) * rescaling
        amp_3 = [amp_a, amp_b, amp_c][T_1_list.index(T_1_pp / rescaling)]
        T_1_error = float(errors[np.where(parameters == T_1 / rescaling)])

        print("""T1 = {1}{8}s, Err = {7}, T1\' = {3}{8}s, T1\'\' = {5}{8}s
              \namp = {0}, amp\' = {2}, amp\' \' = {4}, offset = {6}""".format(
            amp_1, T_1, amp_2, T_1_p, amp_3, T_1_pp, offset, T_1_error, prefix))

        if save == True:
            t_fit = np.linspace(min(t_data), max(t_data), 1000) * rescaling
            return [t_fit, triple_exponential_decay(t_fit, amp_1, T_1, amp_2,
                                                    T_1_p, amp_3, T_1_pp, offset)]
    else:
        raise NameError("Not a valid fit type")


def damped_cos_fitting(data_array, decay_time_guess=1, save=True):
    """Fit damped cosine model to oscillatory decay data.

    Fits data to an exponentially damped cosine function, commonly used for
    Rabi oscillation or other coherent oscillation measurements.

    Args:
        data_array (np.ndarray): 2D array with time data in first row and 
            signal data in second row.
        decay_time_guess (float, optional): Initial guess for decay time parameter. 
            Defaults to 1.
        save (bool, optional): Whether to return fitted curve data. Defaults to True.

    Returns:
        list[np.ndarray, np.ndarray] or None: If save=True, returns [time_fit, signal_fit]
            arrays for plotting the fitted curve. Otherwise returns None.

    Note:
        Automatically estimates initial parameters from data characteristics.
        Prints π-pulse time and frequency error to console.
    """
    # data extraction
    t_data, y_data = data_reading(data_array, units=1)
    bounds = ([0, 0, 0, 0, -1 * np.inf],
              [np.inf, np.inf, np.inf, 2 * np.pi, np.inf])

    amp_guess = np.abs(max(y_data) - min(y_data) / max(y_data))
    print(amp_guess)
    max_index = np.argmax(y_data)
    min_index = np.argmin(y_data)

    pi_time_guess = np.abs(t_data[max_index] - t_data[min_index])

    freq_guess = np.pi / pi_time_guess
    offset_guess = np.mean(y_data)

    parameters, covariance = curve_fit(damped_cos_fit, t_data, y_data, bounds=bounds, p0=[
                                       amp_guess, freq_guess, decay_time_guess, 0, offset_guess])
    amp, freq, decay_time, phi, offset = parameters

    errors = np.sqrt(np.diag(covariance))

    print("""Pi pulse time: {0}ns\n Freq Error: {1}""".format(np.pi / freq,
                                                              errors[1]))

    if save == True:
        t_fit = np.linspace(t_data[0], t_data[-1], 1000)
        return [t_fit, damped_cos_fit(t_fit, amp, freq, decay_time, phi, offset)]


def lorentz_fitting(data_array, fit, save=True):
    """Fit Lorentzian models to spectroscopic data.

    Performs single or double Lorentzian peak fitting, commonly used for
    spectral line analysis, resonance measurements, and ODMR spectroscopy.

    Args:
        data_array (np.ndarray): 2D array with frequency data in first row and 
            signal data in second row.
        fit (str): Type of Lorentzian fit to perform.
            - 'Single': Single Lorentzian peak
            - 'Double': Double Lorentzian peaks
        save (bool, optional): Whether to return fitted curve data. Defaults to True.

    Returns:
        list[np.ndarray, np.ndarray] or None: If save=True, returns [freq_fit, signal_fit]
            arrays for plotting the fitted curve. Otherwise returns None.

    Raises:
        ValueError: If fit parameter is not a valid fit type.

    Note:
        Fit parameters (center frequency, HWHM) are printed to console.
        For single fits, initial parameter guesses are automatically generated.
    """
    f_data, y_data = data_reading(data_array, units=1)
    if fit == 'Single':
        p0 = [0, np.mean(f_data), 0.1, y_data[0]]
        parameters, covariance = curve_fit(single_lorentz_fit, f_data, y_data, p0=p0)
        amp, freq, hwhm, offset = parameters
        errors = np.sqrt(np.diag(covariance))
        print("Freq: {0}\nHWHM: {1}".format(freq, hwhm))
        if save == True:
            f_fit = np.linspace(f_data[0], f_data[-1], 1000)
            return [f_fit, single_lorentz_fit(f_fit, amp, freq, hwhm, offset)]
    elif fit == 'Double':
        parameters, covariance = curve_fit(double_lorentz_fit, f_data, y_data)
        amp_1, freq_1, hwhm_1, amp_2, freq_2, hwhm_2, offset = parameters
        errors = np.sqrt(np.diag(covariance))
        if save == True:
            f_fit = np.linspace(f_data[0], f_data[-1], 1000)
            return [f_fit, double_lorentz_fit(f_fit, amp_1, freq_1, hwhm_1,
                                              amp_2, freq_2, hwhm_2, offset)]
    else:
        return ValueError("Not a valid fit type")


class FittingGUI(QtWidgets.QWidget):
    """A GUI widget for interactive data fitting and visualization.

    Provides a user-friendly interface for performing various types of curve fitting
    on experimental data, including exponential decays, Lorentzian peaks, and damped
    oscillations. The GUI includes dropdown menus for fit selection and real-time
    plotting of both data and fitted curves.

    Supports optional data processing via a user-supplied function that can modify
    or filter the data before fitting and plotting, similar to FlexLinePlotWidget.

    Attributes:
        fit_sink_name (str): Name of the data sink to connect to.
        series_name (str): Name of the data series for display.
        series (str): Key for accessing data series in the sink.
        data_processing_func (Optional[Callable]): Function for data post-processing.
        fit_sink (DataSink): Data sink instance for retrieving data.
        fit_class_combo (QComboBox): Dropdown for selecting fit class.
        fit_type_combo (QComboBox): Dropdown for selecting fit type.
        new_window (QWidget): Reference to the fitting window.
    """

    def __init__(self, fit_sink_name: str, series_name: str, series: str,
                 data_processing_func: Optional[Callable] = None):
        """Initialize the FittingGUI widget.

        Args:
            fit_sink_name (str): Name of the data sink to connect to for retrieving data.
            series_name (str): Human-readable name of the data series for display purposes.
            series (str): Key used to access the specific data series within the sink.
            data_processing_func (Optional[Callable]): Function to do any post-processing 
                of the data retrieved from the sink before fitting/plotting. Takes two 
                arguments: the FittingGUI instance and the DataSink instance.
        """
        self.fit_sink_name = fit_sink_name
        self.series_name = series_name
        self.series = series
        self.data_processing_func = data_processing_func
        super().__init__()
        self.fit_sink = DataSink(fit_sink_name)
        self.fit_sink.start()

    def fit_fun_window(self, default_fit_class: str = 'exp') -> None:
        """Create and display the main fitting window interface.

        Opens a new window containing the fitting interface with plot area,
        fit selection dropdowns, and control buttons. The window includes:
        - Plot widget for data visualization
        - Fit class dropdown (exp, lorentz, damped_cos, custom)
        - Fit type dropdown (context-dependent options)
        - Run Fit button to execute the fitting

        Args:
            default_fit_class (str, optional): Initial fit class selection. 
                Defaults to 'exp'.
        """
        print("Opening a new window...")

        # Create a new window
        new_window = QtWidgets.QWidget()
        new_window.setWindowTitle("Nspyre: Fitting")
        new_window.setGeometry(100, 100, 800, 600)  # Set window size and position

        # Create a layout for the new window
        window_layout = QtWidgets.QVBoxLayout()

        fit_plot_widget = pg.PlotWidget()
        fit_plot_widget.setBackground('white')

        # Add the plot widget to the window layout
        window_layout.addWidget(fit_plot_widget)

        # Create a horizontal layout for the fit options
        fit_options_layout = QtWidgets.QHBoxLayout()

        # Add fit class dropdown
        fit_class_label = QtWidgets.QLabel("Fit Class:")
        fit_class_combo = QtWidgets.QComboBox()
        fit_class_combo.addItems(['exp', 'lorentz', 'damped_cos', 'custom'])
        fit_class_combo.setCurrentText(default_fit_class)

        fit_options_layout.addWidget(fit_class_label)
        fit_options_layout.addWidget(fit_class_combo)

        # Add fit type dropdown (initially hidden)
        fit_type_label = QtWidgets.QLabel("Fit Type:")
        fit_type_combo = QtWidgets.QComboBox()

        fit_options_layout.addWidget(fit_type_label)
        fit_options_layout.addWidget(fit_type_combo)

        # Function to update fit type options based on fit class selection
        def update_fit_type_options():
            fit_class = fit_class_combo.currentText()
            fit_type_combo.clear()

            if fit_class == 'exp':
                fit_type_combo.addItems(['Single', 'Double', 'Triple'])
                fit_type_label.show()
                fit_type_combo.show()
            elif fit_class == 'lorentz':
                fit_type_combo.addItems(['Single', 'Double'])
                fit_type_label.show()
                fit_type_combo.show()
            else:  # rabi or other
                fit_type_label.hide()
                fit_type_combo.hide()

        # Connect the signal to update fit type options when fit class changes
        fit_class_combo.currentTextChanged.connect(update_fit_type_options)

        # Initialize the fit type options based on default selection
        update_fit_type_options()

        # Add the horizontal layout to the main layout
        window_layout.addLayout(fit_options_layout)

        # Store references to the combo boxes for later access
        self.fit_class_combo = fit_class_combo
        self.fit_type_combo = fit_type_combo

        # Add a button to trigger some fitting functionality
        fit_button = QtWidgets.QPushButton("Run Fit")
        fit_button.clicked.connect(lambda: self.data_fitting_fun(fit_plot_widget))

        window_layout.addWidget(fit_button)

        # Set the layout to the new window
        new_window.setLayout(window_layout)

        # Show the new window
        new_window.show()

        # Keep a reference to avoid garbage collection
        self.new_window = new_window

    def data_fitting_fun(self, fit_plot_widget: pg.PlotWidget) -> None:
        """Execute the selected fitting procedure and update the plot.

        Retrieves data from the sink, performs the specified curve fitting,
        and displays both the original data and fitted curve on the plot widget.
        Handles different fit types including exponential decays, Lorentzian peaks,
        and damped cosine oscillations.

        Args:
            fit_plot_widget (pg.PlotWidget): PyQtGraph plot widget to display results.

        Raises:
            ValueError: If no data series available or series not found.

        Note:
            Fit parameters and errors are printed to console during execution.
            Plot styling follows the light mode color scheme with appropriate
            symbols and line styles.
        """
        # Get axis info TODO check if label names are correct
        x_axis_name = getattr(self.fit_sink, 'x_label', 'X Axis')
        y_axis_name = getattr(self.fit_sink, 'y_label', 'Y Axis')

        # Get fit class and type from the combo boxes
        fit_class = self.fit_class_combo.currentText()
        fit_type = self.fit_type_combo.currentText() if self.fit_type_combo.isVisible() else None

        # Get available data series
        if not hasattr(self.fit_sink, 'data_series') or not self.fit_sink.data_series:
            raise ValueError("No data series available")

        if self.series not in self.fit_sink.data_series:
            raise ValueError(f"Data series '{self.series_name}' not found")

        series_data = np.array(self.fit_sink.data_series[self.series])

        # Extract data
        # TODO check correct series data format and use append vs average correctly
        x_axis = series_data[:, 0]
        data_to_fit = series_data[:, 1]

        # Apply data processing function if provided
        if self.data_processing_func is not None:
            self.data_processing_func(self, self.fit_sink)

        # Prepare and plot data
        fitting_data = np.array([x_axis, data_to_fit])
        fit_plot_widget.clear()
        fit_plot_widget.addLegend()

        # Plot data points with light mode styling
        data_color = cyclic_colors[0]  # Use first color from cyclic_colors (blue)
        fit_plot_widget.plot(x_axis, data_to_fit,
                             symbol='o',
                             pen=None,
                             # Dark gray with transparency
                             symbolBrush=pg.mkBrush(color=(25, 25, 25, 100)),
                             symbolSize=8,
                             name=f"{self.series_name} Data")

        # Try fitting based on class type
        try:
            if fit_class == "exp":
                plot_name = f"{fit_type} Exponential Fit"
                fit_result = exponential_decay_fitting(fitting_data, fit_type)
            elif fit_class == "lorentz":
                plot_name = f"{fit_type} Lorentzian Fit"
                fit_result = lorentz_fitting(fitting_data, fit_type)
            elif fit_class == "damped_cos":
                plot_name = "Damped Cosine Fit"
                fit_result = damped_cos_fitting(fitting_data)
            else:
                raise ValueError(f"Invalid fit class: {fit_class}")

            # Plot fit result with light mode styling
            fit_color = cyclic_colors[1]  # Use second color from cyclic_colors (orange)
            fit_plot_widget.plot(fit_result[0], fit_result[1],
                                 name=plot_name,
                                 pen=pg.mkPen(color=fit_color, width=5),
                                 symbolSize=0)  # No symbols for fit line

            fit_plot_widget.setLabel('bottom', x_axis_name)
            fit_plot_widget.setLabel('left', y_axis_name)
            fit_plot_widget.setTitle(plot_name)

        except Exception as e:
            QtWidgets.QMessageBox.warning(None, "Fitting Error", str(e))

    def close(self) -> None:
        """Clean up resources when closing the widget.

        Properly stops the DataSink to prevent resource leaks and calls
        the parent close method to ensure proper widget destruction.
        """
        if hasattr(self, 'fit_sink') and self.fit_sink is not None:
            self.fit_sink.stop()
        super().close()
