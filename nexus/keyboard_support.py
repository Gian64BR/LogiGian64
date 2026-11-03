"""Keyboard assignment is limited to the twelve function keys."""
FUNCTION_KEYS = {f'F{number}': 111 + number for number in range(1, 13)}


def function_key(vk):
    return type(vk) is int and 112 <= vk <= 123


def is_kumara(device):
    import re
    name = re.sub(r'[^a-z0-9]', '', device.name.casefold())
    return device.kind == 'keyboard' and ('redragon' in name or 'reddragon' in name) and 'k552rgb1' in name
