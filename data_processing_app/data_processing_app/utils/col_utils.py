import re
import pandas as pd
from collections import defaultdict

_SUFFIX_RE = re.compile(r"^(.*?)(?: \((\d+)\))?$")


def make_unique_columns(columns):
    counts = defaultdict(int)
    new_cols = []

    for col in columns:
        col = str(col).strip()

        m = _SUFFIX_RE.match(col)
        base = (m.group(1) or "").strip()
        num = m.group(2)

        if not base:
            base = "Column"

        if num is not None:
            n = int(num)
            counts[base] = max(counts[base], n + 1)
            new_cols.append(f"{base} ({n})")
            continue

        if counts[base] == 0:
            new_cols.append(base)
        else:
            new_cols.append(f"{base} ({counts[base]})")

        counts[base] += 1

    return new_cols