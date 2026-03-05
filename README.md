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

│   ├── mailmark_logins.db

│   ├── mixed_weight_logins.db

│   ├── postcodes.db

│   └── seeds.db

├── gui/

│   ├── __init__.py

│   ├── models.py

│   ├── options_dialog.py

│   ├── password_broker.py

│   ├── preview_dialog.py

│   ├── printing_dialog.py

│   ├── table.py

│   ├── window.py

│   └── zip_dialog.py

├── processing/

│   ├── __init__.py

│   ├── cleansing.py

│   ├── database.py

│   ├── headers.py

│   ├── loading.py

│   ├── packaging.py

│   ├── pdf_labels.py

│   ├── transforms.py

│

│   └── repos/

│       ├── __init__.py

│       ├── login_repo.py

│       ├── postcodes_repo.py

│       └── seeds_repo.py

├── utils/

│   ├── __init__.py

│   ├── logging.py

│   ├── print_utils.py

│   └── table_utils.py

└── workspace/

    ├── __init__.py

    ├── base.py

    ├── create_ecommerce_file.py

    ├── create_file.py

    ├── create_zip.py

    ├── format_csv.py

    ├── generate_password.py

    ├── jobs.py

    ├── print_pdf.py

    ├── query_databases.py

    ├── services.py

    ├── split_file.py

    └── update_out_file.py

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
