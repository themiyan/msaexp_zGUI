"""
Main Redshift GUI application class.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import logging
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import pyqtSignal, QSize, Qt
from PyQt5.QtGui import QResizeEvent, QKeyEvent, QKeySequence

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
        self.setGeometry(100, 100, 1600, 900)  # Set default window size

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

    def resizeEvent(self, a0: QResizeEvent):
        """
        Handle window resize events.
        
        Args:
            a0 (QResizeEvent): The resize event
        """
        # Call the parent implementation first
        super().resizeEvent(a0)
        
        # Update image scaling based on new sizes
        update_display(self)
        
    def closeEvent(self, a0):
        """
        Handle window close event.
        
        Args:
            a0: The close event
        
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

    def keyPressEvent(self, a0: QKeyEvent):
        """
        Handle keyboard shortcuts.
        
        Args:
            a0 (QKeyEvent): The key press event
        """
        key = a0.key()
        
        # Check for paste operation first
        if a0.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            text_content = clipboard.text()
            try:
                parts = []
                if ',' in text_content:
                    parts = [p.strip() for p in text_content.split(',')]
                elif '\t' in text_content:
                    parts = [p.strip() for p in text_content.split('\t')]
                else:
                    parts = [p.strip() for p in text_content.split()]
                
                numbers = [float(p) for p in parts if p]
                
                if len(numbers) == 2 and hasattr(self, 'z_min') and hasattr(self, 'z_max'):
                    self.z_min.setValue(numbers[0])
                    self.z_max.setValue(numbers[1])
                    logging.info(f"Pasted z_min: {numbers[0]}, z_max: {numbers[1]}")
                    a0.accept()
                    return
                elif len(numbers) == 1:
                    self.current_z = numbers[0]
                    from event_handlers import update_display
                    update_display(self)
                    logging.info(f"Pasted single value as current_z: {self.current_z}")
                    a0.accept()
                    return
            except ValueError:
                logging.debug("Failed to parse clipboard content as numbers")
        
        # Navigation shortcuts
        if key == Qt.Key.Key_N:
            from event_handlers import on_next_spectrum
            on_next_spectrum(self)
        elif key == Qt.Key.Key_P:
            from event_handlers import on_previous_spectrum
            on_previous_spectrum(self)
        elif key == Qt.Key.Key_F:
            from event_handlers import on_refit_redshift
            on_refit_redshift(self)
        elif key == Qt.Key.Key_1:
            self.z_conf_combo.setCurrentIndex(0)
        elif key == Qt.Key.Key_2:
            self.z_conf_combo.setCurrentIndex(1)
        elif key == Qt.Key.Key_3:
            self.z_conf_combo.setCurrentIndex(2)
        elif key == Qt.Key.Key_9:
            self.z_conf_combo.setCurrentIndex(3)
        else:
            # Pass any unhandled keys to the parent class
            super().keyPressEvent(a0)
