"""Generate matching web colors, canvas tokens, and the CLEAR favicon."""
import json
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from design_tokens import ROOT, TOKENS, color

def build():
    css = ['/* Generated from design-tokens.json. */',
           '@font-face{font-family:"B612 Mono";src:url("fonts/B612Mono-Regular.woff2") format("woff2");font-style:normal;font-weight:400;font-display:swap}',
           '@font-face{font-family:"B612 Mono";src:url("fonts/B612Mono-Bold.woff2") format("woff2");font-style:normal;font-weight:700;font-display:swap}',
           '@font-face{font-family:Graphik;src:local("Graphik Light");font-weight:300;font-style:normal;font-display:swap}',
           '@font-face{font-family:Graphik;src:local("Graphik Regular");font-weight:400;font-style:normal;font-display:swap}']
    for weight, name in [(300, 'Graphik-Light'), (400, 'Graphik-Regular')]:
        if (ROOT / f'assets/fonts/{name}.woff2').exists():
            css.append(f'@font-face{{font-family:Graphik;src:url("fonts/{name}.woff2") format("woff2");font-weight:{weight};font-style:normal;font-display:swap}}')
    css.append(':root{')
    for family, shades in TOKENS['palette'].items():
        for shade, value in shades.items():
            css.append(f'--clear-{family}-{shade}:{value["oklch"]};')
    css.append('}')
    (ROOT / 'assets/design-tokens.css').write_text('\n'.join(css)+'\n')
    data = {family: {shade: value['hex'] for shade, value in shades.items()}
            for family, shades in TOKENS['palette'].items()}
    script='window.CLEAR_DESIGN='+json.dumps(dict(colors=data,sans='Graphik, Arial, sans-serif',mono='"B612 Mono", monospace'),separators=(',',':'))+';\n'
    script+='document.fonts?.load(\'12px "B612 Mono"\').then(()=>window.dispatchEvent(new Event("resize"))).catch(()=>{});\n'
    (ROOT / 'assets/design-tokens.js').write_text(script)
    # Glyph outlines keep the small standalone SVG independent of font requests.
    path = ROOT / 'assets/fonts/Graphik-Regular.otf'
    if not path.exists(): path = ROOT / 'assets/fonts/Graphik-Regular.ttf'
    if not path.exists(): path = ROOT / 'assets/fonts/B612Mono-Regular.ttf'
    font = TTFont(path); glyphs = font.getGlyphSet(); cmap = font.getBestCmap()
    name = cmap[ord('C')]
    pen = SVGPathPen(glyphs); glyphs[name].draw(pen)
    bounds = BoundsPen(glyphs); glyphs[name].draw(bounds)
    left, bottom, right, top = bounds.bounds
    scale = 58 / (top - bottom)
    x = 50 - (left + right) * scale / 2
    y = 50 + (bottom + top) * scale / 2
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><title>CLEAR</title><rect width="100" height="100" rx="18" fill="{color("green",200)}" fill-opacity=".55"/><path fill="#111111" transform="translate({x} {y}) scale({scale} {-scale})" d="{pen.getCommands()}"/></svg>\n'
    (ROOT / 'assets/favicon.svg').write_text(svg)

if __name__ == '__main__': build()
