"""
General utility functions for the Redshift GUI application.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import os
import logging
from PyQt5.QtWidgets import QMessageBox

logging.basicConfig(level=logging.INFO)

def get_related_files(spectrum_file):
    """
    Get the related file paths for a spectrum file.
    
    Args:
        spectrum_file (str): Path to the 1D spectrum file
        
    Returns:
        dict: Dictionary with paths to related files
    """
    base_name = os.path.splitext(spectrum_file)[0]
    return {
        'chi2': f"{base_name}.chi2.png",
        'zfit': f"{base_name}.zfit.png",
        'yaml': f"{base_name}.zfit.yaml",
        's2d': spectrum_file.replace("o1d.fits", "s2d.fits")
    }

def all_files_exist(files_list):
    """
    Check if all files in a list exist.
    
    Args:
        files_list (list): List of file paths
        
    Returns:
        bool: True if all files exist, False otherwise
    """
    return all(os.path.exists(f) for f in files_list)

def extract_ids_from_filename(filename):
    """
    Extract observation ID and galaxy ID from filename.
    
    Args:
        filename (str): Path to the file
        
    Returns:
        tuple: (observation_id, galaxy_id) or (None, None) if extraction fails
    """
    base_name = os.path.basename(os.path.splitext(filename)[0])
    try:
        gal_id = int(base_name.split("_")[1].replace("s", ""))  # Extract galaxy ID
        obs_id = int(base_name.split("_")[0].split("-")[-1].replace("o", ""))  # Extract observation ID
        return obs_id, gal_id
    except (IndexError, ValueError) as e:
        logging.error(f"Error extracting IDs from filename {filename}: {str(e)}")
        return None, None

def handle_error(operation, error, parent=None, show_dialog=True):
    """
    Standardized error handling.
    
    Args:
        operation (str): Description of the operation that failed
        error (Exception or str): The error that occurred
        parent (QWidget, optional): Parent widget for the dialog
        show_dialog (bool): Whether to show a dialog
    """
    error_msg = f"Error {operation}: {str(error)}"
    logging.error(error_msg)
    
    if show_dialog and parent:
        QMessageBox.warning(parent, "Error", error_msg)
