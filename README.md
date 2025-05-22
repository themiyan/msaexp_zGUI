# NIRSpec MSA Redshift Analysis GUI

A graphical user interface for analyzing and fitting redshifts to NIRSpec MSA spectra from JWST observations.

This standalone tool is designed for astronomers working with NIRSpec Multi-Object Spectroscopy (MOS) data from the James Webb Space Telescope (JWST). It provides an intuitive interface for interactive redshift fitting and quality assessment, streamlining the process of analyzing multiple spectra from JWST observations. It is meant to provide more interactivity and ease when using msaexp. 

## Overview

The NIRSpec MSA Redshift Analysis GUI allows researchers to:
- View and analyze 1D and 2D spectral data
- Fit redshifts to spectra with interactive parameter adjustment
- Examine chi-squared plots for goodness-of-fit assessment
- Review and save quality metadata and comments
- Batch process multiple spectra for efficient workflows

## Features
- Interactive display of 1D spectral fits and 2D spectra
- Galaxy image retrieval and display from the Grizli/DJA service when available
- Ability to upload CSV files with redshift guesses (spec-z or photo-z)
- Quality assessment flags and metadata editing
- Keyboard shortcuts for quick navigation and assessment
- Batch processing capability for large datasets

## Code Structure
The application is organized into modules for maintainability:

- `main.py` - Entry point for the application
- `redshift_gui.py` - Main application class
- `config.py` - Configuration settings and constants
- `ui_components.py` - UI setup functions
- `event_handlers.py` - Event handling functions
- `file_utils.py` - File operations
- `spectrum_processing.py` - Spectrum analysis and fitting
- `visualization.py` - Plot and image handling
- `utils.py` - General utilities


## Running the Application
To run the application:

```bash
python main.py
```

Or make the script executable and run directly:

```bash
chmod +x main.py
./main.py
```

### Requirements

#### Python Environment
- Python 3.7+
- JWST calibration pipeline (`jwst`)
- MSA extraction package (`msaexp`)

#### Python Dependencies
- PyQt5 (for the GUI)
- matplotlib (for plotting)
- numpy (for numerical operations)
- astropy (for FITS handling and visualization)
- requests (for fetching galaxy images)
- Pillow (for image processing)
- pyyaml (for YAML file handling)
- pandas (for data manipulation)

#### Installation
You can install the required dependencies with pip:

```bash
pip install PyQt5 matplotlib numpy astropy requests Pillow pyyaml pandas
```

Note: The `jwst` and `msaexp` packages will require special installation procedures. Please refer to their respective documentation.

## Keyboard Shortcuts

The application supports the following keyboard shortcuts for faster workflows:

- `N` - Move to next spectrum
- `P` - Move to previous spectrum
- `F` - Refit redshift
- `1`, `2`, `3`, `9` - Set redshift confidence level
- `Ctrl+V` / `Cmd+V` - Paste redshift values (single value or comma-separated range)

## Usage Instructions

### Basic Usage
1. **Start the application** using `python main.py`
2. **Select a directory** containing NIRSpec MSA spectra using the "Select Directory" button
3. **Navigate through spectra** using the "Previous" and "Next" buttons or keyboard shortcuts (`P` and `N`)
4. **View redshift fits** in the main display
5. **Adjust redshift range** if needed and use "Refit Redshift" to recalculate
6. **Save metadata** including redshift confidence and comments

### Data Format
This tool expects NIRSpec MSA spectra processed through the JWST pipeline with:
- 1D extracted spectra in FITS format
- Associated 2D spectra (for visual inspection)
- Proper file naming conventions to associate related files

The application will look for related YAML files containing redshift fitting results from previous runs.

### Batch Processing
For processing multiple spectra:
1. Select a directory containing spectra
2. Click "Run Fit on All Missing" to process all spectra without existing redshift solutions
3. Optionally upload a CSV file with redshift guesses to initialize the fitting process

### CSV Format for Redshift Guesses
The CSV file with redshift guesses should include:
- A column with object IDs matching the spectrum filenames
- A column with redshift guesses
- Headers identifying these columns

## Troubleshooting

### Common Issues

#### Galaxy Images Not Loading
If galaxy images fail to load (HTTP 403 errors):
- Check your internet connection
- Verify that the Grizli cutout service is accessible
- Ensure the coordinates are correctly formatted in the source files

#### Missing Dependencies
If you encounter import errors:
- Make sure all required packages are installed
- Check that the versions are compatible with your Python version
- For specific error messages, check the terminal output for details

#### File Not Found Errors
If the application cannot find expected files:
- Verify that the file naming conventions match what the application expects
- Ensure that the spectrum files, 2D spectra, and any YAML files are properly located

#### Keyboard Shortcuts Not Working
If keyboard shortcuts aren't working:
- Make sure the main application window has focus
- Check if another application is capturing the key events
- Restart the application

For other issues, please refer to the logs which are printed to the console during execution.

## Acknowledgments

This tool was developed to facilitate redshift analysis of NIRSpec MSA spectra from JWST for Cycle 1 GO program 2565. It builds upon:

- The JWST data analysis pipeline
- The MSA extraction package (msaexp)
- The Grizli cutout service for galaxy image retrieval

2565 data were calibrated using upto Stage 3 using JWST pipeline and 1D optimal 1D extractions were performed using msaexp. While data reduced with msaexp can be directly used as is, if STScI jwst piepline is used, there is a sperate 1D extraction routine that needs to be run on the Stage 3 data to make the code compatible. 1D extraction code will allow users to extract one source at a time interactiveky, which should be the preferred option due to possible source contamination in the 2D spectra and to make sure optimal extraction is performed as expected. 

## Citation

If you use this tool in your research, please consider citing it and the underlying packages it depends on.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions to this project are welcome! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute.

## Installation

You can install the package using pip:

```bash
# Install directly from the repository
pip install git+https://github.com/username/msaexp_zgui.git

# Or install in development mode from a local copy
git clone https://github.com/username/msaexp_zgui.git
cd msaexp_zgui
pip install -e .
```

Replace `username` with the actual GitHub username where the repository is hosted.
