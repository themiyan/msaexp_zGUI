# NIRSpec MSA Redshift Analysis GUI

A graphical user interface for analyzing and fitting redshifts to NIRSpec MSA spectra from JWST observations.

This standalone tool provides an intuitive interface for:
- Viewing 1D and 2D spectral data
- Fitting redshifts to spectra
- Examining chi-squared plots
- Reviewing and saving metadata
- Batch processing multiple spectra

## Features
- Dark-themed modern interface
- Interactive chi-squared plot
- Galaxy image retrieval and display
- Ability to upload CSV files with redshift guesses
- Quality assessment and metadata editing

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
