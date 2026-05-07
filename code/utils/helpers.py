def ask(prompt, default=None, choices=None, typ=str):
    """CLI prompt with optional default, choice list, and type coercion."""
    if choices:
        choice_str = ' / '.join(f"[{i+1}] {c}" for i, c in enumerate(choices))
        prompt = f"{prompt}\n      {choice_str}"
    if default is not None:
        prompt = f"  {prompt} (default: {default}): "
    else:
        prompt = f"  {prompt}: "

    while True:
        raw = input(prompt).strip()
        if raw == '' and default is not None:
            return default
        if choices:
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return choices[int(raw) - 1]
            matches = [c for c in choices if str(c).lower().startswith(raw.lower())]
            if len(matches) == 1:
                return matches[0]
            print(f"      Please enter a number 1-{len(choices)} or type the option.")
            continue
        try:
            return typ(raw)
        except ValueError:
            print(f"      Please enter a valid {typ.__name__}.")


def separator(title=''):
    w = 68
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"\n  {'─'*pad} {title} {'─'*pad}")
    else:
        print(f"\n  {'─'*w}")
