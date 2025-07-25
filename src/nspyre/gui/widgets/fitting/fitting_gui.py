import nspyre.gui.widgets.fitting as ft
import numpy as np
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
import pyqtgraph as pg

class FittingGUI(QtWidgets.QWidget):
    """A GUI class for handling different types of data fitting and visualization."""
    
    def __init__(self, parent=None):
        """Initialize the FittingGUI widget.
        
        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())
        
    def button_generator(self, fit_class: str, fit_type: str, sink_name: str, **kwargs) -> QtWidgets.QPushButton:
        """Generate a fit button and add it to the widget layout.
        
        Args:
            fit_class: Type of fit class to use
            fit_type: Specific type of fit
            sink_name: Name of the data sink
            **kwargs: Additional arguments including:
                signal_data_name (str): Name of signal data (default: 'signal')
                background_data_name (str): Name of background data (default: 'background')
                name_data_to_fit (str): Name of data to fit (default: 'signal')
                x_axis_name (str): Label for x axis (default: 'Frequency (GHz)')
                y_axis_name (str): Label for y axis (default: 'Contrast')
                test_mode (bool): If True, returns the button for testing
        """
        self.fit_button = QtWidgets.QPushButton("Fit")
        self.fit_button.clicked.connect(lambda: self.fit_fun_window(
            fit_class, fit_type, sink_name, **kwargs))
        self.layout().addWidget(self.fit_button)
        if kwargs.get('test_mode', False):
            return self.fit_button

    def fit_fun_window(self, fit_class: str, fit_type: str, sink_name: str, **kwargs) -> None:
        """Open a new window for fitting functionality."""
        print("Opening a new window...")
    
        fit_spec = True
        if fit_class == 'exp':
            fit_class_name = "Exponential"
            fit_type_widget = QtWidgets.QLineEdit(fit_type)
        elif fit_class == 'lorentz':
            fit_class_name = "Lorentzian"
            fit_type_widget = QtWidgets.QLineEdit(fit_type)
        else:
            fit_class_name = fit_class
            fit_spec = False
    
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
    
        # Create a horizontal layout for the label and line edit
        fit_options_layout = QtWidgets.QHBoxLayout()
    
        # Add a label for the fit type
        if fit_spec == True:
            fit_label = QtWidgets.QLabel(fit_class_name +" Fit Type:")
            fit_options_layout.addWidget(fit_label)
            fit_options_layout.addWidget(fit_type_widget)

        # Add the horizontal layout to the main layout
        window_layout.addLayout(fit_options_layout)
    
        # Add a button to trigger some fitting functionality
        fit_button = QtWidgets.QPushButton("Run Fit")
        fit_button.clicked.connect(lambda: 
            self.data_fitting_fun(fit_class, fit_type_widget.text(), fit_plot_widget, 
                         sink_name, **kwargs))
    
        window_layout.addWidget(fit_button)

        # Set the layout to the new window
        new_window.setLayout(window_layout)

        # Show the new window
        new_window.show()

        # Keep a reference to avoid garbage collection
        self.new_window = new_window

    def data_fitting_fun(self, fit_class: str, fit_type: str, 
                        fit_plot_widget: pg.PlotWidget, sink_name: str, **kwargs) -> None:
        """Perform data fitting and plot results."""
        # Get data series name from kwargs or use first available
        series_name = kwargs.get('series_name', None)
        x_axis_name = kwargs.get('x_axis_name', 'Frequency (GHz)')
        y_axis_name = kwargs.get('y_axis_name', 'Signal')

        sink = DataSink(sink_name)
        sink.start()
        sink.pop()
        
        # Get available data series
        if not hasattr(sink, 'data_series') or not sink.data_series:
            sink.stop()
            raise ValueError("No data series available")

        if series_name is None:
            # Use first available series
            series_name = next(iter(sink.data_series.keys()))
        
        if series_name not in sink.data_series:
            sink.stop()
            raise ValueError(f"Data series '{series_name}' not found")

        series_data = sink.data_series[series_name]
        sink.stop()

        if not series_data or not isinstance(series_data, list):
            raise ValueError(f"Invalid data format for series '{series_name}'")

        # Extract data
        x_axis = series_data[0][0]
        data_arrays = np.array(series_data)[:,1,:]
        data_to_fit = np.nanmean(data_arrays, axis=0)
            
        # Prepare and plot data
        fitting_data = np.array([x_axis, data_to_fit])
        fit_plot_widget.clear()
        fit_plot_widget.addLegend()
        fit_plot_widget.plot(x_axis, data_to_fit, symbol='o', 
                           pen=None, symbolBrush='r', 
                           name=f"{series_name} Data")

        # Try fitting based on class type
        try:
            if fit_class == "exponential":
                plot_name = f"{fit_type} Exponential Fit"
                fit_result = ft.exponential_decay_fitting(fitting_data, fit_type)
            elif fit_class == "lorentzian":
                plot_name = f"{fit_type} Lorentzian Fit"
                fit_result = ft.odmr_fitting(fitting_data, fit_type)
            elif fit_class == "rabi":
                plot_name = "Rabi Fit"
                fit_result = ft.rabi_oscillation_fitting(fitting_data)
            else:
                raise ValueError(f"Invalid fit class: {fit_class}")

            # Plot fit result
            fit_plot_widget.plot(fit_result[0], fit_result[1], 
                               name=plot_name,
                               pen=pg.mkPen(color='blue', width=3))
            
            fit_plot_widget.setLabel('bottom', x_axis_name)
            fit_plot_widget.setLabel('left', y_axis_name)
            fit_plot_widget.setTitle(plot_name)

        except Exception as e:
            QtWidgets.QMessageBox.warning(None, "Fitting Error", str(e))

    @staticmethod
    def contrast_array(signal_arrays: np.ndarray, 
                      background_arrays: np.ndarray) -> np.ndarray:
        """Calculate contrast array from signal and background arrays."""
        sum_signal = signal_arrays.sum(axis=0)
        sum_background = background_arrays.sum(axis=0)
        return (sum_signal-sum_background)/(sum_signal+sum_background)

    def fitting_function_gui(self, 
                           fit_class: str,
                           fit_type: str,
                           sink_name: str,
                           signal_data_name: str = 'signal',
                           background_data_name: str = 'background',
                           name_data_to_fit: str = 'signal',
                           x_axis_name: str = 'Frequency (GHz)',
                           y_axis_name: str = 'Contrast',
                           test_mode: bool = False,
                           **kwargs) -> QtWidgets.QPushButton:
        """Main entry point for the fitting GUI."""
        all_kwargs = {
            'signal_data_name': signal_data_name,
            'background_data_name': background_data_name,
            'name_data_to_fit': name_data_to_fit,
            'x_axis_name': x_axis_name,
            'y_axis_name': y_axis_name,
            'test_mode': test_mode,
            **kwargs
        }
        return self.button_generator(fit_class, fit_type, sink_name, **all_kwargs)

