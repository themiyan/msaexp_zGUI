"""
Event handlers for the Redshift GUI application.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import os
import logging
import threading
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import Qt
from utils import handle_error, get_related_files
from file_utils import (
    select_directory, find_existing_results, load_yaml_data, 
    load_redshift_csv, save_yaml_data
)
from visualization import (
    update_chi2_plot, reset_chi2_view, scale_pixmap
)
from spectrum_processing import (
    run_direct_fit, load_2d_spectrum, batch_process_spectra
)

def connect_events(gui):
    """
    Connect all event handlers to GUI components.
    
    Args:
        gui: The main GUI instance
    """
    # Connect button clicks
    gui.select_dir_button.clicked.connect(lambda: on_select_directory(gui))
    gui.reset_view_button.clicked.connect(lambda: on_reset_view(gui))
    gui.refit_button.clicked.connect(lambda: on_refit_redshift(gui))
    gui.prev_button.clicked.connect(lambda: on_previous_spectrum(gui))
    gui.next_button.clicked.connect(lambda: on_next_spectrum(gui))
    gui.save_button.clicked.connect(lambda: on_save_metadata(gui))
    gui.batch_fit_button.clicked.connect(lambda: on_batch_run_missing_fits(gui))
    gui.upload_csv_button.clicked.connect(lambda: on_upload_redshift_csv(gui))
    
    # Connect dropdown and edit fields
    gui.file_dropdown.currentIndexChanged.connect(lambda index: on_file_selected(gui, index))
    gui.z_conf_combo.currentIndexChanged.connect(lambda: on_update_z_conf(gui))
    gui.comment_edit.textChanged.connect(lambda: on_update_comment(gui))
    
    # Connect Matplotlib canvas events if they exist
    if gui.chi2_canvas:
        gui.chi2_motion_cid = gui.chi2_canvas.mpl_connect(
            'motion_notify_event', lambda event: on_chi2_canvas_motion(gui, event)
        )
        gui.chi2_click_cid = gui.chi2_canvas.mpl_connect(
            'button_press_event', lambda event: on_chi2_canvas_click(gui, event)
        )

def on_select_directory(gui):
    """
    Handle selecting a directory of FITS files.
    
    Args:
        gui: The main GUI instance
    """
    spectrum_files = select_directory(gui)
    
    if spectrum_files:
        gui.spectrum_files = spectrum_files
        gui.current_index = 0
        update_file_dropdown(gui)
        load_current_spectrum(gui)

def update_file_dropdown(gui):
    """
    Update the file dropdown with the current spectrum files.
    
    Args:
        gui: The main GUI instance
    """
    gui.file_dropdown.clear()
    
    if gui.spectrum_files:
        for spec_file in gui.spectrum_files:
            gui.file_dropdown.addItem(os.path.basename(spec_file))

def on_file_selected(gui, index):
    """
    Handle file selection from the dropdown.
    
    Args:
        gui: The main GUI instance
        index (int): The selected index in the dropdown
    """
    if 0 <= index < len(gui.spectrum_files):
        # Check if we need to save the current metadata before switching
        if gui.current_index != -1 and gui.yaml_data:
            if gui.yaml_data.get('z_conf') != gui.z_conf_value or gui.yaml_data.get('comment') != gui.comment_value:
                reply = QMessageBox.question(
                    gui, "Save Changes?",
                    "Do you want to save changes to the current file before switching?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    # Revert dropdown selection
                    gui.file_dropdown.blockSignals(True)
                    gui.file_dropdown.setCurrentIndex(gui.current_index)
                    gui.file_dropdown.blockSignals(False)
                    return
                elif reply == QMessageBox.Yes:
                    on_save_metadata(gui)
        
        gui.current_index = index
        load_current_spectrum(gui)

def load_current_spectrum(gui):
    """
    Load the currently selected spectrum and its redshift fit results.
    
    Args:
        gui: The main GUI instance
    """
    if not gui.spectrum_files or gui.current_index >= len(gui.spectrum_files):
        return

    spectrum_file = gui.spectrum_files[gui.current_index]
    gui.file_label.setText(f"File {gui.current_index + 1}/{len(gui.spectrum_files)}: {os.path.basename(spectrum_file)}")
    
    # Update dropdown selection to match the current index
    if hasattr(gui, 'file_dropdown') and 0 <= gui.current_index < len(gui.spectrum_files):
        # Temporarily disconnect signal to avoid triggering on_file_selected
        gui.file_dropdown.blockSignals(True)
        gui.file_dropdown.setCurrentIndex(gui.current_index)
        gui.file_dropdown.blockSignals(False)

    # Clear previous state
    if gui.chi2_ax:
        gui.chi2_ax.clear()
        if gui.chi2_canvas:
            gui.chi2_canvas.draw_idle()
    
    gui.zfit_pixmap = None
    gui.s2d_pixmap = None
    gui.galaxy_pixmap = None
    gui.current_z = None
    gui.yaml_data = None  # Clear YAML data
    update_display(gui)   # Update UI to reflect cleared state

    # Load the 2D spectrum
    spectrum_result = load_2d_spectrum(spectrum_file, handle_galaxy_image=True, filters='f115w-clear,f277w-clear,f444w-clear')
    if spectrum_result:
        gui.s2d_pixmap = spectrum_result.get('s2d_pixmap')
        gui.galaxy_pixmap = spectrum_result.get('galaxy_pixmap')
        update_display(gui)  # Update with loaded images

    # Check if redshift fit results already exist
    zfit_file, yaml_file = find_existing_results(spectrum_file)

    if zfit_file and yaml_file:
        # Load existing results
        load_fit_results(gui, zfit_file, yaml_file)
        return

    # Check if there's a CSV-based redshift guess for this spectrum
    from file_utils import get_redshift_guess_from_csv
    from config import REDSHIFT_GUESS_LOWER_FACTOR, REDSHIFT_GUESS_UPPER_FACTOR, DEFAULT_Z_MIN, DEFAULT_Z_MAX
    
    redshift_guess = get_redshift_guess_from_csv(spectrum_file, gui.redshift_df)
    
    if redshift_guess is not None:
        # We have a guess from the CSV - ask if the user wants to use it
        z_min = redshift_guess * REDSHIFT_GUESS_LOWER_FACTOR
        z_max = redshift_guess * REDSHIFT_GUESS_UPPER_FACTOR
        
        reply = QMessageBox.question(
            gui, "Run Redshift Fit",
            f"No existing results. Found redshift guess {redshift_guess:.4f} in CSV. "
            f"Run fitting with range {z_min:.4f}-{z_max:.4f}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            gui.z_min.setValue(z_min)
            gui.z_max.setValue(z_max)
            on_run_direct_fit(gui, spectrum_file, z_min, z_max)
        return
    
    # No CSV guess, ask about default range
    reply = QMessageBox.question(
        gui, "Run Redshift Fit",
        f"Redshift fit results not found for {os.path.basename(spectrum_file)}. Run fitting?",
        QMessageBox.Yes | QMessageBox.No
    )

    if reply == QMessageBox.Yes:
        # Set default z range to 0-10 for first-time fits
        gui.z_min.setValue(DEFAULT_Z_MIN)
        gui.z_max.setValue(DEFAULT_Z_MAX)
        
        # Get the values from the UI
        z_min = gui.z_min.value()
        z_max = gui.z_max.value()

        # Run fit directly
        on_run_direct_fit(gui, spectrum_file, z_min, z_max)

def load_fit_results(gui, zfit_file, yaml_file):
    """
    Load existing redshift fit results.
    
    Args:
        gui: The main GUI instance
        zfit_file (str): Path to the zfit PNG file
        yaml_file (str): Path to the YAML file with fit results
    """
    gui.yaml_data = None  # Clear previous YAML data

    try:
        # Load YAML data
        gui.yaml_data = load_yaml_data(yaml_file)
        
        # Update chi-squared plot
        if gui.chi2_ax:
            update_chi2_plot(
                gui.chi2_ax, 
                gui.chi2_canvas, 
                gui.yaml_data, 
                os.path.basename(yaml_file)
            )

        # Load zfit pixmap
        gui.zfit_pixmap = None  # Clear previous
        if os.path.exists(zfit_file):
            from PyQt5.QtGui import QPixmap
            gui.zfit_pixmap = QPixmap(zfit_file)
            if gui.zfit_pixmap.isNull():
                logging.error(f"Failed to load zfit image: {zfit_file}")
                gui.zfit_pixmap = None 
        else:
            logging.error(f"Zfit image not found: {zfit_file}")
    
        # Update current_z and other metadata from YAML
        if gui.yaml_data:
            z_val = gui.yaml_data.get('z')
            gui.current_z = float(z_val) if z_val is not None else None
            gui.z_conf_value = int(gui.yaml_data.get('z_conf', 1))
            gui.comment_value = gui.yaml_data.get('comment', "")
        else: 
            gui.current_z = None
            gui.z_conf_value = 1
            gui.comment_value = ""
        
        update_display(gui)
        
    except Exception as e:
        handle_error(f"loading results for {os.path.basename(yaml_file)}", e, gui)
        if gui.chi2_ax: 
            gui.chi2_ax.clear()
        if gui.chi2_canvas: 
            gui.chi2_canvas.draw_idle()
        gui.zfit_pixmap = None
        gui.current_z = None
        update_display(gui)  # Reflect error state in UI

def on_run_direct_fit(gui, spectrum_file, z_min=0.0, z_max=10.0):
    """
    Run the redshift fitting directly.
    
    Args:
        gui: The main GUI instance
        spectrum_file (str): Path to the spectrum file
        z_min (float): Minimum redshift for fitting
        z_max (float): Maximum redshift for fitting
    """
    # Run the fit
    success, new_zfit_file, new_yaml_file = run_direct_fit(
        spectrum_file, z_min, z_max,
        update_status_callback=gui.update_status_signal.emit
    )
    
    if success and new_zfit_file and new_yaml_file:
        load_fit_results(gui, new_zfit_file, new_yaml_file)
        gui.update_status_signal.emit(f"Fit complete for {os.path.basename(spectrum_file)}")
    else:
        gui.update_status_signal.emit("Error running fit")

def update_display(gui):
    """
    Update the display with current images and redshift.
    
    Args:
        gui: The main GUI instance
    """
    # Clear image labels before attempting to set new content
    gui.zfit_image.clear()
    gui.s2d_image.clear()
    gui.galaxy_image.clear()

    # Chi-squared plot is drawn directly on its canvas.
    # Ensure canvas is drawn if it exists and is visible
    if gui.chi2_canvas and gui.chi2_canvas.isVisible():
         gui.chi2_canvas.draw_idle()

    # 1D spectrum (zfit_image)
    if gui.zfit_pixmap and not gui.zfit_pixmap.isNull():
        gui.zfit_image.setPixmap(gui.zfit_pixmap)
    else:
        gui.zfit_image.setText("Spectrum N/A")
        
    # 2D spectrum (s2d_image)
    if gui.s2d_pixmap and not gui.s2d_pixmap.isNull():
        gui.s2d_image.setPixmap(gui.s2d_pixmap)
    else:
        gui.s2d_image.setText("2D Spectrum N/A")
        
    # Galaxy image
    if gui.galaxy_pixmap and not gui.galaxy_pixmap.isNull():
        gui.galaxy_image.setPixmap(scale_pixmap(
            gui.galaxy_pixmap,
            gui.galaxy_image.width(), 
            gui.galaxy_image.height(), 
            True
        ))
    else:
        gui.galaxy_image.setText("Galaxy Image N/A")
    
    # Update redshift display
    gui.z_value.setText(f"{gui.current_z:.4f}" if gui.current_z is not None else "N/A")
    
    # Update z_conf combo
    conf_index = gui.z_conf_combo.findText(str(gui.z_conf_value))
    if conf_index != -1:
        gui.z_conf_combo.setCurrentIndex(conf_index)
        
    gui.comment_edit.setText(gui.comment_value if gui.comment_value is not None else "")

    # Enable/disable buttons based on state
    has_files = bool(gui.spectrum_files)
    is_valid_index = -1 < gui.current_index < len(gui.spectrum_files) if has_files else False

    gui.prev_button.setEnabled(has_files and gui.current_index > 0)
    gui.next_button.setEnabled(has_files and gui.current_index < len(gui.spectrum_files) - 1)
    gui.refit_button.setEnabled(is_valid_index)
    # Enable save only if there's a current spectrum and a redshift value (implies YAML is loaded)
    gui.save_button.setEnabled(is_valid_index and gui.yaml_data is not None)

def on_refit_redshift(gui):
    """
    Refit the redshift with new z range.
    
    Args:
        gui: The main GUI instance
    """
    if not gui.spectrum_files or gui.current_index >= len(gui.spectrum_files):
        return
    
    z_min = gui.z_min.value()
    z_max = gui.z_max.value()
    
    if z_min >= z_max:
        QMessageBox.warning(
            gui, "Invalid Range", 
            "Minimum redshift must be less than maximum redshift."
        )
        return
    
    # Run redshift fitting directly
    on_run_direct_fit(
        gui,
        gui.spectrum_files[gui.current_index],
        z_min=z_min,
        z_max=z_max
    )

def on_previous_spectrum(gui):
    """
    Move to the previous spectrum and save metadata.
    
    Args:
        gui: The main GUI instance
    """
    if gui.current_index > 0:
        # Check if we need to save metadata
        if gui.yaml_data and (
            gui.yaml_data.get('z_conf') != gui.z_conf_value or 
            gui.yaml_data.get('comment') != gui.comment_value
        ):
            on_save_metadata(gui)
            
        # Move to previous spectrum
        gui.current_index -= 1
        load_current_spectrum(gui)

def on_next_spectrum(gui):
    """
    Move to the next spectrum and save metadata.
    
    Args:
        gui: The main GUI instance
    """
    if gui.current_index < len(gui.spectrum_files) - 1:
        # Check if we need to save metadata
        if gui.yaml_data and (
            gui.yaml_data.get('z_conf') != gui.z_conf_value or 
            gui.yaml_data.get('comment') != gui.comment_value
        ):
            on_save_metadata(gui)
            
        # Move to next spectrum
        gui.current_index += 1
        load_current_spectrum(gui)
    elif gui.spectrum_files:
        QMessageBox.information(
            gui, "End of List", 
            "You've reached the last spectrum in the list."
        )

def on_update_z_conf(gui):
    """
    Update the redshift confidence value when the dropdown changes.
    
    Args:
        gui: The main GUI instance
    """
    try:
        gui.z_conf_value = int(gui.z_conf_combo.currentText())
    except (ValueError, TypeError) as e:
        handle_error("updating z_conf", e, gui, False)
        gui.z_conf_value = 1  # Default to 1 on error

def on_update_comment(gui):
    """
    Update the comment value when the text field changes.
    
    Args:
        gui: The main GUI instance
    """
    gui.comment_value = gui.comment_edit.toPlainText()

def on_save_metadata(gui, show_popup=True):
    """
    Save the redshift metadata to the YAML file.
    
    Args:
        gui: The main GUI instance
        show_popup (bool): Whether to show a success popup
    """
    if not gui.spectrum_files or gui.current_index < 0 or gui.current_index >= len(gui.spectrum_files):
        return
        
    if not gui.yaml_data:
        QMessageBox.warning(
            gui, "Cannot Save", 
            "No redshift data to save. Please run redshift fitting first."
        )
        return
    
    spectrum_file = gui.spectrum_files[gui.current_index]
    yaml_file = get_related_files(spectrum_file)['yaml']
    
    # Update the YAML data with the current UI values
    gui.yaml_data['z_conf'] = gui.z_conf_value
    gui.yaml_data['comment'] = gui.comment_value
    
    # Save the YAML data
    if save_yaml_data(yaml_file, gui.yaml_data):
        if show_popup:
            QMessageBox.information(
                gui, "Save Successful", 
                f"Metadata saved to {os.path.basename(yaml_file)}"
            )
        return True
    else:
        QMessageBox.warning(
            gui, "Save Failed", 
            f"Could not save metadata to {os.path.basename(yaml_file)}"
        )
        return False

def on_reset_view(gui):
    """
    Reset the chi-squared plot to its original view.
    
    Args:
        gui: The main GUI instance
    """
    reset_chi2_view(gui.chi2_ax, gui.chi2_canvas)

def on_chi2_canvas_motion(gui, event):
    """
    Handle mouse motion over the chi-squared plot.
    
    Args:
        gui: The main GUI instance
        event: The matplotlib motion event
    """
    if not event.inaxes or not gui.chi2_ax:
        return
        
    # Update status bar with cursor coordinates
    z_value = event.xdata
    chi2_value = event.ydata
    gui.status_label.setText(f"z: {z_value:.4f}, χ²: {chi2_value:.4f}")

def on_chi2_canvas_click(gui, event):
    """
    Handle mouse clicks on the chi-squared plot.
    
    Args:
        gui: The main GUI instance
        event: The matplotlib click event
    """
    if not event.inaxes or not gui.chi2_ax:
        return
    
    # Left click: set z range around clicked point
    if event.button == 1:  # Left click
        z_value = event.xdata
        z_width = 0.5  # Default width for zoom
        
        # Set redshift range centered on clicked point
        gui.z_min.setValue(max(0, z_value - z_width/2))
        gui.z_max.setValue(z_value + z_width/2)
        
        gui.status_label.setText(f"Set z range: {gui.z_min.value():.4f} - {gui.z_max.value():.4f}")
    
    # Right click: zoom to region around clicked point
    elif event.button == 3:  # Right click
        z_value = event.xdata
        z_width = 0.5  # Default width for zoom
        
        # Zoom to region around clicked point
        gui.chi2_ax.set_xlim(z_value - z_width, z_value + z_width)
        gui.chi2_canvas.draw_idle()

def on_batch_run_missing_fits(gui):
    """
    Run redshift fitting on all spectra without existing results.
    
    Args:
        gui: The main GUI instance
    """
    if not gui.spectrum_files:
        QMessageBox.information(
            gui, "No Files", 
            "No spectrum files loaded. Please select a directory first."
        )
        return
    
    # Get all files that need processing
    files_to_process = []
    for spectrum_file in gui.spectrum_files:
        if not find_existing_results(spectrum_file)[0]:
            files_to_process.append(spectrum_file)
    
    if not files_to_process:
        QMessageBox.information(
            gui, "No Missing Files", 
            "All spectrum files already have redshift fits."
        )
        return
    
    reply = QMessageBox.question(
        gui, "Batch Processing", 
        f"Found {len(files_to_process)} spectra without redshift fits. Process them now?",
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply != QMessageBox.Yes:
        return
    
    # Set up progress bar
    gui.progress_bar.setVisible(True)
    gui.progress_bar.setValue(0)
    gui.batch_fit_button.setEnabled(False)
    gui.select_dir_button.setEnabled(False)
    
    # Run batch processing in a separate thread
    def update_progress(value):
        gui.progress_bar.setValue(value)
        QApplication.processEvents()
    
    def batch_complete(processed_count):
        gui.progress_bar.setVisible(False)
        gui.batch_fit_button.setEnabled(True)
        gui.select_dir_button.setEnabled(True)
        gui.update_status_signal.emit(f"Batch processing complete. Processed {processed_count} files.")
        
        # Reload current spectrum to show any changes
        if 0 <= gui.current_index < len(gui.spectrum_files):
            load_current_spectrum(gui)
    
    # Start batch processing thread
    def run_batch():
        from config import DEFAULT_Z_MIN, DEFAULT_Z_MAX
        processed = batch_process_spectra(
            files_to_process, 
            z_min=DEFAULT_Z_MIN, 
            z_max=DEFAULT_Z_MAX,
            redshift_df=gui.redshift_df,
            update_status_callback=gui.update_status_signal.emit,
            update_progress_callback=update_progress
        )
        # Signal completion on the main thread
        gui.update_status_signal.emit(f"Batch processing complete. Processed {processed} files.")
        batch_complete(processed)
    
    batch_thread = threading.Thread(target=run_batch)
    batch_thread.daemon = True
    batch_thread.start()

def on_upload_redshift_csv(gui):
    """
    Upload a CSV file with redshift guesses.
    
    Args:
        gui: The main GUI instance
    """
    redshift_df = load_redshift_csv(gui)
    
    if redshift_df is not None:
        gui.redshift_df = redshift_df
        QMessageBox.information(
            gui, "CSV Loaded", 
            f"Loaded redshift guesses for {len(redshift_df)} objects."
        )
    else:
        gui.redshift_df = None
