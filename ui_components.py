"""
UI setup functions for the Redshift GUI application.
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QDoubleSpinBox, QScrollArea, QSizePolicy, QComboBox, 
    QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt
from config import DEFAULT_Z_MIN, DEFAULT_Z_MAX

def configure_layout(layout, margins=(0, 0, 0, 0), spacing=5):
    """
    Configure layout margins and spacing consistently.
    
    Args:
        layout: The layout to configure
        margins (tuple): Content margins (left, top, right, bottom)
        spacing (int): Spacing between widgets
        
    Returns:
        The configured layout
    """
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout

def create_header_label(text):
    """
    Create a consistently styled header label.
    
    Args:
        text (str): Label text
        
    Returns:
        QLabel: Styled header label
    """
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label

def create_image_label():
    """
    Create a consistently styled image display label.
    
    Returns:
        QLabel: Styled image label
    """
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return label

def setup_central_widget(gui):
    """
    Set up the central widget and main layout.
    
    Args:
        gui: The main GUI instance
    """
    # Create the main widget and layout
    gui.central_widget = QWidget()
    gui.setCentralWidget(gui.central_widget)
    gui.main_layout = QVBoxLayout(gui.central_widget)
    
    # Create scroll area for image display
    gui.scroll_area = QScrollArea()
    gui.scroll_area.setWidgetResizable(True)
    gui.scroll_widget = QWidget()
    gui.scroll_layout = QVBoxLayout(gui.scroll_widget)
    gui.scroll_area.setWidget(gui.scroll_widget)
    
    gui.scroll_widget.setObjectName("scrollWidget")
    
    # Status display at the bottom
    gui.status_label = QLabel("Ready")
    
    # Add scroll area to main layout
    gui.main_layout.addWidget(gui.scroll_area)
    gui.main_layout.addWidget(gui.status_label)

def setup_file_controls(gui):
    """
    Set up the file selection controls.
    
    Args:
        gui: The main GUI instance
    """
    file_layout = QHBoxLayout()
    
    # Button to select directory
    gui.select_dir_button = QPushButton("Select Directory")
    file_layout.addWidget(gui.select_dir_button)
    
    # Label to show current file
    gui.file_label = QLabel("No files selected")
    file_layout.addWidget(gui.file_label)
    
    # Button to run batch fit for all missing redshift solutions
    gui.batch_fit_button = QPushButton("Run Fit on All Missing")
    file_layout.addWidget(gui.batch_fit_button)
    
    # Button to upload CSV with redshift guesses
    gui.upload_csv_button = QPushButton("Upload Redshift CSV")
    file_layout.addWidget(gui.upload_csv_button)
    
    # Batch progress bar (initially hidden)
    gui.progress_bar = QProgressBar()
    gui.progress_bar.setVisible(False)
    file_layout.addWidget(gui.progress_bar)
    
    # Add to scroll layout
    gui.scroll_layout.addLayout(file_layout)

def setup_image_display(gui):
    """
    Set up the image display area.
    
    Args:
        gui: The main GUI instance
    """
    image_layout = QHBoxLayout()
    configure_layout(image_layout, spacing=5)
    
    # === LEFT SIDE: File dropdown and chi2 plot (20% of horizontal space) ===
    chi2_layout = QVBoxLayout()
    configure_layout(chi2_layout)
    
    # Add file dropdown at the top of the left side
    dropdown_layout = QHBoxLayout()
    dropdown_layout.addWidget(QLabel("Select File:"))
    gui.file_dropdown = QComboBox()
    gui.file_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    gui.file_dropdown.setMinimumWidth(200)  # Make dropdown reasonably wide
    dropdown_layout.addWidget(gui.file_dropdown)
    chi2_layout.addLayout(dropdown_layout)

    # Add galaxy image panel between dropdown and chi2 plot
    gui.galaxy_label = create_header_label("Galaxy Image")
    gui.galaxy_image = create_image_label()
    gui.galaxy_image.setFixedHeight(200)  # Fixed height for the galaxy image
    
    chi2_layout.addWidget(gui.galaxy_label)
    chi2_layout.addWidget(gui.galaxy_image)
    
    # Add chi-squared plot below the galaxy image
    gui.chi2_label = create_header_label("Chi-squared vs Redshift")
    
    # gui.chi2_figure, gui.chi2_canvas, gui.chi2_ax are already initialized in __init__
    chi2_layout.addWidget(gui.chi2_label)
    chi2_layout.addWidget(gui.chi2_canvas) 
    
    # Add a reset view button for chi-squared plot
    reset_view_button = QPushButton("Reset View")
    gui.reset_view_button = reset_view_button
    chi2_layout.addWidget(reset_view_button)
    
    image_layout.addLayout(chi2_layout, 20)
    
    # === RIGHT SIDE: Vertical layout for 2D and 1D spectrum (80% of horizontal space) ===
    right_layout = QVBoxLayout()
    configure_layout(right_layout, spacing=5)
    
    # 2D spectrum plot (30% of vertical space on right side)
    gui.s2d_label = create_header_label("2D Spectrum")
    gui.s2d_image = create_image_label()
    
    s2d_layout = QVBoxLayout()
    configure_layout(s2d_layout)
    s2d_layout.addWidget(gui.s2d_label)
    s2d_layout.addWidget(gui.s2d_image)
    
    # Add 2D spectrum layout to right layout with 30% of vertical space
    right_layout.addLayout(s2d_layout, 30)
    
    # 1D spectrum plot (70% of vertical space on right side)
    gui.zfit_label = create_header_label("Spectrum Fit")
    gui.zfit_image = create_image_label()
    
    zfit_layout = QVBoxLayout()
    configure_layout(zfit_layout)
    zfit_layout.addWidget(gui.zfit_label)
    zfit_layout.addWidget(gui.zfit_image)
    
    # Add 1D spectrum layout to right layout with 70% of vertical space
    right_layout.addLayout(zfit_layout, 70)
    
    # Add right layout to main image layout with 80% of horizontal space
    image_layout.addLayout(right_layout, 80)
    
    # Add to scroll layout
    gui.scroll_layout.addLayout(image_layout)

def setup_redshift_controls(gui):
    """
    Set up the redshift fitting controls.
    
    Args:
        gui: The main GUI instance
    """
    # Create layout for redshift controls
    redshift_layout = QHBoxLayout()
    
    # Current redshift display
    gui.z_label = QLabel("Best fit z:")
    redshift_layout.addWidget(gui.z_label)
    
    gui.z_value = QLabel("N/A")
    redshift_layout.addWidget(gui.z_value)
    
    # Min/max z for refitting
    redshift_layout.addWidget(QLabel("New z range:"))
    
    gui.z_min = QDoubleSpinBox()
    gui.z_min.setRange(0.0, 20.0)
    gui.z_min.setDecimals(3)
    gui.z_min.setSingleStep(0.1)
    gui.z_min.setValue(DEFAULT_Z_MIN)
    redshift_layout.addWidget(gui.z_min)
    
    redshift_layout.addWidget(QLabel("to"))
    
    gui.z_max = QDoubleSpinBox()
    gui.z_max.setRange(0.0, 20.0)
    gui.z_max.setDecimals(3)
    gui.z_max.setSingleStep(0.1)
    gui.z_max.setValue(DEFAULT_Z_MAX)
    redshift_layout.addWidget(gui.z_max)
    
    # Refit button
    gui.refit_button = QPushButton("Refit Redshift")
    redshift_layout.addWidget(gui.refit_button)
    
    # Navigation buttons
    gui.prev_button = QPushButton("Previous")
    redshift_layout.addWidget(gui.prev_button)
    
    gui.next_button = QPushButton("Next")
    redshift_layout.addWidget(gui.next_button)
    
    # Add to scroll layout
    gui.scroll_layout.addLayout(redshift_layout)
    
    # Add z_conf and comment controls in a new layout
    quality_layout = QHBoxLayout()
    
    # Redshift quality (z_conf) dropdown
    quality_layout.addWidget(QLabel("Redshift Quality:"))
    gui.z_conf_combo = QComboBox()
    # Add items individually with explicit text
    gui.z_conf_combo.addItem("1")
    gui.z_conf_combo.addItem("2")
    gui.z_conf_combo.addItem("3")
    gui.z_conf_combo.addItem("9")  # New quality option added
    gui.z_conf_combo.setCurrentIndex(0)  # Default to 1
    
    # Set explicit size policy and minimum width to ensure dropdown is visible
    gui.z_conf_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    gui.z_conf_combo.setMinimumWidth(80)
    quality_layout.addWidget(gui.z_conf_combo)
    
    # Comment field
    quality_layout.addWidget(QLabel("Comment:"))
    gui.comment_edit = QTextEdit()
    gui.comment_edit.setMaximumHeight(60)  # Limit height
    quality_layout.addWidget(gui.comment_edit)
    
    # Save button
    gui.save_button = QPushButton("Save Metadata")
    quality_layout.addWidget(gui.save_button)
    
    # Add to scroll layout
    gui.scroll_layout.addLayout(quality_layout)
