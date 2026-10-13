"""Shared palette and type for the page, figures, and recorded replays."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / 'assets/design-tokens.json').read_text())

def color(family, shade=600):
    return TOKENS['palette'][family][str(shade)]['hex']

def rgb(family, shade=200):
    value = color(family, shade)
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))

def font_path(mono=False, light=False):
    fonts = ROOT / 'assets/fonts'
    if mono:
        return str(fonts / 'B612Mono-Regular.ttf')
    stem = 'Graphik-Light' if light else 'Graphik-Regular'
    for extension in ('otf', 'ttf'):
        path = fonts / f'{stem}.{extension}'
        if path.exists():
            return str(path)
    raise FileNotFoundError(f'{stem}: provide the licensed rendering font in assets/fonts')
