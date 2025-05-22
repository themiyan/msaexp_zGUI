"""
Spectrum processing functions for the Redshift GUI application.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import os
import logging
from msaexp.spectrum import fit_redshift
from jwst.datamodels import open as dm_open
import numpy as np
from utils import get_related_files, handle_error
from visualization import create_2d_spectrum_image, fetch_galaxy_image

def run_direct_fit(spectrum_file, z_min=0.0, z_max=10.0, update_status_callback=None):
    """
    Run the redshift fitting directly.
    
    Args:
        spectrum_file (str): Path to the spectrum file
        z_min (float): Minimum redshift for fitting
        z_max (float): Maximum redshift for fitting
        update_status_callback (callable, optional): Callback for status updates
        
    Returns:
        tuple: (success, zfit_file, yaml_file)
    """
    try:
        if update_status_callback:
            update_status_callback(f"Processing {os.path.basename(spectrum_file)}...")
        
        # Run fit_redshift (writes .zfit.png and .zfit.yaml files)
        fit_redshift(
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
            if update_status_callback:
                update_status_callback(f"Fit complete for {os.path.basename(spectrum_file)}")
            return True, new_zfit_file, new_yaml_file
        else:
            logging.error(f"Output files not found after fit: {new_zfit_file}, {new_yaml_file}")
            if update_status_callback:
                update_status_callback("Error: Fit output files missing.")
            return False, None, None
            
    except Exception as e:
        logging.error(f"Error running fit for {spectrum_file}: {str(e)}")
        if update_status_callback:
            update_status_callback("Error during fit.")
        return False, None, None

def load_2d_spectrum(spectrum_file, handle_galaxy_image=True, filters='f115w-clear,f277w-clear,f444w-clear'):
    """
    Load the 2D spectrum associated with a 1D spectrum file.
    
    Args:
        spectrum_file (str): Path to the 1D spectrum file
        handle_galaxy_image (bool): Whether to fetch the galaxy image
        filters (str): Comma-separated list of filters for galaxy image
    Returns:
        dict: Dictionary with 's2d_pixmap' and 'galaxy_pixmap' (if requested)
    """
    result = {'s2d_pixmap': None, 'galaxy_pixmap': None}
    
    # Get the path to the 2D spectrum file
    related_files = get_related_files(spectrum_file)
    s2d_file = related_files['s2d']
    
    if not os.path.exists(s2d_file):
        logging.error(f"2D spectrum file not found: {s2d_file}")
        return result
    
    try:
        with dm_open(s2d_file) as model:
            data = model.data  # JWST spec model data
            
            # Get the WCS information from the model metadata
            alpha_C, delta_C, yinfo = model.meta.wcs(
                np.arange(0, model.data.shape[1]), 
                np.zeros_like(model.data.shape[1])
            )
            wavelength = yinfo
            
            # Create the 2D spectrum image
            result['s2d_pixmap'] = create_2d_spectrum_image(
                data, wavelength, model.data.shape
            )
            
            # Get galaxy image if requested
            if handle_galaxy_image:
                # Extract RA and Dec from the model metadata
                ra = model.source_ra
                dec = model.source_dec
                metafile = model.meta.instrument.msa_metadata_file.split('_')[0]
                
                if ra is not None and dec is not None:
                    result['galaxy_pixmap'] = fetch_galaxy_image(
                        ra=ra, 
                        dec=dec, 
                        size=1.0,  # Size in arcminutes 
                        metafile=metafile,
                        scl=3,
                        filters=filters,
                    )
                    result['ra_dec'] = (ra, dec)
    
    except Exception as e:
        logging.error(f"Error loading 2D spectrum: {str(e)}")
    
    return result

def batch_process_spectra(spectrum_files, z_min=0.0, z_max=10.0, 
                          redshift_df=None, update_status_callback=None,
                          update_progress_callback=None):
    """
    Process multiple spectrum files in batch.
    
    Args:
        spectrum_files (list): List of spectrum file paths
        z_min (float): Default minimum redshift for fitting
        z_max (float): Default maximum redshift for fitting
        redshift_df (pandas.DataFrame, optional): DataFrame with redshift guesses
        update_status_callback (callable, optional): Callback for status updates
        update_progress_callback (callable, optional): Callback for progress updates
        
    Returns:
        int: Number of successfully processed files
    """
    if not spectrum_files:
        return 0
        
    from config import REDSHIFT_GUESS_LOWER_FACTOR, REDSHIFT_GUESS_UPPER_FACTOR
    from file_utils import find_existing_results, get_redshift_guess_from_csv
    
    processed_count = 0
    total_files = len(spectrum_files)
    
    for i, spectrum_file in enumerate(spectrum_files):
        # Update progress
        if update_progress_callback:
            progress = int((i / total_files) * 100)
            update_progress_callback(progress)
            
        # Skip if results already exist
        if find_existing_results(spectrum_file)[0]:
            continue
            
        # Check if we have a CSV-based redshift guess
        fit_z_min, fit_z_max = z_min, z_max
        if redshift_df is not None:
            redshift_guess = get_redshift_guess_from_csv(spectrum_file, redshift_df)
            if redshift_guess is not None:
                fit_z_min = redshift_guess * REDSHIFT_GUESS_LOWER_FACTOR
                fit_z_max = redshift_guess * REDSHIFT_GUESS_UPPER_FACTOR
                
        # Update status
        if update_status_callback:
            update_status_callback(
                f"Processing file {i+1}/{total_files}: {os.path.basename(spectrum_file)}"
            )
            
        # Run fit
        success, _, _ = run_direct_fit(spectrum_file, fit_z_min, fit_z_max)
        if success:
            processed_count += 1
            
    # Update progress to 100%
    if update_progress_callback:
        update_progress_callback(100)
            
    return processed_count
