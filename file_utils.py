"""
File operations for the Redshift GUI application.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import os
import glob
import yaml
import pandas as pd
import logging
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from utils import get_related_files, extract_ids_from_filename, handle_error

def select_directory(parent):
    """
    Open a directory dialog and find all FITS files in it.
    
    Args:
        parent: The parent widget for the dialog
        
    Returns:
        list: Sorted list of FITS file paths, or empty list if none found
    """
    directory = QFileDialog.getExistingDirectory(parent, "Select Directory")
    
    if directory:
        # Find all FITS files in this directory
        fits_files = glob.glob(os.path.join(directory, "*o1d.fits"))
        
        if fits_files:
            logging.info(f"Found {len(fits_files)} FITS files in {directory}")
            return sorted(fits_files)
        else:
            QMessageBox.information(parent, "No FITS Files", 
                                   f"No FITS files found in {directory}")
    
    return []

def find_existing_results(spectrum_file):
    """
    Find existing redshift fit results for a file.
    
    Args:
        spectrum_file (str): Path to the spectrum file
        
    Returns:
        tuple: (zfit_file, yaml_file) if they exist, otherwise (None, None)
    """
    related_files = get_related_files(spectrum_file)
    
    # We need zfit.png for the plot and zfit.yaml for chi2 data and metadata
    if os.path.exists(related_files['zfit']) and os.path.exists(related_files['yaml']):
        return related_files['zfit'], related_files['yaml']
    
    return None, None

def load_yaml_data(yaml_file):
    """
    Load YAML data from a file.
    
    Args:
        yaml_file (str): Path to the YAML file
        
    Returns:
        dict: The loaded YAML data, or None if loading fails
    """
    try:
        if os.path.exists(yaml_file):
            with open(yaml_file, 'r') as f:
                return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading YAML file {yaml_file}: {str(e)}")
    
    return None

def save_yaml_data(yaml_file, data):
    """
    Save data to a YAML file.
    
    Args:
        yaml_file (str): Path to the YAML file
        data (dict): The data to save
        
    Returns:
        bool: True if saving was successful, False otherwise
    """
    try:
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f)
        return True
    except Exception as e:
        logging.error(f"Error saving YAML file {yaml_file}: {str(e)}")
        return False

def get_redshift_guess_from_csv(spectrum_file, redshift_df):
    """
    Get the redshift guess from the stored CSV data for a spectrum file.
    
    Args:
        spectrum_file (str): Path to the spectrum file
        redshift_df (pandas.DataFrame): DataFrame with redshift guesses
        
    Returns:
        float: The redshift guess, or None if no matching entry is found
    """
    if redshift_df is None:
        return None
        
    # Extract observation ID and galaxy ID from filename
    obs_id, gal_id = extract_ids_from_filename(spectrum_file)
    
    if obs_id is None or gal_id is None:
        return None
        
    try:
        # Filter DataFrame for matching observation ID
        df_obs = redshift_df.query(f"obsid == {obs_id}")
        if df_obs.empty:
            return None
        
        # Search for matching galaxy ID in the filtered DataFrame
        matching_row = df_obs[df_obs["objid"] == gal_id]
        
        if not matching_row.empty and "specz" in matching_row.columns:
            return float(matching_row["specz"].iloc[0])
    except Exception as e:
        logging.error(f"Error getting redshift guess from CSV: {str(e)}")
        
    return None

def load_redshift_csv(parent):
    """
    Load a CSV file with redshift guesses.
    
    Args:
        parent: The parent widget for the dialog
        
    Returns:
        pandas.DataFrame: DataFrame with redshift guesses, or None if loading fails
    """
    file_path, _ = QFileDialog.getOpenFileName(
        parent, "Open Redshift CSV", "", "CSV Files (*.csv)"
    )
    
    if file_path and os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            required_columns = ["obsid", "objid", "specz"]
            
            # Check if required columns exist
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                QMessageBox.warning(
                    parent, "Invalid CSV Format",
                    f"CSV file is missing required columns: {', '.join(missing)}"
                )
                return None
                
            return df
        except Exception as e:
            handle_error("loading CSV file", e, parent)
    
    return None
