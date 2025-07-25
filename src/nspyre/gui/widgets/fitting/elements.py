"""
Example GUI elements.
"""
import numpy as np
from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from nspyre import cyclic_colors
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
import pyqtgraph as pg
from fitting import exponential_decay_fitting
from fitting import rabi_oscillation_fitting
from fitting import rabi_fit
from fitting import odmr_fitting
from template.gui.fitting_gui import FittingGUI

import template.experiments.odmr
from plot_color_flip import PlotColorManager


class ODMRWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(100e3, 10e9),
                    dec=True,
                ),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(100e3, 10e9),
                    dec=True,
                ),
            },
            'num_points': {
                'display_text': 'Number of Scan Points',
                'widget': SpinBox(value=101, int=True, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Number of Experiment Repeats',
                'widget': SpinBox(value=50, int=True, bounds=(1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmr'),
            },
        }

        super().__init__(params_config, 
                        template.experiments.odmr,
                        'SpinMeasurements',
                        'odmr_sweep',
                        title='ODMR')

def process_ODMR_data(sink: DataSink):
    """Subtract the signal from background trace and add it as a new 'diff' dataset."""
    diff_sweeps = []
    contrast_sweeps = []
    for s,_ in enumerate(sink.datasets['signal']):
        freqs = sink.datasets['signal'][s][0]
        sig = sink.datasets['signal'][s][1]
        bg = sink.datasets['background'][s][1]
        diff_sweeps.append(np.stack([freqs, sig - bg]))
        contrast_sweeps.append(np.stack([freqs, (sig-bg)/(sig+bg)]))
    sink.datasets['diff'] = diff_sweeps
    sink.datasets['contr'] = contrast_sweeps


class FlexLinePlotWidgetWithODMRDefaults(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_ODMR_data)
        # create some default signal plots
        self.add_plot('sig_avg',        series='signal',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('sig_latest',     series='signal',   scan_i='-1',   scan_j='',  processing='Average')
        self.add_plot('sig_first',      series='signal',   scan_i='0',    scan_j='1', processing='Average')
        self.add_plot('sig_latest_10',  series='signal',   scan_i='-10',  scan_j='',  processing='Average')
        self.hide_plot('sig_first')
        self.hide_plot('sig_latest_10')

        # create some default background plots
        self.add_plot('bg_avg',         series='background',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('bg_latest',      series='background',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default diff plots
        self.add_plot('diff_avg',       series='diff',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('diff_latest',    series='diff',  scan_i='-1',    scan_j='',  processing='Average')
        self.add_plot('contr_avg',      series='contr',  scan_i='',      scan_j='',  processing='Average')
        # manually set the XY range
        self.line_plot.plot_item().setXRange(3.0, 4.0)
        self.line_plot.plot_item().setYRange(-3000, 4500)

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmr')
        
        layout = self.layout()
        
        # Create and add the fitting GUI
        self.fitting_gui = FittingGUI()
        self.fitting_gui.fitting_function_gui('lorentz', 'Single', 'odmr')
        layout.addWidget(self.fitting_gui)
        
        # Initialize the plot color manager
        self.plot_color_manager = PlotColorManager(self)
        layout.addWidget(self.plot_color_manager.color_flip_button)
         
#     def fit_fun_window(self):
#         """Open a new window"""
#         print("Opening a new window...")
        
#         # Create a new window
#         new_window = QtWidgets.QWidget()
#         new_window.setWindowTitle("Fitting")
#         new_window.setGeometry(100, 100, 800, 600)  # Set window size and position

#         # Create a layout for the new window
#         window_layout = QtWidgets.QVBoxLayout()

#         fit_plot_widget = pg.PlotWidget()
#         fit_plot_widget.setBackground('white')

#         # Add the plot widget to the window layout
#         window_layout.addWidget(fit_plot_widget)
        
        
#         # Create a horizontal layout for the label and line edit
#         fit_options_layout = QtWidgets.QHBoxLayout()

#         # Add a label for the fit type
#         fit_label = QtWidgets.QLabel("Exponential Fit Type:")
#         fit_options_layout.addWidget(fit_label)

#         # Add a QLineEdit to specify the fit type
#         fit_type = QtWidgets.QLineEdit('Double')
#         fit_options_layout.addWidget(fit_type)
        
#         pi_time_label = QtWidgets.QLabel("Pi Pulse Time Guess:")
#         pi_time_guess = SpinBox(value=10, suffix='ns', siPrefix=False, bounds=(0, np.inf), int=False, step = 1)
#         fit_options_layout.addWidget(pi_time_label)
#         fit_options_layout.addWidget(pi_time_guess)

#         # Add the horizontal layout to the main layout
#         window_layout.addLayout(fit_options_layout)
        
        
#         # Add a button to trigger some fitting functionality
#         fit_button = QtWidgets.QPushButton("Run Fit")
#         fit_button.clicked.connect(lambda: self.data_fitting_fun(fit_type.text(),fit_plot_widget,pi_time_guess.value()))
        
#         window_layout.addWidget(fit_button)

#         # Set the layout to the new window
#         new_window.setLayout(window_layout)

#         # Show the new window
#         new_window.show()

#         # Keep a reference to avoid garbage collection
#         self.new_window = new_window
        
#     def data_fitting_fun(self,fit_type,fit_plot_widget, pi_time_guess):
#         sink = DataSink('odmr')
#         ## Code a way to check if the dataserver has data in it. Python will crash if it does not
#         sink.start()
#         sink.pop()
#         data = sink.data.get('datasets')
#         signal_data = data.get('signal')
#         background_data = data.get('background')
#         print(data)
#         sink.stop()
#         x_axis = signal_data[0][0]
#         signal_arrays = np.array(signal_data)[:,1,:]
#         background_arrays = np.array(background_data)[:,1,:]
#         average_signal = np.nanmean(signal_arrays,axis=0)
#         average_background = np.nanmean(background_arrays, axis=0)
#         average_contrast = (average_signal-average_background)/average_background
#         average_signal = rabi_fit(x_axis, 1000, 22, 1, 0, 500)
#         fitting_data = np.array([x_axis,average_signal])
#         # Plot your data in the new window (example: average_signal vs. x_axis)
#         fit_plot_widget.clear()
#         fit_plot_widget.addLegend()
#         fit_plot_widget.scatterPlot(x_axis, average_signal, brush = pg.mkBrush('r'),name="Average Signal")
#         #fit_plot_widget.scatterPlot(x_axis, average_contrast, brush = pg.mkBrush('r'),name="Average Contrast")
#         #fitting_data = np.array([x_axis, average_contrast])
#         #fit_data = exponential_decay_fitting(fitting_data, fit_type, save = True)
#         fit_data = rabi_oscillation_fitting(fitting_data)
#         #fit_data = odmr_fitting(fitting_data, fit_type, save = True)
#         plot_name = fit_type + " exponential fit"
#         fit_plot_widget.plot(fit_data[0],fit_data[1], name=plot_name, pen=pg.mkPen(color='blue', width=3))
#         fit_plot_widget.setLabel('bottom', 'Frequency (GHz)')
#         fit_plot_widget.setLabel('left', 'Contrast')
#         fit_plot_widget.setTitle(plot_name)
        
    
    


        
        
        

# class FittingDataWidget(ExperimentWidget):
#     def __init__(self):
#         params_config = {
#             'fit_type': {
#                 'display_text': "Fit Type",
#                 'widget': QtWidgets.QLineEdit('Double'),
#             },
#             'units': {
#                 'display_text': "Units",
#                 'widget': QtWidgets.QLineEdit('micro'),
#             },
#             'measurement': {
#                 'display_text': "Measurement",
#                 'widget': QtWidgets.QLineEdit('Optical T1')
#             },
#             'B_dir': {
#                 'display_text': "B direction",
#                 'widget': QtWidgets.QLineEdit(''),
#             },
#             'B_str': {
#                 'display_text': "B Strength",
#                 'widget': SpinBox(value=0, int=True, bounds=(None, None), dec=True),
#             },
#             'log_plot': {
#                 'display_text': "Log Plot",
#                 'widget': QtWidgets.QCheckBox('Log Plot'),
#             },
#             'data_save': {
#                 'display_text': "Data Save",
#                 'widget': QtWidgets.QCheckBox('Data Save'),
#             },
#             'plot_save': {
#                 'display_text': "Plot Save",
#                 'widget': QtWidgets.QCheckBox('Plot Save'),
#             },
#             'plot': {
#                 'display_text': "Plot",
#                 'widget': QtWidgets.QCheckBox('Plot')
#             },
#         }
#         print(dir(FittingDataWidget))
#         # Import and assign the module object
#         import template.gui.elements
#         module = template.gui.elements

#         cls = "FittingDataWidget"
#         fun_name = "fit_fun"
        
#         # Call parent constructor
#         super().__init__(params_config, module, cls, fun_name)
            
#         self.hide_run_stop_buttons()


#         # Get the existing layout from the parent class
#         layout = self.layout()

        
#         # for param_name, param_config in self.params_config.items():
#         #     widget = param_config['widget']
#         #     widget.setObjectName(param_name)  # Set the object name to the parameter name
#         #     layout.addWidget(widget)  # Add widget to the layout
            
            
#         # Add a "Fit" button
#         self.fit_button = QtWidgets.QPushButton("Fit")
#         self.fit_button.clicked.connect(self.fit_fun)  # Connect button to function
#         layout.addWidget(self.fit_button)  # Add the button to the layout

        
#     def hide_run_stop_buttons(self):
#         # Iterate through all QPushButton widgets and hide the ones with "Run" and "Stop" text
#         for widget in self.findChildren(QtWidgets.QPushButton):
#             if widget.text() == "Run" or widget.text() == "Stop":
#                 widget.setVisible(False)
    
#     def fit_fun(self):
#         print(self.findChild(QtWidgets.QLineEdit,'fit_type'))
#         """This is the method that will be run by the nspyre run button."""
#         # fit_type = self.findChild(QtWidgets.QLineEdit, "fit_type").text()
#         # units = self.findChild(QtWidgets.QLineEdit, "units").text()
#         # measurement = self.findChild(QtWidgets.QLineEdit, "measurement").text()
#         # B_dir = self.findChild(QtWidgets.QLineEdit, "B_dir").text()
#         # B_str = self.findChild(SpinBox, "B_str").value()  # For SpinBox widget
#         # log_plot = self.findChild(QtWidgets.QCheckBox, "log_plot").isChecked()
#         # data_save = self.findChild(QtWidgets.QCheckBox, "data_save").isChecked()
#         # plot_save = self.findChild(QtWidgets.QCheckBox, "plot_save").isChecked()
#         # plot = self.findChild(QtWidgets.QCheckBox, "plot").isChecked()

#         # You can perform the fitting logic here
#         # print(f"Running fitting with params: {fit_type}, {units}, {measurement}, {B_dir}, {B_str}, {log_plot}, {data_save}, {plot_save}, {plot}")











