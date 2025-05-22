"""
Main Redshift GUI application class.
"""
import logging
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import pyqtSignal, QSize
from PyQt5.QtGui import QResizeEvent

# Import our modules
from config import DARK_THEME_STYLESHEET
from ui_components import (
    setup_central_widget, setup_file_controls, 
    setup_image_display, setup_redshift_controls
)
from visualization import create_chi2_figure
from event_handlers import connect_events, update_display

class RedshiftGUI(QMainWindow):
    """
    Main GUI class for the Redshift Fitting application.
    """
    # Define signals for thread-safe updates
    update_status_signal = pyqtSignal(str)
    show_message_signal = pyqtSignal(str, str)  # For thread-safe QMessageBox

    def __init__(self):
        """Initialize the Redshift GUI application."""
        super().__init__()
        self.setWindowTitle("Redshift Fitting GUI")
        self.setGeometry(100, 100, 1600, 900)  # Increased default size

        # Initialize state attributes
        self.spectrum_files = []
        self.current_index = -1
        self.yaml_data = None
        self.current_z = None
        self.z_conf_value = 1  # Default z_conf
        self.comment_value = ""  # Default comment
        self.redshift_df = None  # To store redshift guesses from CSV

        # Create Matplotlib figure and canvas for chi-squared plot
        self.chi2_figure, self.chi2_canvas, self.chi2_ax = create_chi2_figure()
        
        # Initialize image data attributes
        self.zfit_pixmap = None
        self.s2d_pixmap = None
        self.galaxy_pixmap = None

        # Initialize Matplotlib event connection IDs
        self.chi2_motion_cid = None
        self.chi2_click_cid = None

        # Set up the UI
        self.apply_theme()
        self.initialize_ui()
        
        # Connect signals
        self.update_status_signal.connect(self.status_label.setText)
        self.show_message_signal.connect(self.show_message_dialog)

    def apply_theme(self):
        """Apply the UI theme."""
        try:
            self.setStyleSheet(DARK_THEME_STYLESHEET)
        except Exception as e:
            logging.error(f"Error setting UI theme: {str(e)}")

    def initialize_ui(self):
        """Initialize all UI components."""
        # Set up the main layout
        setup_central_widget(self)
        
        # Set up UI components
        setup_file_controls(self)
        setup_image_display(self)
        setup_redshift_controls(self)
        
        # Connect event handlers
        connect_events(self)
        
        # Initialize with empty state
        update_display(self)

    def show_message_dialog(self, title, message):
        """
        Show a message dialog.
        
        Args:
            title (str): Dialog title
            message (str): Dialog message
        """
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, title, message)

    def resizeEvent(self, event: QResizeEvent):
        """
        Handle window resize events.
        
        Args:
            event (QResizeEvent): The resize event
        """
        # Call the parent implementation first
        super().resizeEvent(event)
        
        # Update image scaling based on new sizes
        update_display(self)
        
    def closeEvent(self, event):
        """
        Handle window close event.
        
        Args:
            event: The close event
        """
        # Check if there are unsaved changes
        if self.yaml_data and (
            self.yaml_data.get('z_conf') != self.z_conf_value or 
            self.yaml_data.get('comment') != self.comment_value
        ):
            from PyQt5.QtWidgets import QMessageBox
            from event_handlers import on_save_metadata
            
            reply = QMessageBox.question(
                self, "Save Changes?",
                "Do you want to save changes before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Yes:
                on_save_metadata(self, show_popup=False)
        
        # Accept the close event (close the window)
        event.accept()
