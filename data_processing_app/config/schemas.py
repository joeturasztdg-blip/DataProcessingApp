from config.seeds import seed_dict, split_seed_dict

CHANGE_DELIM_SCHEMA = [
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output Delimiter",
        "options": [
            ("Comma (,)", ","),
            ("Semicolon (;)", ";"),
            ("Tab", "\t"),
            ("Pipe (|)", "|")
        ],
        "default": ","
    }
]

CREATE_FILE_SCHEMA = [
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
                "key": "cell_name"
            }
        },
        "default": "off"
    },
    {
        "type": "toggle_select",
        "key": "seeds",
        "label": "Seed Settings",
        "toggle": {"off": "None", "on": "Append Seeds"},
        "options": [
            {"label": f"{k}: {seed_dict[k][0]}", "value": k}
            for k in seed_dict
        ],
        "default": "off"
    },
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output Delimiter",
        "options": [
            ("Comma (,)", ","),
            ("Semicolon (;)", ";"),
            ("Tab", "\t"),
            ("Pipe (|)", "|")
        ],
        "default": ","
    }
]

SPLIT_ZONES_SCHEMA = [
    {
        "type": "toggle_select",
        "key": "seeds",
        "label": "Seed Settings",
        "toggle": {"off": "No seeds", "on": "Add seeds"},
        "options": [
            {"label": f"{k}: {split_seed_dict[k][0]}", "value": k}
            for k in split_seed_dict
        ],
        "default": "off"
    },
    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output Delimiter",
        "options": [
            ("Comma (,)", ","),
            ("Semicolon (;)", ";"),
            ("Tab", "\t"),
            ("Pipe (|)", "|")
        ],
        "default": ","
    }
]

UPDATE_OUT_FILE_SCHEMA = [
    {
        "type": "radio_with_extras",
        "key": "ucid_updates",
        "label": "UCID Updates",
        "options": [
            {
                "label": "None",
                "value": "none"
            },
            {
                "label": "1 UCID",
                "value": "1",
                "extras": [
                    {
                        "type": "text",
                        "label": "UCID",
                        "key": "ucid1",
                        "indent": True
                    }
                ]
            },
            {
                "label": "2 UCIDs",
                "value": "2",
                "extras": [
                    {
                        "type": "text",
                        "label": "UCID 1",
                        "key": "ucid1",
                        "indent": True
                    },
                    {
                        "type": "text",
                        "label": "UCID 2",
                        "key": "ucid2",
                        "indent": True
                    }
                ]
            }
        ],
        "default": "none"
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
        "default": "none"
    },

    {
        "type": "radio",
        "key": "delimiter",
        "label": "Output Delimiter",
        "options": [
            ("Comma (,)", ","),
            ("Semicolon (;)", ";"),
            ("Tab", "\t"),
            ("Pipe (|)", "|")
        ],
        "default": ","
    }
]

CREATE_ZIP_SCHEMA = [
    {
        "type": "radio_with_extras",
        "key": "password_mode",
        "label": "ZIP Password",
        "options": [
            {
                "label": "Generate random password",
                "value": "random",
                "extras": []
            },
            {
                "label": "Enter password",
                "value": "manual",
                "extras": [
                    {
                        "type": "text",
                        "label": "Password",
                        "key": "password"
                    }
                ]
            }
        ],
        "default": "random"
    }
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
        "default": True
    }
]
