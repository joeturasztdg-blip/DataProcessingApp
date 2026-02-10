def pad_rows(rows):
    if not rows:
        return rows, 0

    max_cols = max(len(r) for r in rows)
    padded = [
        r + [""] * (max_cols - len(r))
        for r in rows
    ]
    return padded, max_cols


def trailing_empty_run(row):
    cnt = 0
    for c in reversed(row):
        if str(c).strip() == "":
            cnt += 1
        else:
            break
    return cnt


def is_duplicate_header(r1, r2):
    return [c.strip().lower() for c in r1] == [c.strip().lower() for c in r2]
