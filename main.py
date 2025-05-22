#!/usr/bin/env python3
"""
Entry point for the Redshift Fitting GUI application.
"""
import sys
import logging
from PyQt5.QtWidgets import QApplication
from redshift_gui import RedshiftGUI

def main():
    """Main entry point for the application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start the application
    app = QApplication(sys.argv)
    window = RedshiftGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
