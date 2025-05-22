"""
Visualization utilities for the Redshift GUI application.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
import os
import tempfile
import numpy as np
import matplotlib.pyplot as plt
from astropy.visualization import ZScaleInterval
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import requests
from io import BytesIO
from PIL import Image
import logging

def create_chi2_figure():
    """
    Create a matplotlib figure for the chi-squared plot.
    
    Returns:
        tuple: (figure, canvas, axes)
    """
    figure = Figure(figsize=(5, 4), dpi=100)
    canvas = FigureCanvasQTAgg(figure)
    axes = figure.add_subplot(111)
    axes.set_navigate(False)  # Disable default Matplotlib navigation
    return figure, canvas, axes

def update_chi2_plot(axes, canvas, yaml_data, yaml_file_basename=None):
    """
    Update the chi-squared plot with data from a YAML file.
    
    Args:
        axes: The matplotlib axes to plot on
        canvas: The matplotlib canvas to draw on
        yaml_data (dict): The YAML data
        yaml_file_basename (str, optional): Basename of the YAML file for the title
    """
    axes.clear()
    
    if yaml_data and \
       'zg1' in yaml_data and isinstance(yaml_data.get('zg1'), list) and \
       'chi1' in yaml_data and isinstance(yaml_data.get('chi1'), list) and \
       len(yaml_data['zg1']) > 0 and \
       len(yaml_data['zg1']) == len(yaml_data['chi1']):
        
        axes.plot(yaml_data['zg0'], yaml_data['chi0'], label=r'data')
        axes.plot(yaml_data['zg1'], yaml_data['chi1'], label=r'$\chi^2$ ')
        axes.set_xlabel("Redshift (z)")
        axes.set_ylabel(r"$\chi^2$")
        
        if yaml_file_basename:
            axes.set_title(rf"$\chi^2$ for {yaml_file_basename}")
        
        axes.legend()
        axes.relim()
        axes.autoscale_view()
    else:
        msg = "Problem with $\chi^2$ data"
        if yaml_file_basename:
            msg += f" in\n{yaml_file_basename}"
        axes.text(0.5, 0.5, msg, ha='center', va='center', transform=axes.transAxes)
    
    canvas.draw_idle()

def reset_chi2_view(axes, canvas):
    """
    Reset chi-squared plot to original view (no zoom).
    
    Args:
        axes: The matplotlib axes to reset
        canvas: The matplotlib canvas to draw on
    """
    if axes:
        axes.autoscale(True)
        axes.relim()
        axes.autoscale_view()
        if canvas:
            canvas.draw_idle()

def create_2d_spectrum_image(data, wavelength, model_shape=None):
    """
    Create a 2D spectrum image.
    
    Args:
        data (numpy.ndarray): The 2D spectrum data
        wavelength (numpy.ndarray): Wavelength array
        model_shape (tuple, optional): Shape of the model
        
    Returns:
        QPixmap: The created image as a QPixmap
    """
    try:
        zscale = ZScaleInterval()
        vmin, vmax = zscale.get_limits(data)

        # Define extent so that imshow will display wavelength ticks on the x-axis
        if model_shape:
            extent = [wavelength[0], wavelength[-1], 0, model_shape[0]]
        else:
            extent = [wavelength[0], wavelength[-1], 0, data.shape[0]]

        # Create a figure, add axis labels, and save the image with extent
        fig, ax = plt.subplots(figsize=(20, 3))
        im = ax.imshow(data, origin='lower', vmin=vmin, vmax=vmax, cmap="gray")
        
        # Add green dashed grid lines
        ax.grid(True, color='green', linestyle='--', linewidth=0.5)
        
        # Add wavelength ticks
        tick_positions = np.arange(0, len(wavelength), 50)
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(np.round(wavelength[tick_positions], 2))
        ax.set_xlabel("Wavelength (microns)")
        ax.set_ylabel("Spatial")
        
        # Save to a temporary file and load as QPixmap
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            fig.savefig(tmpfile.name)
            pixmap = QPixmap(tmpfile.name)
            
        plt.close(fig)
        os.unlink(tmpfile.name)  # Delete the temporary file after loading pixmap
        
        return pixmap
        
    except Exception as e:
        logging.error(f"Error creating 2D spectrum image: {str(e)}")
        return None

def fetch_galaxy_image(ra, dec, size=1.0, metafile=None, scl=3, filters='f115w-clear,f277w-clear,f444w-clear'):
    """
    Fetch a cutout image of a galaxy from the Grizli service.
    
    Args:
        ra (float): Right ascension in degrees
        dec (float): Declination in degrees
        size (float): Size of cutout in arcminutes (default: 1.0)
        metafile (str, optional): Metadata file name
        scl (int): Scale factor for image display (default: 3)
        filters (str): Comma-separated list of filters (default: 'f115w-clear,f277w-clear,f444w-clear')
        
    Returns:
        QPixmap: The galaxy image as a QPixmap, or None if fetching fails
    """
    try:
        # Format the coordinates
        rd = f"{ra:.6f},{dec:.6f}"
        
        # Add NIRSpec MSA metadata if available
        nirspec_string = ""
        if metafile:
            nirspec_string = f"nirspec=True&dpi_scale=6&nrs_lw=0.5&nrs_alpha=0.8&metafile={metafile}"
        
        # Define user agents and headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://grizli-cutout.herokuapp.com/',
            'Connection': 'keep-alive',
        }
        
        # Try both URL patterns - first the heroku one, then fallback to s3 if needed
        urls = [
            # Primary URL (Heroku)
            f"https://grizli-cutout.herokuapp.com/thumb?coord={rd}&size={size}&scl={scl}&asinh=True&filters={filters}&rgb_scl=1.0,0.95,1.2&pl=2&{nirspec_string}",
            
            # Fallback URL (S3) if metafile is available
            f"https://s3.amazonaws.com/grizli-v1/Pipeline/{metafile}/Thumbnails/rgb_ra{ra:.6f}_dec{dec:.6f}_size{size}.png" if metafile else None
        ]
        
        # Try URLs in sequence
        for url in urls:
            if url is None:
                continue
                
            logging.info(f"Attempting to fetch galaxy image from URL: {url}")
            
            # Make request to the server with headers
            response = requests.get(url, headers=headers, timeout=20)  # Increased timeout
            
            # On success, process the image
            if response.status_code == 200:
                try:
                    # Open the image using PIL
                    img = Image.open(BytesIO(response.content))
                    
                    # Save to a temporary file and load as QPixmap
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                        img.save(tmpfile.name)
                        pixmap = QPixmap(tmpfile.name)
                        
                    os.unlink(tmpfile.name)  # Delete the temporary file after loading pixmap
                    logging.info(f"Successfully fetched galaxy image from: {url}")
                    return pixmap
                except Exception as img_error:
                    logging.error(f"Error processing image from {url}: {str(img_error)}")
                    continue  # Try next URL if available
            else:
                logging.warning(f"Failed to fetch galaxy image: HTTP {response.status_code}, URL: {url}")
                if response.status_code == 403:
                    logging.debug(f"Response headers: {response.headers}")
                    try:
                        logging.debug(f"Response content: {response.text[:500]}...")  # Log first 500 chars of response
                    except:
                        pass
        
        # If we get here, all URLs failed
        logging.error("All attempts to fetch galaxy image failed")
            
    except Exception as e:
        logging.error(f"Error fetching galaxy image: {str(e)}")
        
    return None

def scale_pixmap(pixmap, width, height, keep_aspect=True):
    """
    Scale a pixmap with consistent options.
    
    Args:
        pixmap (QPixmap): The pixmap to scale
        width (int): Target width
        height (int): Target height
        keep_aspect (bool): Whether to maintain aspect ratio
        
    Returns:
        QPixmap: The scaled pixmap, or None if scaling fails
    """
    if pixmap and not pixmap.isNull():
        aspect_ratio_mode = Qt.AspectRatioMode.KeepAspectRatio if keep_aspect else Qt.AspectRatioMode.IgnoreAspectRatio
        return pixmap.scaled(
            width, height,
            aspect_ratio_mode, Qt.TransformationMode.SmoothTransformation
        )
    return None
