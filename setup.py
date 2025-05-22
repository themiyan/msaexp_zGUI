#!/usr/bin/env python3
"""
Setup script for NIRSpec MSA Redshift Analysis GUI.

MIT License
Copyright (c) 2025 NIRSpec MSA Redshift Analysis GUI Contributors
See LICENSE file for details.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="msaexp_zgui",
    version="0.1.0",
    author="NIRSpec MSA Redshift Analysis GUI Contributors",
    author_email="",
    description="A GUI for analyzing and fitting redshifts to NIRSpec MSA spectra",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
    python_requires=">=3.7",
    install_requires=[
        "PyQt5>=5.15.0",
        "matplotlib>=3.5.0",
        "numpy>=1.20.0",
        "astropy>=5.0.0",
        "requests>=2.25.0",
        "Pillow>=8.0.0",
        "pyyaml>=6.0",
        "pandas>=1.3.0",
    ],
    entry_points={
        "console_scripts": [
            "msaexp_zgui=msaexp_zgui.main:main",
        ],
    },
)
