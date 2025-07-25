from pyqtgraph.Qt import QtWidgets
import pyqtgraph as pg
from PyQt6.QtGui import QColor
from nspyre import cyclic_colors
from typing import List, Tuple

class PlotColorManager:
    """Class to manage plot color schemes between light and dark modes."""
    
    def __init__(self, plot_widget):
        """
        Initialize the plot color manager.
        
        Args:
            plot_widget: The plot widget to manage colors for
        """
        self.plot_widget = plot_widget
        self.color_list = cyclic_colors
        self.setup_color_controls()
        
    def setup_color_controls(self) -> None:
        """Set up the color control buttons and stacked widget."""
        self.color_flip_button = QtWidgets.QStackedWidget()
        self.light_plot_button = QtWidgets.QPushButton("Light Plot Mode")
        self.dark_plot_button = QtWidgets.QPushButton("Dark Plot Mode")
        
        self.light_plot_button.clicked.connect(self.light_plot)
        self.dark_plot_button.clicked.connect(self.dark_plot)
        
        # Add buttons to stacked widget
        self.color_flip_button.addWidget(self.light_plot_button)
        self.color_flip_button.addWidget(self.dark_plot_button)
        
        
    def get_plot_items(self):
        """Get all plot items in the plot widget."""
        return self.plot_widget.line_plot.plot_widget.items()

    def get_current_plot_colors(self) -> List[Tuple[int, int, int, int]]:
        """
        Get the colors currently being used by plot items using pen color attributes.
        
        Returns:
            List[Tuple[int, int, int, int]]: List of RGBA color tuples currently used in plots
        """
        colors = []
        for item in self.get_plot_items():
            if isinstance(item, pg.PlotDataItem):
                pen = item.opts['pen']
                if type(pen) == QColor:
                    colors.append(pen)
        return colors if colors else self.color_list
    
    def light_plot(self) -> None:
        """Switch to light plot mode."""
        self.color_list = self.get_current_plot_colors()  # Get colors when button clicked
        self.plot_widget.line_plot.plot_widget.setBackground('white')
        item_counter = 0
        for item in self.get_plot_items():
            if isinstance(item, pg.PlotDataItem):
                item.setPen(pg.mkPen(color=self.color_list[item_counter], width=5))
                item.setSymbolBrush(pg.mkBrush(color=(10, 10, 10, 100)))
                item.setSymbolSize(0)
                item_counter += 1
        self.color_flip_button.setCurrentIndex(1)
    
    def dark_plot(self) -> None:
        """Switch to dark plot mode."""
        self.plot_widget.line_plot.plot_widget.setBackground('k')
        item_counter = 0
        for item in self.get_plot_items():
            if isinstance(item, pg.PlotDataItem):
                item.setPen(pg.mkPen(color=self.color_list[item_counter], width=1))
                item.setSymbolBrush(pg.mkBrush(color=(240, 240, 240, 100)))
                item.setSymbolSize(5)
                item_counter += 1
        self.color_flip_button.setCurrentIndex(0)


