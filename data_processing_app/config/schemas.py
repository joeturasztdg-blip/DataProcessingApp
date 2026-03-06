from config.constants import DELIMITER_OPTIONS

EDIT_CSV_FORMAT_SCHEMA = [
    {
        "type": "radio",
        "key": "header_cleaning",
        "label": "Header cleaning",
        "options": [
            ("None", "none"),
            ("Remove _", "underscore"),
            ("Remove .", "dot"),
        ],
        "default": "none",
    },
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output delimiter",
        "options": DELIMITER_OPTIONS,
        "default": ",",
    },
]

def _standard_default(standard_options):
    standard_options = standard_options or []
    return next(
        (o.get("value") for o in standard_options
            if str(o.get("label", "")).strip().lower() == "admail"),
        (standard_options[0].get("value") if standard_options else None))

def _seed_block(*, standard_options, bespoke_options, toggle_off_text, toggle_on_text):
    standard_options = standard_options or []
    bespoke_options = bespoke_options or []

    bespoke_opts_with_none = [{"label": "- None -", "value": "__none__"}] + bespoke_options

    return {
        "type": "toggle_select",
        "key": "seeds",
        "label": "Seed Settings",
        "toggle": {"off": toggle_off_text, "on": toggle_on_text},
        "options": [],
        "default": "off",
        "extra": {
            "__enabled__": [
                {
                    "type": "select",
                    "label": "Standard",
                    "key": "standard_seed",
                    "options": standard_options,
                    "default": _standard_default(standard_options),
                },
                {
                    "type": "select",
                    "label": "Bespoke",
                    "key": "bespoke_seed",
                    "options": bespoke_opts_with_none,
                    "default": "__none__",
                },
            ]
        },
    }

def build_create_ecommerce_file_schema(*, column_options, preview_rows=None):
    return [
        {
            "type": "table_preview",
            "key": "file_preview",
            "label": "Preview (first 10 rows)",
            "rows": preview_rows or [],
        },
        {
            "type": "section",
            "label": "Address Fields (Fields marked with * are mandatory)",
            "children": [
                {
                    "type": "range_select",
                    "key": "address_fields",
                    "start_key": "address_start",
                    "end_key": "address_end",
                    "start_label": "Address Start*",
                    "end_label": "Address End*",
                    "options": column_options,
                    "default_start": "__select__",
                    "default_end": "__select__",
                    "required_keys": ["address_start", "address_end"],
                },
                {
                    "type": "compact_select_row",
                    "children": [
                        {
                            "type": "compact_select",
                            "key": "postcode_column",
                            "label": "Postcode*",
                            "options": column_options,
                            "default": "__select__",
                            "required": True,
                        },
                        {
                            "type": "compact_select",
                            "key": "town_column",
                            "label": "Town*",
                            "options": column_options,
                            "default": "__select__",
                            "required": True,
                        },
                        {
                            "type": "compact_select",
                            "key": "county_column",
                            "label": "County",
                            "options": column_options,
                            "default": "__select__",
                            "required": False,
                        },
                    ],
                },
            ],
        },
        {
            "type": "section",
            "label": "Information",
            "children": [
                {
                    "type": "switch_with_extras",
                    "key": "reference_mode",
                    "default": "a",
                    "state_name_a": "Select Reference Column",
                    "state_name_b": "Enter Reference",
                    "control_a": {
                        "type": "compact_select",
                        "key": "reference_column",
                        "label": "",
                        "options": column_options,
                        "default": "__select__",
                    },
                    "control_b": {
                        "type": "text",
                        "key": "reference_text",
                        "label": "",
                        "default": "",
                    },
                },
            ],
        },
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]

def build_create_file_schema(*, standard_options, bespoke_options):
    return [
        {
            "key": "header_cleaning",
            "type": "radio",
            "label": "Header cleaning",
            "default": "none",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "Remove _", "value": "underscore"},
                {"label": "Remove .", "value": "dot"},
            ],
        },
        {
            "type": "toggle_select",
            "key": "mmi",
            "label": "MMI Settings",
            "toggle": {"off": "None", "on": "Append MMI"},
            "options": ["Coopers", "Scotts", "ProHub DMS"],
            "extra": {
                "Scotts": {
                    "type": "text",
                    "label": "Cell name",
                    "key": "cell_name",
                }
            },
            "default": "off",
        },
        _seed_block(
            standard_options=standard_options,
            bespoke_options=bespoke_options,
            toggle_off_text="None",
            toggle_on_text="Append Seeds",
        ),
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output Delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]

