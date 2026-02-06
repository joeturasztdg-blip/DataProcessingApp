def color(text, c):
    if c == "red":
        return f'<span style="color:#cc0000;"><b>{text}</b></span>'
    if c == "yellow":
        return f'<span style="color:#c9a100;"><b>{text}</b></span>'
    if c == "green":
        return f'<span style="color:#0a8900;"><b>{text}</b></span>'
    return text