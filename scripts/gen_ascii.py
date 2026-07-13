#!/usr/bin/env python3
"""
gen_ascii.py — Convertit une image en portrait ASCII animé façon terminal (SVG).
Usage:
    python gen_ascii.py <image_in> <svg_out> [--cols N] [--title "texte"]

Génère un SVG avec animation "machine à écrire" (chaque ligne se dessine
de gauche à droite avec un curseur clignotant), identique à l'esthétique
des profils GitHub self-generating.
"""
import sys, html, argparse
from PIL import Image, ImageOps, ImageEnhance

# Rampe de densité : du plus sombre (espace) au plus lumineux (dense).
# L'image est un hacker BLANC sur fond NOIR -> le personnage prend les
# glyphes denses, le fond reste vide. Rampe soignée à 10 niveaux.
RAMP = " .':-+*oO#@"

def image_to_ascii(path, cols=92, char_aspect=0.52, contrast=1.25, autocrop=True):
    img = Image.open(path).convert("L")

    if autocrop:
        # Recadre sur la boîte englobante de la zone lumineuse (le hacker),
        # avec une petite marge, pour maximiser le détail.
        thresh = img.point(lambda p: 255 if p > 28 else 0)
        bbox = thresh.getbbox()
        if bbox:
            pad_x = int((bbox[2] - bbox[0]) * 0.04)
            pad_y = int((bbox[3] - bbox[1]) * 0.04)
            l = max(bbox[0] - pad_x, 0)
            t = max(bbox[1] - pad_y, 0)
            r = min(bbox[2] + pad_x, img.width)
            b = min(bbox[3] + pad_y, img.height)
            img = img.crop((l, t, r, b))

    # Boost de contraste pour bien séparer le sujet du fond.
    img = ImageEnhance.Contrast(img).enhance(contrast)

    w, h = img.size
    rows = max(1, int(cols * (h / w) * char_aspect))
    img = img.resize((cols, rows), Image.LANCZOS)
    px = img.load()

    n = len(RAMP) - 1
    lines = []
    for y in range(rows):
        row_chars = []
        for x in range(cols):
            lum = px[x, y]  # 0..255
            # gamma léger pour éclaircir les demi-teintes du personnage
            v = (lum / 255) ** 0.85
            row_chars.append(RAMP[int(v * n + 0.5)])
        # supprime les espaces de fin pour un rendu propre
        lines.append("".join(row_chars).rstrip())
    # retire les lignes entièrement vides en haut/bas
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def ascii_to_svg(lines, out_path, title="kossivi@github: ~$ ./identity.sh",
                 font_size=12.0, pad=20, line_gap=15, per_line=0.055):
    cols = max((len(l) for l in lines), default=1)
    char_w = font_size * 0.60
    text_w = max(cols * char_w, 480)
    header_h = 34
    body_top = header_h + 6
    height = body_top + len(lines) * line_gap + pad
    width = int(text_w + pad * 2)

    # Dégradé vertical par ligne : vert néon -> cyan, pour un look "hacker".
    def line_color(i, total):
        t = i / max(total - 1, 1)
        # interpolation #39d353 (vert) -> #2dd4bf (teal) -> #58a6ff (bleu)
        stops = [(0x39, 0xd3, 0x53), (0x2d, 0xd4, 0xbf), (0x58, 0xa6, 0xff)]
        if t <= 0.5:
            a, b, k = stops[0], stops[1], t / 0.5
        else:
            a, b, k = stops[1], stops[2], (t - 0.5) / 0.5
        r = int(a[0] + (b[0] - a[0]) * k)
        g = int(a[1] + (b[1] - a[1]) * k)
        bl = int(a[2] + (b[2] - a[2]) * k)
        return f"#{r:02x}{g:02x}{bl:02x}"

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{int(height)}" '
        f'viewBox="0 0 {width} {int(height)}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
    )
    # fond + cadre
    parts.append(
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#060a10"/>'
        '</linearGradient>'
        '<linearGradient id="glow" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#39d353"/><stop offset="1" stop-color="#58a6ff"/>'
        '</linearGradient>'
        '</defs>'
    )
    parts.append(f'<rect width="{width}" height="{int(height)}" rx="12" fill="url(#bg)"/>')
    parts.append(f'<rect x="0.75" y="0.75" width="{width-1.5}" height="{int(height)-1.5}" '
                 f'rx="12" fill="none" stroke="url(#glow)" stroke-width="1.5" stroke-opacity="0.6"/>')
    # barre de titre
    parts.append(f'<line x1="0" y1="{header_h}" x2="{width}" y2="{header_h}" stroke="#1f6feb" stroke-opacity="0.35"/>')
    parts.append('<circle cx="22" cy="17" r="5.5" fill="#ff5f56"/>')
    parts.append('<circle cx="40" cy="17" r="5.5" fill="#ffbd2e"/>')
    parts.append('<circle cx="58" cy="17" r="5.5" fill="#27c93f"/>')
    parts.append(f'<text x="{width/2:.1f}" y="21.5" fill="#7d8590" font-size="12.5" '
                 f'text-anchor="middle">{html.escape(title)}</text>')

    total = len(lines)
    for i, line in enumerate(lines):
        y_line = body_top + i * line_gap
        begin = i * per_line
        col = line_color(i, total)
        safe = html.escape(line) if line else " "
        clip_id = f"cl{i}"
        # clip qui s'ouvre en largeur = effet frappe
        parts.append(
            f'<clipPath id="{clip_id}"><rect x="{pad}" y="{y_line-line_gap+3}" height="{line_gap}" width="0">'
            f'<animate attributeName="width" from="0" to="{text_w:.0f}" begin="{begin:.3f}s" dur="0.06s" fill="freeze"/>'
            f'</rect></clipPath>'
        )
        parts.append(
            f'<g clip-path="url(#{clip_id})"><text xml:space="preserve" x="{pad}" y="{y_line:.1f}" '
            f'fill="{col}" font-size="{font_size}" textLength="{len(line)*char_w:.1f}" '
            f'lengthAdjust="spacing">{safe}</text></g>'
        )

    # curseur clignotant final
    last_y = body_top + (total - 1) * line_gap
    end = total * per_line
    parts.append(
        f'<rect x="{pad}" y="{last_y-line_gap+4}" width="{char_w:.0f}" height="{line_gap-2}" fill="#39d353" opacity="0">'
        f'<set attributeName="opacity" to="0.9" begin="{end:.3f}s"/>'
        f'<animate attributeName="opacity" values="0.9;0.1;0.9" dur="1.05s" begin="{end:.3f}s" repeatCount="indefinite"/>'
        f'</rect>'
    )
    parts.append('</svg>')

    svg = "".join(parts)
    with open(out_path, "w") as f:
        f.write(svg)
    return width, int(height), cols, total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image_in")
    ap.add_argument("svg_out")
    ap.add_argument("--cols", type=int, default=92)
    ap.add_argument("--title", default="kossivi@github: ~$ ./identity.sh")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    lines = image_to_ascii(args.image_in, cols=args.cols)
    if args.preview:
        print("\n".join(lines))
        print(f"\n[{len(lines)} lignes x {max(len(l) for l in lines)} colonnes]")
    w, h, c, r = ascii_to_svg(lines, args.svg_out, title=args.title)
    print(f"SVG écrit -> {args.svg_out}  ({w}x{h}, {c} cols x {r} lignes)")
