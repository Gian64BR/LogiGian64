"""Primary mouse controls are never valid macro triggers or disabled controls."""
PROTECTED_SLOTS = frozenset(('G1', 'G2', 'Principal', 'Secundario', 'Clic principal', 'Clic secundario'))


def protected_trigger(trigger):
    if not isinstance(trigger, dict):
        return False
    return (trigger.get('type') == 'gbutton' and trigger.get('button') in (0, 1) or
            trigger.get('type') == 'mouse' and trigger.get('button') in ('left', 'right'))


def protected_control(value):
    return (value.get('slot') in PROTECTED_SLOTS or
            protected_trigger(value.get('trigger', {})) or
            type(value.get('button')) is int and value['button'] in (0, 1))
