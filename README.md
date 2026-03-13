Data Processing Application

A modular Python desktop application for loading, cleaning, transforming, validating, and exporting tabular data through a GUI-driven workflow.

The application is built with PySide6 and is primarily designed for operational data processing tasks such as preparing mailing files, generating ecommerce files, packaging outputs, and querying internal reference databases.

The system provides structured workflows that guide users through common processing tasks while keeping the codebase maintainable through clear separation of responsibilities.

Features

The application allows users to:

Load CSV, TXT, and Excel files

Automatically detect and normalize headers

Clean and standardize tabular data

Configure processing through schema-driven dialogs

Preview and edit processed data before export

Resolve postcode / PAF issues interactively

Resolve service rule violations interactively

Generate structured operational output files

Query and maintain local reference databases

Produce ZIP packages and PDF print jobs

Log diagnostics during processing

Available Workflows

The application currently provides the following workflows:

Workflow	Purpose
Create File	Standard data preparation workflow
Create E-Commerce File	Build ecommerce upload files with validation and resolution tools
Split File	Divide large datasets into smaller files
Update OUT File	Apply updates to existing OUT files
Format CSV	Reformat CSV files according to predefined rules
Create ZIP	Package files into ZIP archives
Generate Password	Generate passwords for operational use
Print PDF	Generate or print PDF label batches
Query Databases	Inspect and query internal reference databases

Each workflow is implemented as a controller class under the workspace module.

Project Structure
```text
DATA_PROCESSING_APP/

├── main.py

├── config/
│   ├── constants.py
│   ├── schemas.py
│   ├── mailmark_logins.db
│   ├── mixed_weight_logins.db
│   ├── postcodes.db
│   ├── return_addresses.db
│   ├── seeds.db
│   └── services.db

├── gui/
│   ├── paf_resolution_table.py
│   ├── pandas_model.py
│   ├── password_broker.py
│   ├── service_resolution_table.py
│   ├── table.py
│   ├── toggle_switch.py
│   ├── window.py
│   └── dialogs/
│       ├── databases_dialog.py
│       ├── options_dialog.py
│       ├── paf_resolution_dialog.py
│       ├── preview_dialog.py
│       ├── printing_dialog.py
│       ├── service_resolution_dialog.py
│       ├── zip_dialog.py
│       └── options/
│           ├── bindings.py
│           ├── building.py
│           ├── context.py
│           ├── mutex.py
│           ├── paging.py
│           ├── rules.py
│           └── service_dimensions.py

├── processing/
│   ├── cleansing.py
│   ├── database.py
│   ├── headers.py
│   ├── loading.py
│   ├── packaging.py
│   ├── pdf_labels.py
│   ├── transforms.py
│   ├── ecommerce/
│   │   ├── defaults.py
│   │   ├── mapping.py
│   │   ├── paf_resolution.py
│   │   ├── services.py
│   │   └── transforms.py
│   └── repos/
│       ├── login_repo.py
│       ├── postcodes_repo.py
│       ├── return_addresses_repo.py
│       ├── seeds_repo.py
│       └── services_repo.py

├── utils/
│   ├── logging.py
│   ├── print_utils.py
│   └── table_utils.py

└── workspace/
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
```
Architecture

The project is divided into modules based on responsibility.

GUI Layer

gui/

Contains the main window, dialogs, table models, and UI components used for interacting with the application.

Workflow Layer

workspace/

Contains workflow controllers responsible for orchestrating user actions, dialogs, background jobs, and file exports.

Processing Layer

processing/

Contains the data processing logic used by workflows, including:

file loading

header detection

data cleansing

transformation utilities

packaging logic

PDF label generation

Ecommerce Processing

processing/ecommerce/

Contains logic specific to ecommerce file generation, including:

default column detection

field mapping

postcode / PAF resolution helpers

service validation logic

ecommerce-specific transformations

Repository Layer

processing/repos/

Provides structured access to local SQLite reference databases, including:

login credentials

postcode references

service definitions

return addresses

seed data

Configuration

config/

Contains application constants, schema definitions for configuration dialogs, and bundled SQLite databases used by the system.

Utilities

utils/

Shared helper functions used across the project, including logging, table utilities, and printing helpers.

Requirements

Python 3.10+

Windows (GUI focused)

Install dependencies:

pip install -r requirements.txt
Running the Application

From the project root:

python main.py
