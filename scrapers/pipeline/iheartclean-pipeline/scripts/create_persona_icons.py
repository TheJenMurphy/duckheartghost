#!/usr/bin/env python3
"""
Create persona icon PNGs with true transparent corners using CairoSVG.
Extracts SVG paths from HTML files and renders with proper transparency.
"""

import os
import re
from pathlib import Path
import cairosvg

OUTPUT_DIR = Path("/Users/jenmurphy/Downloads/persona_icons")
OUTPUT_DIR.mkdir(exist_ok=True)

INPUT_DIR = Path("/Users/jenmurphy/Downloads")

# Map HTML files to output names
HTML_FILES = {
    "Persona-Skeptic-Black-Icon.html": ("skeptic", "black"),
    "Persona-Inclusion-White-Icon.html": ("inclusion", "white"),
    "Persona-Inclusion-Black-Icon.html": ("inclusion", "black"),
    "Persona-Gentle-White-Icon (1).html": ("gentle", "white"),
    "Persona-Gentle-Black-Icon (1).html": ("gentle", "black"),
    "Persona-Gen-Z-White-Icon.html": ("genz", "white"),
    "Persona-Family-White-Icon.html": ("family", "white"),
    "Persona-Family-Black-Icon.html": ("family", "black"),
    "Persona-Professional-White-Icon.html": ("professional", "white"),
    "Persona-Professional-Black-Icon.html": ("professional", "black"),
}


def extract_from_html(html_path):
    """Extract gradient colors and SVG path from HTML file."""
    with open(html_path, 'r') as f:
        content = f.read()

    # Extract gradient from CSS (radial-gradient in .icon class)
    gradient_match = re.search(
        r'\.icon\s*\{[^}]*background:\s*radial-gradient\(circle at 30% 30%,\s*([#\w]+)\s+0%,\s*([#\w]+)\s+50%,\s*([#\w]+)\s+100%\)',
        content, re.DOTALL
    )

    colors = None
    if gradient_match:
        colors = [gradient_match.group(1), gradient_match.group(2), gradient_match.group(3)]

    # Extract SVG path(s) from the large icon section
    svg_match = re.search(
        r'<div class="icon icon-squircle">.*?<svg[^>]*viewBox="([^"]*)"[^>]*>(.*?)</svg>',
        content, re.DOTALL
    )

    viewbox = "0 0 998.25 998.25"
    paths = []

    if svg_match:
        viewbox = svg_match.group(1)
        svg_content = svg_match.group(2)

        # Extract all path elements
        path_matches = re.findall(r'<path[^>]*d="([^"]*)"[^>]*/>', svg_content)
        paths = path_matches

    # Get symbol color
    color_match = re.search(r'fill="(#[0-9a-fA-F]+)"', content)
    symbol_color = color_match.group(1) if color_match else "#000000"

    return {
        "colors": colors,
        "viewbox": viewbox,
        "paths": paths,
        "symbol_color": symbol_color
    }


def create_icon_svg(config, size=140, radius=28):
    """Create complete SVG with squircle background and symbol."""
    colors = config["colors"]
    paths = config["paths"]
    symbol_color = config["symbol_color"]

    # Calculate symbol size and offset
    symbol_size = int(size * 0.75)
    offset = (size - symbol_size) / 2

    # Create SVG
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <radialGradient id="bg" cx="30%" cy="30%" r="70%" fx="30%" fy="30%">
      <stop offset="0%" stop-color="{colors[0]}"/>
      <stop offset="50%" stop-color="{colors[1]}"/>
      <stop offset="100%" stop-color="{colors[2]}"/>
    </radialGradient>
    <linearGradient id="glass" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="white" stop-opacity="0.5"/>
      <stop offset="20%" stop-color="white" stop-opacity="0.25"/>
      <stop offset="50%" stop-color="white" stop-opacity="0.05"/>
      <stop offset="80%" stop-color="black" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="black" stop-opacity="0.2"/>
    </linearGradient>
    <clipPath id="squircle">
      <rect x="0" y="0" width="{size}" height="{size}" rx="{radius}" ry="{radius}"/>
    </clipPath>
  </defs>

  <g clip-path="url(#squircle)">
    <!-- Gradient background -->
    <rect x="0" y="0" width="{size}" height="{size}" fill="url(#bg)"/>

    <!-- Glass overlay -->
    <rect x="0" y="0" width="{size}" height="{size}" fill="url(#glass)"/>

    <!-- Symbol -->
    <g transform="translate({offset}, {offset}) scale({symbol_size/998.25})">
'''

    for path in paths:
        svg += f'      <path fill="{symbol_color}" opacity="0.85" d="{path}"/>\n'

    svg += '''    </g>
  </g>
</svg>'''

    return svg


def main():
    """Generate all persona icons."""
    print("=" * 60)
    print("CREATING PERSONA ICON PNGs")
    print("=" * 60)

    for html_file, (persona, color) in HTML_FILES.items():
        html_path = INPUT_DIR / html_file

        if not html_path.exists():
            print(f"\n  SKIP: {html_file} (not found)")
            continue

        print(f"\n{persona.title()} ({color}):")

        # Extract info from HTML
        config = extract_from_html(html_path)

        if not config["colors"]:
            print(f"  ERROR: Could not extract gradient colors")
            continue

        if not config["paths"]:
            print(f"  ERROR: Could not extract SVG paths")
            continue

        # Create large icon (140px, 2x = 280px output)
        large_svg = create_icon_svg(config, size=140, radius=28)
        large_output = OUTPUT_DIR / f"{persona}_{color}_large.png"

        try:
            cairosvg.svg2png(
                bytestring=large_svg.encode('utf-8'),
                write_to=str(large_output),
                output_width=280,
                output_height=280
            )
            print(f"  Created: {large_output.name} (280x280)")
        except Exception as e:
            print(f"  ERROR (large): {e}")

        # Create small icon (35px, 2x = 70px output)
        small_svg = create_icon_svg(config, size=35, radius=7)
        small_output = OUTPUT_DIR / f"{persona}_{color}_small.png"

        try:
            cairosvg.svg2png(
                bytestring=small_svg.encode('utf-8'),
                write_to=str(small_output),
                output_width=70,
                output_height=70
            )
            print(f"  Created: {small_output.name} (70x70)")
        except Exception as e:
            print(f"  ERROR (small): {e}")

    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
