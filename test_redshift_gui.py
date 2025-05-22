import os
import sys
import yaml
import glob
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QDoubleSpinBox,
                             QFileDialog, QMessageBox, QProgressBar, QCheckBox,
                             QScrollArea, QSizePolicy, QComboBox, QTextEdit)
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QKeySequence, QKeyEvent, QResizeEvent, QCloseEvent
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from astropy.visualization import ZScaleInterval
import matplotlib.pyplot as plt
from msaexp.spectrum import fit_redshift
from jwst.datamodels import open as dm_open
import requests
from io import BytesIO
import tempfile
import threading
import logging
from PIL import Image
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

logging.basicConfig(level=logging.INFO)

REDSHIFT_GUESS_LOWER_FACTOR = 0.95
REDSHIFT_GUESS_UPPER_FACTOR = 1.05
DEFAULT_Z_MIN = 0.0
DEFAULT_Z_MAX = 10.0

class RedshiftGUI(QMainWindow):
    update_status_signal = pyqtSignal(str)
    show_message_signal = pyqtSignal(str, str) # For thread-safe QMessageBox

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Redshift Fitting GUI")
        self.setGeometry(100, 100, 1600, 900) # Increased default size

        # Initialize attributes
        self.spectrum_files = []
        self.current_index = -1
        self.yaml_data = None
        self.current_z = None
        self.z_conf_value = 1 # Default z_conf
        self.comment_value = "" # Default comment
        self.redshift_df = None # To store redshift guesses from CSV

        # Matplotlib figure and canvas for chi-squared plot
        self.chi2_figure = Figure(figsize=(5, 4), dpi=100)
        self.chi2_canvas = FigureCanvasQTAgg(self.chi2_figure)
        self.chi2_ax = self.chi2_figure.add_subplot(111)
        self.chi2_ax.set_navigate(False) # Disable default Matplotlib navigation for this axes
        
        self.zfit_pixmap = None
        self.s2d_pixmap = None
        self.galaxy_pixmap = None  # To store the galaxy cutout image

        # Initialize Matplotlib event connection IDs
        self.chi2_motion_cid = None
        self.chi2_click_cid = None
        
        self.set_theme()
        self.init_ui() 
        self.update_status_signal.connect(self.status_label.setText)
        self.show_message_signal.connect(self.show_message_dialog)

        # Connect Matplotlib canvas events
        if self.chi2_canvas:
            self.chi2_motion_cid = self.chi2_canvas.mpl_connect('motion_notify_event', self.on_chi2_canvas_motion)
            self.chi2_click_cid = self.chi2_canvas.mpl_connect('button_press_event', self.on_chi2_canvas_click)

    def init_ui(self):
        # Create the main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create scroll area for image display
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.scroll_widget.setObjectName("scrollWidget")
        
        # Add file selection controls
        self.setup_file_controls()
        
        # Add image display area
        self.setup_image_display()
        
        # Add redshift controls
        self.setup_redshift_controls()
        
        # Status display
        self.status_label = QLabel("Ready")
        self.main_layout.addWidget(self.status_label)
        
        # Add scroll area to main layout
        self.main_layout.addWidget(self.scroll_area)
        
        # Initialize with empty state
        self.update_display()

    # HELPER METHODS FOR REDUCING REPETITION
    
    def configure_layout(self, layout, margins=(0, 0, 0, 0), spacing=5):
        """Helper to configure layout margins and spacing consistently"""
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        return layout
    
    def create_header_label(self, text):
        """Create a consistently styled header label"""
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label
    
    def create_image_label(self):
        """Create a consistently styled image display label"""
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return label
    
    def scale_pixmap(self, pixmap, width, height, keep_aspect=True):
        """Scale a pixmap with consistent options"""
        if pixmap and not pixmap.isNull():
            aspect_ratio_mode = Qt.AspectRatioMode.KeepAspectRatio if keep_aspect else Qt.AspectRatioMode.IgnoreAspectRatio
            return pixmap.scaled(
                width, height,
                aspect_ratio_mode, Qt.TransformationMode.SmoothTransformation
            )
        return None
    
    def get_related_files(self, spectrum_file):
        """Get the related file paths for a spectrum file"""
        base_name = os.path.splitext(spectrum_file)[0]
        return {
            'chi2': f"{base_name}.chi2.png",
            'zfit': f"{base_name}.zfit.png",
            'yaml': f"{base_name}.zfit.yaml",
            's2d': spectrum_file.replace("o1d.fits", "s2d.fits")
        }
    
    def all_files_exist(self, files_list):
        """Check if all files in a list exist"""
        return all(os.path.exists(f) for f in files_list)
    
    def show_confirmation(self, title, message, default=QMessageBox.Yes):
        """Show a Yes/No confirmation dialog"""
        return QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No, default
        )
    
    def handle_error(self, operation, error, show_dialog=True):
        """Standardized error handling"""
        error_msg = f"Error {operation}: {str(error)}"
        print(error_msg)
        if show_dialog:
            QMessageBox.warning(self, "Error", error_msg)
        self.status_label.setText("Error")
        
    def extract_ids_from_filename(self, filename):
        """Extract observation ID and galaxy ID from filename"""
        base_name = os.path.basename(os.path.splitext(filename)[0])
        try:
            gal_id = int(base_name.split("_")[1].replace("s", ""))  # Extract galaxy ID
            obs_id = int(base_name.split("_")[0].split("-")[-1].replace("o", ""))  # Extract observation ID
            return obs_id, gal_id
        except (IndexError, ValueError) as e:
            self.handle_error("extracting IDs from filename", e, False)
            return None, None
    
    def get_redshift_guess_from_csv(self, spectrum_file):
        """
        Get the redshift guess from the stored CSV data for a spectrum file.
        Returns None if no matching entry is found or no CSV data is loaded.
        """
        if self.redshift_df is None:
            return None
            
        # Extract observation ID and galaxy ID from filename
        obs_id, gal_id = self.extract_ids_from_filename(spectrum_file)
        
        if obs_id is None or gal_id is None:
            return None
            
        try:
            # Filter DataFrame for matching observation ID
            df_obs = self.redshift_df.query(f"obsid == {obs_id}")
            if df_obs.empty:
                return None
            
            # Search for matching galaxy ID in the filtered DataFrame
            matching_row = df_obs[df_obs["objid"] == gal_id]
            
            if not matching_row.empty and "specz" in matching_row.columns:
                return float(matching_row["specz"].iloc[0])
        except Exception as e:
            print(f"Error getting redshift guess from CSV: {str(e)}")
            
        return None
    
    def show_message_dialog(self, title, message):
        QMessageBox.information(self, title, message)
    
    def set_theme(self):
        """Set up a modern UI theme"""
        try:
            # Modern dark theme with blue accents
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #292E3C;
                    color: #E0E0E0;
                }
                QLabel {
                    color: #E0E0E0;
                    font-weight: bold;
                    padding: 2px;
                    border-radius: 3px;
                }
                QLabel#header {
                    font-size: 14px;
                    color: #62AAFF;
                }
                QPushButton {
                    background-color: #4A6DB5;
                    color: white;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background-color: #5A7DC5;
                }
                QPushButton:pressed {
                    background-color: #3A5DA5;
                }
                QPushButton:disabled {
                    background-color: #3A4055;
                    color: #808080;
                }
                QDoubleSpinBox, QComboBox, QTextEdit {
                    background-color: #383E50;
                    color: #E0E0E0;
                    border: 1px solid #5A6374;
                    border-radius: 3px;
                    padding: 2px;
                    min-height: 20px;
                }
                QComboBox {
                    min-width: 80px;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 15px;
                    border-left: 1px solid #5A6374;
                }
                QComboBox::down-arrow {
                    image: none;
                    width: 10px;
                    height: 10px;
                    background-color: #E0E0E0;
                }
                QComboBox QAbstractItemView {
                    background-color: #383E50;
                    color: #E0E0E0;
                    selection-background-color: #4A6DB5;
                    selection-color: #FFFFFF;
                    border: 2px solid #5A6374;
                    font-weight: bold;
                    padding: 5px;
                    outline: none;
                }
                QComboBox QAbstractItemView::item {
                    min-height: 20px;
                    padding: 5px;
                }
                QScrollArea {
                    background-color: #292E3C;
                    border: 1px solid #383E50;
                    border-radius: 3px;
                }
                QWidget#scrollWidget {
                    background-color: #292E3C;
                }
            """)
        except Exception as e:
            self.handle_error("setting UI theme", e, False)
    
    def setup_file_controls(self):
        file_layout = QHBoxLayout()
    
        # Button to select directory
        self.select_dir_button = QPushButton("Select Directory")
        self.select_dir_button.clicked.connect(self.select_directory)
        file_layout.addWidget(self.select_dir_button)
        
        # Label to show current file
        self.file_label = QLabel("No files selected")
        file_layout.addWidget(self.file_label)
        
        # New button to run batch fit for all missing redshift solutions
        self.batch_fit_button = QPushButton("Run Fit on All Missing")
        self.batch_fit_button.clicked.connect(self.batch_run_missing_fits)
        file_layout.addWidget(self.batch_fit_button)
        
        # New button to upload CSV with redshift guesses
        self.upload_csv_button = QPushButton("Upload Redshift CSV")
        self.upload_csv_button.clicked.connect(self.upload_redshift_csv)
        file_layout.addWidget(self.upload_csv_button)
        
        # Add to main layout
        self.scroll_layout.addLayout(file_layout)
    
    def reset_chi2_view(self):
        """Reset chi-squared plot to original view (no zoom)"""
        if self.chi2_ax:
            self.chi2_ax.autoscale(True)
            self.chi2_ax.relim()
            self.chi2_ax.autoscale_view() # Ensure the view is updated
            if self.chi2_canvas:
                self.chi2_canvas.draw_idle() # Use draw_idle
    
    def setup_image_display(self):
        """
        Set up the image display with a horizontal layout:
        - Chi-squared plot on the left (20% width)
        - 2D and 1D spectrum plots stacked vertically on the right (80% width)
        """
        image_layout = QHBoxLayout()
        self.configure_layout(image_layout, spacing=5)
        
        # Create left side layout for file dropdown and chi2 plot
        chi2_layout = QVBoxLayout()
        self.configure_layout(chi2_layout)
        
        # Add file dropdown at the top of the left side
        dropdown_layout = QHBoxLayout()
        dropdown_layout.addWidget(QLabel("Select File:"))
        self.file_dropdown = QComboBox()
        self.file_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_dropdown.setMinimumWidth(200)  # Make dropdown reasonably wide
        self.file_dropdown.currentIndexChanged.connect(self.on_file_selected)
        dropdown_layout.addWidget(self.file_dropdown)
        chi2_layout.addLayout(dropdown_layout)

        # Add galaxy image panel between dropdown and chi2 plot
        self.galaxy_label = self.create_header_label("Galaxy Image")
        self.galaxy_image = self.create_image_label()
        self.galaxy_image.setFixedHeight(200)  # Fixed height for the galaxy image
        self.galaxy_image.setAlignment(Qt.AlignCenter)
        
        chi2_layout.addWidget(self.galaxy_label)
        chi2_layout.addWidget(self.galaxy_image)
        
        # Add chi-squared plot below the dropdown
        self.chi2_label = self.create_header_label("Chi-squared vs Redshift")
        
        # self.chi2_figure, self.chi2_canvas, self.chi2_ax are already initialized in __init__
        self.chi2_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        chi2_layout.addWidget(self.chi2_label)
        chi2_layout.addWidget(self.chi2_canvas) 
        
        image_layout.addLayout(chi2_layout, 20)
        
        # Add a reset view button for chi-squared plot
        reset_view_button = QPushButton("Reset View")
        reset_view_button.clicked.connect(self.reset_chi2_view)
        chi2_layout.addWidget(reset_view_button)
        
        # === RIGHT SIDE: Vertical layout for 2D and 1D spectrum (80% of horizontal space) ===
        right_layout = QVBoxLayout()
        self.configure_layout(right_layout, spacing=5)
        
        # 2D spectrum plot (30% of vertical space on right side)
        self.s2d_label = self.create_header_label("2D Spectrum")
        self.s2d_image = self.create_image_label()
        # self.s2d_image.setScaledContents(True) # Removed, will do manual scaling
        
        s2d_layout = QVBoxLayout()
        self.configure_layout(s2d_layout)
        s2d_layout.addWidget(self.s2d_label)
        s2d_layout.addWidget(self.s2d_image)
        
        # Add 2D spectrum layout to right layout with 30% of vertical space
        right_layout.addLayout(s2d_layout, 30)
        
        # 1D spectrum plot (70% of vertical space on right side)
        self.zfit_label = self.create_header_label("Spectrum Fit")
        self.zfit_image = self.create_image_label()
        # self.zfit_image.setScaledContents(True) # Removed, will do manual scaling
        
        zfit_layout = QVBoxLayout()
        self.configure_layout(zfit_layout)
        zfit_layout.addWidget(self.zfit_label)
        zfit_layout.addWidget(self.zfit_image)
        
        # Add 1D spectrum layout to right layout with 70% of vertical space
        right_layout.addLayout(zfit_layout, 70)
        
        # Add right layout to main image layout with 80% of horizontal space
        image_layout.addLayout(right_layout, 80)
        
        # Add to main layout
        self.scroll_layout.addLayout(image_layout)
    
    def setup_redshift_controls(self):
        # Create layout for redshift controls
        redshift_layout = QHBoxLayout()
        
        # Current redshift display
        self.z_label = QLabel("Best fit z:")
        redshift_layout.addWidget(self.z_label)
        
        self.z_value = QLabel("N/A")
        redshift_layout.addWidget(self.z_value)
        
        # Min/max z for refitting
        redshift_layout.addWidget(QLabel("New z range:"))
        
        self.z_min = QDoubleSpinBox()
        self.z_min.setRange(0.0, 20.0)
        self.z_min.setDecimals(3)
        self.z_min.setSingleStep(0.1)
        self.z_min.setValue(0.0)
        redshift_layout.addWidget(self.z_min)
        
        redshift_layout.addWidget(QLabel("to"))
        
        self.z_max = QDoubleSpinBox()
        self.z_max.setRange(0.0, 20.0)
        self.z_max.setDecimals(3)
        self.z_max.setSingleStep(0.1)
        self.z_max.setValue(10.0)
        redshift_layout.addWidget(self.z_max)
        
        # Refit button
        self.refit_button = QPushButton("Refit Redshift")
        self.refit_button.clicked.connect(self.refit_redshift)
        redshift_layout.addWidget(self.refit_button)
        
        # Navigation buttons
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_spectrum)
        redshift_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_spectrum)
        redshift_layout.addWidget(self.next_button)
        
        # Add to main layout
        self.scroll_layout.addLayout(redshift_layout)
        
        # Add z_conf and comment controls in a new layout
        quality_layout = QHBoxLayout()
        
        # Redshift quality (z_conf) dropdown
        quality_layout.addWidget(QLabel("Redshift Quality:"))
        self.z_conf_combo = QComboBox()
        # Add items individually with explicit text
        self.z_conf_combo.addItem("1")
        self.z_conf_combo.addItem("2")
        self.z_conf_combo.addItem("3")
        self.z_conf_combo.addItem("9")  # New quality option added
        self.z_conf_combo.setCurrentIndex(0)  # Default to 1
        self.z_conf_combo.currentIndexChanged.connect(self.update_z_conf)
        # Set explicit size policy and minimum width to ensure dropdown is visible
        self.z_conf_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.z_conf_combo.setMinimumWidth(80)
        quality_layout.addWidget(self.z_conf_combo)
        
        # Comment field
        quality_layout.addWidget(QLabel("Comment:"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(60)  # Limit height
        self.comment_edit.textChanged.connect(self.update_comment)
        quality_layout.addWidget(self.comment_edit)
        
        # Save button
        self.save_button = QPushButton("Save Metadata")
        self.save_button.clicked.connect(lambda: self.save_metadata(True))
        quality_layout.addWidget(self.save_button)
        
        # Add to main layout
        self.scroll_layout.addLayout(quality_layout)
    
    def select_directory(self):
        """Open a directory dialog and find all FITS files in it"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        
        if directory:
            # Find all FITS files in this directory
            fits_files = glob.glob(os.path.join(directory, "*o1d.fits"))
            
            if fits_files:
                print(f"Found {len(fits_files)} FITS files in {directory}")
                self.spectrum_files = sorted(fits_files)
                self.current_index = 0
                self.update_file_dropdown()  # Update the file dropdown with new files
                self.load_current_spectrum()
            else:
                QMessageBox.information(self, "No FITS Files", f"No FITS files found in {directory}")
    
    def find_existing_results(self, spectrum_file):
        """Find existing redshift fit results for a file.
        Chi2 plot is generated from yaml, so chi2.png is not strictly needed for display.
        """
        related_files = self.get_related_files(spectrum_file)
        
        # We need zfit.png for the plot and zfit.yaml for chi2 data and metadata
        if os.path.exists(related_files['zfit']) and os.path.exists(related_files['yaml']):
            return related_files['zfit'], related_files['yaml']
        
        return None, None
  
    def load_current_spectrum(self):
        """Load the current spectrum and its redshift fit results"""
        if not self.spectrum_files or self.current_index >= len(self.spectrum_files):
            return

        spectrum_file = self.spectrum_files[self.current_index]
        self.file_label.setText(f"File {self.current_index + 1}/{len(self.spectrum_files)}: {os.path.basename(spectrum_file)}")
        
        # Update dropdown selection to match the current index
        if hasattr(self, 'file_dropdown') and 0 <= self.current_index < len(self.spectrum_files):
            # Temporarily disconnect signal to avoid triggering on_file_selected
            self.file_dropdown.blockSignals(True)
            self.file_dropdown.setCurrentIndex(self.current_index)
            self.file_dropdown.blockSignals(False)

        # Clear previous state
        if self.chi2_ax:
            self.chi2_ax.clear()
            if self.chi2_canvas: # Draw cleared axes
                self.chi2_canvas.draw_idle()
        
        self.zfit_pixmap = None
        self.s2d_pixmap = None
        self.galaxy_pixmap = None
        self.current_z = None
        self.yaml_data = None # Clear YAML data for the new spectrum
        self.update_display() # Update UI to reflect cleared state

        # Load the 2D spectrum
        related_files = self.get_related_files(spectrum_file)
        s2d_file = related_files['s2d']
        
        if os.path.exists(s2d_file):
            try:
                with dm_open(s2d_file) as model:
                    data = model.data  # JWST spec model data
                    zscale = ZScaleInterval()
                    vmin, vmax = zscale.get_limits(data)

                    # Get the WCS information from the model metadata
                    alpha_C, delta_C, yinfo = model.meta.wcs(np.arange(0,model.data.shape[1]), np.zeros_like(model.data.shape[1]))
                    wavelength = yinfo
                    
                    # Extract RA and Dec from the model metadata for galaxy image
                    ra = model.source_ra
                    dec = model.source_dec
                    metafile= model.meta.instrument.msa_metadata_file.split('_')[0]
                    
                    if ra is not None and dec is not None:
                        # Fetch galaxy image from Grizli server
                        self.galaxy_pixmap = self.fetch_galaxy_image(ra, dec, metafile=metafile)
                        if self.galaxy_pixmap and not self.galaxy_pixmap.isNull():
                            # Update the galaxy image display
                            self.galaxy_image.setPixmap(self.galaxy_pixmap.scaled(
                                self.galaxy_image.width(),
                                self.galaxy_image.height(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation))
                        else:
                            self.galaxy_image.setText("Galaxy Image N/A")
                    else:
                        self.galaxy_image.setText("RA/Dec not found in metadata")

                    # Define extent so that imshow will display wavelength ticks on the x-axis
                    extent = [wavelength[0], wavelength[-1], 0, model.data.shape[0]]

                    # Create a figure, add axis labels, a colorbar, and save the image with extent
                    fig, ax = plt.subplots(figsize=(20, 3))

                    im = ax.imshow(data, origin='lower', vmin=vmin, vmax=vmax, cmap="gray")
                    
                    # Add green dashed grid lines
                    ax.grid(True, color='green', linestyle='--', linewidth=0.5)
                    
                    tick_positions = np.arange(0, len(wavelength), 50)
                    ax.set_xticks(tick_positions)
                    ax.set_xticklabels(np.round(wavelength[tick_positions], 2))
                    ax.set_xlabel("Wavelength (microns)")
                    ax.set_ylabel("Spatial")
                    
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                        fig.savefig(tmpfile.name)
                        self.s2d_pixmap = QPixmap(tmpfile.name)
                    plt.close(fig)
                    os.unlink(tmpfile.name)  # Delete the temporary file after loading pixmap
                    
                    # We'll scale this in update_display to match the zfit_image width
                    self.s2d_image.setPixmap(self.s2d_pixmap)
            except Exception as e:
                self.handle_error("loading 2D spectrum", e, False)

        # Check if redshift fit results already exist
        zfit_file, yaml_file = self.find_existing_results(spectrum_file) # Updated unpacking

        if zfit_file and yaml_file: # Updated condition
            # Load existing results
            self.load_fit_results(zfit_file, yaml_file) # Updated call
            return

        # Check if there's a CSV-based redshift guess for this spectrum
        redshift_guess = self.get_redshift_guess_from_csv(spectrum_file)
        
        if redshift_guess is not None:
            # We have a guess from the CSV - ask if the user wants to use it
            z_min = redshift_guess * REDSHIFT_GUESS_LOWER_FACTOR
            z_max = redshift_guess * REDSHIFT_GUESS_UPPER_FACTOR
            
            reply = self.show_confirmation(
                "Run Redshift Fit",
                f"No existing results. Found redshift guess {redshift_guess:.4f} in CSV. "
                f"Run fitting with range {z_min:.4f}-{z_max:.4f}?",
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.z_min.setValue(z_min)
                self.z_max.setValue(z_max)
                self.run_direct_fit(spectrum_file, z_min, z_max)
            return
        
        # No CSV guess, ask about default range
        reply = self.show_confirmation(
            "Run Redshift Fit",
            f"Redshift fit results not found for {os.path.basename(spectrum_file)}. Run fitting?",
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # Set default z range to 0-10 for first-time fits
            self.z_min.setValue(DEFAULT_Z_MIN)
            self.z_max.setValue(DEFAULT_Z_MAX)
            
            # Get the values from the UI
            z_min = self.z_min.value()
            z_max = self.z_max.value()

            # Run fit directly
            self.run_direct_fit(spectrum_file, z_min, z_max)
    
    def load_fit_results(self, zfit_file, yaml_file): # Updated signature
        """Load existing redshift fit results"""
        self.yaml_data = None # Clear previous YAML data before loading new one

        try:
            if os.path.exists(yaml_file):
                with open(yaml_file, 'r') as f_yaml:
                    self.yaml_data = yaml.safe_load(f_yaml)
            
            # Plot Chi-squared from YAML data
            if self.chi2_ax:
                self.chi2_ax.clear()
                if self.yaml_data and \
                   'zg1' in self.yaml_data and isinstance(self.yaml_data.get('zg1'), list) and \
                   'chi1' in self.yaml_data and isinstance(self.yaml_data.get('chi1'), list) and \
                   len(self.yaml_data['zg1']) > 0 and \
                   len(self.yaml_data['zg1']) == len(self.yaml_data['chi1']):
                    self.chi2_ax.plot(self.yaml_data['zg0'], self.yaml_data['chi0'], label=r'data')
                    self.chi2_ax.plot(self.yaml_data['zg1'], self.yaml_data['chi1'], label=r'$\chi^2$ ')
                    self.chi2_ax.set_xlabel("Redshift (z)")
                    self.chi2_ax.set_ylabel(r"$\chi^2$") # Raw string for chi-squared symbol
                    self.chi2_ax.set_title(rf"$\chi^2$ for {os.path.basename(yaml_file)}") # Raw string for title
                    self.chi2_ax.legend()
                    self.chi2_ax.relim()
                    self.chi2_ax.autoscale_view()
                else:
                    msg = f"Problem with $\chi^2$ data in\n{os.path.basename(yaml_file)}"
                    if not os.path.exists(yaml_file):
                        msg = f"YAML file not found:\n{os.path.basename(yaml_file)}"
                    elif not self.yaml_data:
                        msg = f"YAML empty or invalid:\n{os.path.basename(yaml_file)}"
                    self.chi2_ax.text(0.5, 0.5, msg, ha='center', va='center', transform=self.chi2_ax.transAxes)
            
            if self.chi2_canvas:
                self.chi2_canvas.draw_idle()

            # Load zfit pixmap
            self.zfit_pixmap = None # Clear previous
            if os.path.exists(zfit_file):
                self.zfit_pixmap = QPixmap(zfit_file)
                if self.zfit_pixmap.isNull():
                    print(f"Failed to load zfit image: {zfit_file}")
                    self.zfit_pixmap = None 
            else:
                print(f"Zfit image not found: {zfit_file}")
        
            # Update current_z and other metadata from YAML
            if self.yaml_data:
                z_val = self.yaml_data.get('z')
                self.current_z = float(z_val) if z_val is not None else None
                self.z_conf_value = int(self.yaml_data.get('z_conf', 1))
                self.comment_value = self.yaml_data.get('comment', "")
            else: 
                self.current_z = None
                self.z_conf_value = 1
                self.comment_value = ""
            
            self.update_display()
            
        except Exception as e:
            self.handle_error(f"loading results for {os.path.basename(yaml_file)}", e)
            if self.chi2_ax: self.chi2_ax.clear()
            if self.chi2_canvas: self.chi2_canvas.draw_idle()
            self.zfit_pixmap = None
            self.current_z = None
            self.update_display() # Reflect error state in UI
    
    def run_direct_fit(self, spectrum_file, z_min=0.0, z_max=10.0):
        """Run the redshift fitting directly in the main thread"""
        try:
            self.status_label.setText(f"Processing {os.path.basename(spectrum_file)}...")
            QApplication.processEvents()  # Update the UI
            
            # Run fit_redshift (assuming it writes .zfit.png and .zfit.yaml files)
            # The returned 'data' is assumed to be the YAML content, but we'll load from file
            # for consistency with load_fit_results.
            # fit_redshift might return chi2_file, zfit_file, yaml_data_dict
            # We primarily need the paths to the generated zfit_file and yaml_file.
            fit_redshift( # Discard return values if not directly used, rely on file creation
                spectrum_file,
                z0=[z_min, z_max],
                is_prism=True,
                use_full_dispersion=True
            )

            # Construct paths to the output files
            base_name = os.path.splitext(spectrum_file)[0]
            new_zfit_file = f"{base_name}.zfit.png"
            new_yaml_file = f"{base_name}.zfit.yaml"

            if os.path.exists(new_zfit_file) and os.path.exists(new_yaml_file):
                self.load_fit_results(new_zfit_file, new_yaml_file)
                self.status_label.setText(f"Fit complete for {os.path.basename(spectrum_file)}")
            else:
                self.handle_error(f"running fit for {os.path.basename(spectrum_file)}", 
                                  "Output files (zfit.png/yaml) not found after fit.")
                self.status_label.setText("Error: Fit output files missing.")
            
        except Exception as e:
            self.handle_error(f"running fit for {os.path.basename(spectrum_file)}", e)
            self.status_label.setText("Error during fit.")
    
    def update_display(self):
        """Update the display with current images and redshift"""
        # Clear image labels before attempting to set new content
        self.zfit_image.clear()
        self.s2d_image.clear()
        self.galaxy_image.clear()

        # Chi-squared plot is drawn directly on its canvas.
        # Ensure canvas is drawn if it exists and is visible
        if self.chi2_canvas and self.chi2_canvas.isVisible():
             self.chi2_canvas.draw_idle()

        # 1D spectrum (zfit_image)
        if self.zfit_pixmap and not self.zfit_pixmap.isNull():
            # For now, set directly. Proper scaling should be handled in resizeEvent
            # or by a dedicated method that considers the label's current size.
            self.zfit_image.setPixmap(self.zfit_pixmap)
        else:
            self.zfit_image.setText("Spectrum N/A")
            
        # 2D spectrum (s2d_image)
        if self.s2d_pixmap and not self.s2d_pixmap.isNull():
            self.s2d_image.setPixmap(self.s2d_pixmap)
        else:
            self.s2d_image.setText("2D Spectrum N/A")
            
        # Galaxy image
        if self.galaxy_pixmap and not self.galaxy_pixmap.isNull():
            self.galaxy_image.setPixmap(self.galaxy_pixmap.scaled(
                self.galaxy_image.width(), 
                self.galaxy_image.height(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation))
        else:
            self.galaxy_image.setText("Galaxy Image N/A")
        
        # Update redshift display
        self.z_value.setText(f"{self.current_z:.4f}" if self.current_z is not None else "N/A")
        
        # Update z_conf combo
        conf_index = self.z_conf_combo.findText(str(self.z_conf_value))
        if conf_index != -1:
            self.z_conf_combo.setCurrentIndex(conf_index)
        else: # Default to first item (usually "1") if value not found
            self.z_conf_combo.setCurrentIndex(0) 
            
        self.comment_edit.setText(self.comment_value if self.comment_value is not None else "")

        # Enable/disable buttons based on state
        has_files = bool(self.spectrum_files)
        is_valid_index = -1 < self.current_index < len(self.spectrum_files) if has_files else False

        self.prev_button.setEnabled(has_files and self.current_index > 0)
        self.next_button.setEnabled(has_files and self.current_index < len(self.spectrum_files) - 1)
        self.refit_button.setEnabled(is_valid_index)
        # Enable save only if there's a current spectrum and a redshift value (implies YAML is loaded)
        self.save_button.setEnabled(is_valid_index and self.yaml_data is not None)

    
    def refit_redshift(self):
        """Refit the redshift with new z range"""
        if not self.spectrum_files or self.current_index >= len(self.spectrum_files):
            return
        
        z_min = self.z_min.value()
        z_max = self.z_max.value()
        
        if z_min >= z_max:
            QMessageBox.warning(self, "Invalid Range", "Minimum z must be less than maximum z")
            return
        
        # Run redshift fitting directly
        self.run_direct_fit(
            self.spectrum_files[self.current_index],
            z_min=z_min,
            z_max=z_max,
        )
    
    def previous_spectrum(self):
        """Move to the previous spectrum and save metadata"""
        if self.current_index > 0:
            # Save metadata for current spectrum before moving
            self.save_metadata(False)
            self.current_index -= 1
            self.load_current_spectrum()
    
    def next_spectrum(self):
        """Move to the next spectrum and save metadata"""
        if self.current_index < len(self.spectrum_files) - 1:
            # Save metadata for current spectrum before moving
            self.save_metadata(False)
            self.current_index += 1
            self.load_current_spectrum()
        elif self.spectrum_files:  # Only show message if there are files loaded
            # User is at the last file - show popup
            self.show_message_dialog("End of Files", "You have reached the end of all FITS files. All files have been looked at.")
    
    def resizeEvent(self, a0: QResizeEvent):
        """Handle window resize events"""
        super().resizeEvent(a0)
        # Add a small delay before updating display to ensure layout is settled
        QTimer.singleShot(50, self.update_display)
    
    def update_z_conf(self):
        current_text = self.z_conf_combo.currentText()
        try: # Add try-except for safety, though currentText should be valid
            self.z_conf_value = int(current_text)
        except ValueError:
            print(f"Warning: Could not convert z_conf '{current_text}' to int. Defaulting to 1.")
            self.z_conf_value = 1 # Default to a safe value
            self.z_conf_combo.setCurrentIndex(0) # Reset combo to '1'
    
    def update_comment(self):
        """Update the comment value when the text changes"""
        self.comment_value = self.comment_edit.toPlainText()
    
    def save_metadata(self, show_popup=True):
        """Save the current z_conf and comment to the YAML file"""
        if not self.spectrum_files or self.current_index >= len(self.spectrum_files):
            return # Added return if no spectrum files
        
        spectrum_file = self.spectrum_files[self.current_index]
        
        # Find the yaml file
        zfit_file, yaml_file = self.find_existing_results(spectrum_file)
        
        if not yaml_file or not os.path.exists(yaml_file):
            # If yaml_file doesn't exist, we might need to create it if self.yaml_data is populated
            # from a fresh fit. Let's use the expected path.
            related_files = self.get_related_files(spectrum_file)
            yaml_file = related_files['yaml'] # Expected path

        if self.yaml_data is None: # Check if yaml_data is populated
             if show_popup:
                QMessageBox.warning(self, "Error", "No YAML data to save. Perform a fit first.")
             return

        try:
            # Ensure yaml_data is a dictionary before updating
            if not isinstance(self.yaml_data, dict):
                if show_popup:
                    QMessageBox.warning(self, "Error", "YAML data is not in the correct format.")
                print(f"Error: yaml_data is not a dict: {type(self.yaml_data)}")
                return

            self.yaml_data['z_conf'] = self.z_conf_value
            self.yaml_data['comment'] = self.comment_value
            if self.current_z is not None: # Save selected z if available
                self.yaml_data['z_sel'] = float(self.current_z)
            
            # Save the yaml file
            with open(yaml_file, 'w') as f:
                yaml.dump(self.yaml_data, f, default_flow_style=False, sort_keys=False)
            
            if show_popup:
                QMessageBox.information(self, "Success", f"Metadata saved to {os.path.basename(yaml_file)}")
        except Exception as e:
            if show_popup:
                self.handle_error(f"saving metadata to {os.path.basename(yaml_file)}", e) 
            else:
                print(f"Error saving metadata silently to {os.path.basename(yaml_file)}: {str(e)}") 
                
    def on_chi2_canvas_motion(self, event):
        """Handle mouse motion over the chi-squared canvas to display coordinates."""
        if event.inaxes == self.chi2_ax:
            x_data, y_data = event.xdata, event.ydata
            if x_data is not None and y_data is not None:
                self.status_label.setText(f"Chi-squared: z={x_data:.4f}, chi2={y_data:.2f}")
        else:
            # Check if status_label exists before trying to set its text
            if hasattr(self, 'status_label') and self.status_label:
                 current_text = self.status_label.text()
                 # Avoid overwriting important status messages like "Loading..." or "Saving..."
                 # Only reset to "Ready" if it's currently showing coordinates or "Ready"
                 if current_text.startswith("Chi-squared: z=") or current_text == "Ready" or not current_text.strip():
                    self.status_label.setText("Ready")
            # else: pass # status_label not yet initialized or already destroyed

    def on_chi2_canvas_click(self, event):
        """Handle clicks on the chi-squared canvas to select a redshift."""
        if event.inaxes == self.chi2_ax and event.xdata is not None and self.yaml_data: # Ensure yaml_data is loaded
            clicked_z = float(event.xdata)
            
            # Find the closest redshift in zg1 (coarse) or zg0 (fine) if available
            target_z_array = None
            if 'zg0' in self.yaml_data and isinstance(self.yaml_data['zg0'], list) and len(self.yaml_data['zg0']) > 0:
                target_z_array = np.array(self.yaml_data['zg0'])
            elif 'zg1' in self.yaml_data and isinstance(self.yaml_data['zg1'], list) and len(self.yaml_data['zg1']) > 0:
                target_z_array = np.array(self.yaml_data['zg1'])

            if target_z_array is not None and target_z_array.size > 0:
                closest_z_idx = np.abs(target_z_array - clicked_z).argmin()
                actual_z = float(target_z_array[closest_z_idx])
                self.current_z = actual_z 
                
                # Update z_min and z_max spinboxes around the new z
                self.z_min.setValue(actual_z - 0.05) 
                self.z_max.setValue(actual_z + 0.05) 
                
                self.update_display() 
                self.status_label.setText(f"Selected z = {self.current_z:.4f} from chi-squared plot. Adjust range and refit if needed.")
            else:
                self.status_label.setText(f"Clicked on z={clicked_z:.4f}. No z-data in YAML to snap to. Adjust range and refit.")
        # else:
            # self.status_label.setText("Ready") # Avoid overwriting if click is outside or no data

    def save_current_fit_to_yaml(self):
        if not self.spectrum_files or self.current_index < 0:
            self.show_message_dialog("Error", "No spectrum loaded to save.")
            return

        if self.yaml_data is None: # Check if yaml_data is populated
            self.show_message_dialog("Error", "No fit data (YAML) loaded or generated to save.")
            return

        current_file_path = self.spectrum_files[self.current_index]
        base, ext = os.path.splitext(current_file_path)
        if ext == '.gz': # Handle .fits.gz
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        
        yaml_file_path = base + ".yaml"

        try:
            # Update yaml_data with current selections from GUI
            self.yaml_data['z_conf'] = self.z_conf_value 
            self.yaml_data['comment'] = self.comment_value
            if self.current_z is not None:
                 self.yaml_data['z_sel'] = float(self.current_z) # Ensure it's a float

            with open(yaml_file_path, 'w') as f:
                yaml.dump(self.yaml_data, f, default_flow_style=False, sort_keys=False)
            self.status_label.setText(f"Saved fit to {os.path.basename(yaml_file_path)}")
            self.show_message_dialog("Success", f"Fit data saved to {yaml_file_path}")
            
            # Update CSV if loaded
            if self.redshift_df is not None:
                filename_to_update = os.path.basename(current_file_path)
                if filename_to_update in self.redshift_df['filename'].values:
                    idx = self.redshift_df[self.redshift_df['filename'] == filename_to_update].index
                    self.redshift_df.loc[idx, 'z_guess'] = self.current_z if self.current_z is not None else np.nan
                    self.redshift_df.loc[idx, 'z_conf'] = self.z_conf_value
                    self.redshift_df.loc[idx, 'comment'] = self.comment_value
                    # print(f"Updated DataFrame for {filename_to_update}")
                else:
                    print(f"Filename {filename_to_update} not found in loaded CSV for live update.")

        except Exception as e:
            error_message = f"Error saving YAML: {e}"
            print(error_message)
            self.show_message_dialog("Error", error_message)
            self.status_label.setText(f"Error saving YAML.")
    
    def upload_redshift_csv(self):
        """Upload a CSV file with redshift guesses."""
        csv_file, _ = QFileDialog.getOpenFileName(
            self, "Upload Redshift CSV", "", "CSV Files (*.csv)"
        )
        
        if not csv_file:
            return # User cancelled
            
        try:
            self.redshift_df = pd.read_csv(csv_file)
            print(f"Loaded redshift guesses from {csv_file}")
            QMessageBox.information(self, "CSV Loaded", f"Successfully loaded {csv_file}")
            
            # If a spectrum is currently loaded, try to find a guess for it
            if self.spectrum_files and self.current_index < len(self.spectrum_files):
                current_spectrum_file = self.spectrum_files[self.current_index]
                # Check if we need to run a fit if results are missing
                zfit_file, yaml_file = self.find_existing_results(current_spectrum_file)
                if not (zfit_file and yaml_file):
                    # Attempt to load current spectrum again, which might trigger a fit using the new CSV data
                    self.load_current_spectrum()
                else:
                    # If results exist, just update the display in case the CSV provided a new best guess
                    # that might be different from the saved 'z' (though this is less direct)
                    # A more direct approach would be to re-evaluate the 'best z' if that's desired.
                    self.update_display() # Refresh display, z_value might change if logic allows
                    
        except Exception as e:
            self.handle_error("loading redshift CSV", e)

    def batch_run_missing_fits(self):
        threading.Thread(target=self._batch_run_missing_fits_worker, daemon=True).start()
    
    def _batch_run_missing_fits_worker(self):
        """Run redshift fitting for all files without a redshift solution (no .zfit.yaml)."""
        if not self.spectrum_files:
            self.show_message_signal.emit("No Files", "No spectrum files available.")
            return
        
        unsolved_files = []
        for f_path in self.spectrum_files:
            related_files = self.get_related_files(f_path)
            if not os.path.exists(related_files['yaml']):
                unsolved_files.append(f_path)
        
        if not unsolved_files:
            self.show_message_signal.emit("Up-to-date", "All files already have redshift solutions.")
            return
        
        total_files = len(unsolved_files)
        processed = 0
        for spectrum_file in unsolved_files:
            processed += 1
            self.update_status_signal.emit(f"Processing {processed}/{total_files}: {os.path.basename(spectrum_file)}...")
            # QApplication.processEvents() # Removed: Unsafe to call from worker thread
            
            redshift_guess = self.get_redshift_guess_from_csv(spectrum_file)
            
            if redshift_guess is not None:
                # We have a guess - use a targeted range around it
                z_min = redshift_guess * REDSHIFT_GUESS_LOWER_FACTOR
                z_max = redshift_guess * REDSHIFT_GUESS_UPPER_FACTOR
                logging.info(f"Using CSV guess {redshift_guess:.4f} for {os.path.basename(spectrum_file)}")
            else:
                # No guess - use current UI values (default range)
                z_min = self.z_min.value()
                z_max = self.z_max.value()
                logging.info(f"No CSV guess for {os.path.basename(spectrum_file)}, using range {z_min:.4f}-{z_max:.4f}")
            
            try:
                self.run_direct_fit(spectrum_file, z_min=z_min, z_max=z_max)
            except Exception as e:
                print(f"Error processing {spectrum_file}: {e}")
        
        self.update_status_signal.emit("Batch processing complete.")
    
    def keyPressEvent(self, a0: QKeyEvent):
        """Handle keyboard shortcuts"""
        key = a0.key()
        # modifiers = a0.modifiers() # Not used, can be removed if not needed later

        if a0.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            text_content = clipboard.text()
            try:
                parts = []
                if ',' in text_content:
                    parts = [p.strip() for p in text_content.split(',')]
                elif '\\t' in text_content:
                    parts = [p.strip() for p in text_content.split('\\t')]
                else:
                    parts = [p.strip() for p in text_content.split()]

                numbers = [float(p) for p in parts if p] 

                if len(numbers) == 2:
                    self.z_min.setValue(numbers[0])
                    self.z_max.setValue(numbers[1])
                    print(f"Pasted z_min: {numbers[0]}, z_max: {numbers[1]}")
                    a0.accept()
                    return 
                elif len(numbers) == 1:
                    self.current_z = numbers[0]
                    self.update_display() 
                    print(f"Pasted single value as current_z: {self.current_z}")
                    a0.accept()
                    return 
                else:
                    pass
            except ValueError:
                pass # Fall through if conversion fails
        
        if key == Qt.Key.Key_N:
            self.next_spectrum()
        elif key == Qt.Key.Key_P:
            self.previous_spectrum()
        elif key == Qt.Key.Key_F:
            self.refit_redshift()
        elif key == Qt.Key.Key_1:
            self.z_conf_combo.setCurrentIndex(0)
        elif key == Qt.Key.Key_2:
            self.z_conf_combo.setCurrentIndex(1)
        elif key == Qt.Key.Key_3:
            self.z_conf_combo.setCurrentIndex(2)
        elif key == Qt.Key.Key_9:
            self.z_conf_combo.setCurrentIndex(3)
        else:
            super().keyPressEvent(a0)

    def closeEvent(self, a0: QCloseEvent):
        """Handle window close events to disconnect Matplotlib handlers."""
        if self.chi2_canvas:
            if self.chi2_motion_cid:
                try:
                    self.chi2_canvas.mpl_disconnect(self.chi2_motion_cid)
                except Exception as e:
                    print(f"Error disconnecting chi2_motion_cid: {e}")
                self.chi2_motion_cid = None

            if self.chi2_click_cid:
                try:
                    self.chi2_canvas.mpl_disconnect(self.chi2_click_cid)
                except Exception as e:
                    print(f"Error disconnecting chi2_click_cid: {e}")
                self.chi2_click_cid = None
        
        super().closeEvent(a0)

    def update_file_dropdown(self):
        """Update the file dropdown with all spectrum files"""
        if hasattr(self, 'file_dropdown'):
            self.file_dropdown.clear()
            
            if self.spectrum_files:
                # Add items with both index and filename for easier identification
                for i, file_path in enumerate(self.spectrum_files):
                    base_name = os.path.basename(file_path)
                    self.file_dropdown.addItem(f"{i+1}: {base_name}", i)  # Store index as item data
                
                # Set current index based on currently loaded spectrum
                if 0 <= self.current_index < len(self.spectrum_files):
                    self.file_dropdown.setCurrentIndex(self.current_index)
    
    def on_file_selected(self, index):
        """Handle file selection from dropdown"""
        if not self.spectrum_files or index < 0:
            return
            
        # Get the index stored as item data
        selected_index = self.file_dropdown.itemData(index)
        
        if selected_index is not None and selected_index != self.current_index:
            # Save metadata for current spectrum before changing
            self.save_metadata(False)
            
            self.current_index = selected_index
            self.load_current_spectrum()
            self.status_label.setText(f"Loaded file {self.current_index + 1}/{len(self.spectrum_files)}")

    def fetch_galaxy_image(self, ra, dec, metafile=None, size=1.0, scl=3, filters='f115w-clear,f277w-clear,f444w-clear'):
        """Fetch a galaxy image from the Grizli cutout server
        
        Parameters
        ----------
        ra, dec : float
            Coordinates in degrees
        size : float, optional
            Size of cutout in arcminutes
        scl : int, optional
            Scale factor for image display
        filters : str, optional
            Comma-separated list of filters
            
        Returns
        -------
        QPixmap or None
            The galaxy image as a QPixmap, or None if fetch failed
        """
        try:
            rd = f"{ra:.6f},{dec:.6f}"
            
            if metafile:
                nirspec_string = f"nirspec=True&dpi_scale=6&nrs_lw=0.5&nrs_alpha=0.8&metafile={metafile}"
                           
            url = f"https://grizli-cutout.herokuapp.com/thumb?coord={rd}&size={size}&scl={scl}&asinh=True&filters={filters}&rgb_scl=1.0,0.95,1.2&pl=2&{nirspec_string}"
            
            self.status_label.setText(f"Fetching galaxy image for RA={ra:.6f}, Dec={dec:.6f}...")
            QApplication.processEvents()  # Update the UI
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.handle_error(f"fetching galaxy image (HTTP {response.status_code})", "Server returned an error", False)
                return None
                
            # Process the image
            img = Image.open(BytesIO(response.content))
            
            # Convert to QPixmap
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                img.save(tmpfile.name)
                pixmap = QPixmap(tmpfile.name)
                os.unlink(tmpfile.name)  # Delete temporary file
                
            return pixmap
            
        except Exception as e:
            self.handle_error("fetching galaxy image", e, False)
            return None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = RedshiftGUI()
    gui.show()
    sys.exit(app.exec_())