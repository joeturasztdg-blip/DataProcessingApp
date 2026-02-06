Data Processing Application

This is a modular Python application used for loading, cleaning, transforming, and exporting tabular data files through a simple GUI-driven workflow.
The project originally started as a single Python script and was later refactored into a multi-package structure to keep things maintainable as the codebase grew.

The application allows users to:
Select CSV, TXT, or Excel files from a GUI
Automatically detect and clean headers
Run a data-cleansing and transformation pipeline
Apply schema-driven rules
Package and export processed files
Log actions and diagnostics during processing

Project layout:
data_processing_app/
├── main.py        – entry point for the application
├── config/        – constants, schemas, and seed data
├── gui/           – windows, dialogs, and UI models
├── processing/   – core processing logic
├── utils/        – shared helpers used across the app
└── README.md

Requirements:
Python 3.10 or newer
Windows (GUI focused)

Install dependencies:
pip install -r requirements.txt

Running the app

From the project root:
python main.py

How it’s structured:
The code is organised into separate modules based on responsibility:
The GUI handles user interaction
The processing layer contains the main business logic
Config holds schemas and constants
Utils contains shared helpers used throughout the project

This keeps things easier to reason about and avoids everything living in one huge file.