def build_split_file_schema(*, standard_options, bespoke_options):
    standard_options = standard_options or []
    bespoke_options = bespoke_options or []

    bespoke_opts_with_none = [{"label": "- None -", "value": "__none__"}] + bespoke_options

    return [
        # -------------------- split mode --------------------
        {
            "type": "radio",
            "key": "split_mode",
            "label": "Split mode",
            "options": [
                ("Split by column", "column"),
                ("Split by number of items", "items"),
            ],
            "default": "column",
        },

        # -------------------- split by items --------------------
        {
            "type": "number",
            "key": "items_file1",
            "label": "File 1 items",
            "default": 0,
            "min": 0,
            "visible_if": {"key": "split_mode", "op": "==", "value": "items"},
        },
        {
            "type": "number",
            "key": "items_file2",
            "label": "File 2 items",
            "default": 0,
            "min": 0,
            "visible_if": {"key": "split_mode", "op": "==", "value": "items"},
        },

        # -------------------- split by column --------------------
        {
            "type": "select",
            "key": "split_column",
            "label": "Column to split by",
            "options": [],
            "default": "__select__",
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "radio",
            "key": "split_count",
            "label": "Number of files",
            "options": [("2", 2), ("3", 3), ("4", 4), ("5", 5)],
            "default": 2,
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },

        # -------------------- file value selectors --------------------
        {
            "type": "multi_select",
            "key": "file1_values",
            "label": "File 1",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "multi_select",
            "key": "file2_values",
            "label": "File 2",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_mode", "op": "==", "value": "column"},
        },
        {
            "type": "multi_select",
            "key": "file3_values",
            "label": "File 3",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 3},
        },
        {
            "type": "multi_select",
            "key": "file4_values",
            "label": "File 4",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 4},
        },
        {
            "type": "multi_select",
            "key": "file5_values",
            "label": "File 5",
            "options": [],
            "default": [],
            "depends_on": "split_column",
            "page_group": "split_files",
            "visible_if": {"key": "split_count", "op": ">=", "value": 5},
        },
        # -------------------- Append MMI --------------------
        {
            "type": "toggle_select",
            "key": "mmi",
            "label": "MMI",
            "toggle": {"off": "None", "on": "Append"},
            "options": [
                ("Coopers", "Coopers"),
                ("Scotts", "Scotts"),
                ("ProHub DMS", "ProHub DMS"),
            ],
            "extra": {
                "Scotts": [
                    {
                        "type": "text",
                        "key": "cell_name",
                        "label": "Cell name",
                    }
                ]
            },
        },
        # -------------------- Append Seeds --------------------
        {
            "type": "radio_with_extras",
            "key": "seeds_mode",
            "label": "Seed Settings",
            "orientation": "horizontal",
            "disable_value": "none",
            "options": [
                {"label": "No Seeds", "value": "none", "extras": []},
                {"label": "First File", "value": "file1", "extras": []},
                {"label": "All Files", "value": "all", "extras": []},
            ],
            "default": "none",
            "shared_extras": [
                {
                    "type": "select",
                    "label": "Standard",
                    "key": "standard_seed",
                    "options": standard_options,
                    "default": None,
                },
                {
                    "type": "select",
                    "label": "Bespoke",
                    "key": "bespoke_seed",
                    "options": bespoke_opts_with_none,
                    "default": "__none__",
                },
            ],
        },

        # -------------------- delimiter --------------------
        {
            "type": "radio",
            "key": "delimiter",
            "label": "Output Delimiter",
            "options": DELIMITER_OPTIONS,
            "default": ",",
        },
    ]

UPDATE_OUT_FILE_SCHEMA = [
    {
        "type": "radio_with_extras",
        "key": "ucid_updates",
        "label": "UCID Updates",
        "options": [
            {"label": "None", "value": "none"},
            {
                "label": "1 UCID",
                "value": "1",
                "extras": [
                    {"type": "text", "label": "UCID", "key": "ucid1", "indent": True}
                ],
            },
            {
                "label": "2 UCIDs",
                "value": "2",
                "extras": [
                    {"type": "text", "label": "UCID 1", "key": "ucid1", "indent": True},
                    {"type": "text", "label": "UCID 2", "key": "ucid2", "indent": True},
                ],
            },
        ],
        "default": "none",
    },
    {
        "type": "radio",
        "key": "barcode_padding",
        "label": "Barcode Padding",
        "options": [
            ("None", "none"),
            ("X", "X"),
            ("Z", "Z"),
        ],
        "default": "none",
    },
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output Delimiter",
        "options": DELIMITER_OPTIONS,
        "default": ",",
    },
]

PRINT_PDF_SCHEMA = [
    {
        "type": "radio",
        "key": "print_filename_label",
        "label": "Print filename label page",
        "options": [
            ("Print Filename", True),
            ("Don't Print Filename", False),
        ],
        "default": True,
    }
]