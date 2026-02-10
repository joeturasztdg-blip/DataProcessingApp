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

DATA_PROCESSING_APP/

├── main.py

├── config/

│   ├── __init__.py

│   ├── constants.py

│   ├── schemas.py

│   └── seeds.py

├── gui/

│   ├── __init__.py

│   ├── dialogs.py

│   ├── main_window.py

│   ├── models.py

│   ├── password_broker.py

│   ├── progress.py

│   └── table.py

├── processing/

│   ├── __init__.py

│   ├── cleansing.py

│   ├── headers.py

│   ├── loading.py

│   ├── packaging.py

│   └── transforms.py

└── utils/

│    ├── __init__.py
    
│    ├── col_utils.py
    
│    ├── formatting.py
    
│    ├── logging_adapter.py
    
│    ├── pdf_utils.py
    
│    └── row_utils.py
    

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
