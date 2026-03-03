#!/usr/bin/env python3
"""
Convert persona icon HTML files to PNG with transparent corners.
Uses Chromium screenshot + PIL post-processing to add alpha mask.
"""

import asyncio
import re
from pathlib import Path
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

INPUT_DIR = Path("/Users/jenmurphy/Downloads/files (4)")
OUTPUT_DIR = Path("/Users/jenmurphy/Downloads/persona_icons")
OUTPUT_DIR.mkdir(exist_ok=True)

HTML_FILES = {
    "Persona-Skeptic-White-Icon-Export.html": ("skeptic", "white"),
    "Persona-Skeptic-Black-Icon-Export.html": ("skeptic", "black"),
    "Persona-Inclusion-White-Icon-Export.html": ("inclusion", "white"),
    "Persona-Inclusion-Black-Icon-Export.html": ("inclusion", "black"),
    "Persona-Gentle-White-Icon-Export.html": ("gentle", "white"),
    "Persona-Gentle-Black-Icon-Export.html": ("gentle", "black"),
    "Persona-Gen-Z-White-Icon-Export.html": ("genz", "white"),
    "Persona-Gen-Z-White-Icon-Export.html:black": ("genz", "black"),
    "Persona-Family-White-Icon-Export.html": ("family", "white"),
    "Persona-Family-Black-Icon-Export.html": ("family", "black"),
    "Persona-Professional-White-Icon-Export.html": ("professional", "white"),
    "Persona-Professional-Black-Icon-Export.html": ("professional", "black"),
}


def extract_icon_data(html_path, symbol_color_variant):
    """Extract gradient colors and SVG from HTML file."""
    with open(html_path, 'r') as f:
        content = f.read()

    gradient_match = re.search(
        r'radial-gradient\(circle at 30% 30%,\s*([#\w]+)\s+0%,\s*([#\w]+)\s+50%,\s*([#\w]+)\s+100%\)',
        content
    )
    colors = [gradient_match.group(i) for i in range(1, 4)] if gradient_match else ["#4a90d9", "#2d5a87", "#1a3a5c"]

    # Try multiple SVG extraction patterns
    svg_match = re.search(
        r'<div class="icon-symbol">.*?(<svg[^>]*>.*?</svg>)',
        content, re.DOTALL
    )
    if not svg_match:
        svg_match = re.search(
            r'<div class="icon icon-squircle">.*?(<svg[^>]*>.*?</svg>)',
            content, re.DOTALL
        )
    if not svg_match:
        svg_match = re.search(r'(<svg[^>]*>.*?</svg>)', content, re.DOTALL)

    svg_content = svg_match.group(1) if svg_match else ""

    # Force deep black or pure white for symbol colors
    if symbol_color_variant == "black":
        svg_content = re.sub(r'fill="[^"]*"', 'fill="#000000"', svg_content)
    else:
        svg_content = re.sub(r'fill="[^"]*"', 'fill="#FFFFFF"', svg_content)

    return colors, svg_content


def create_icon_html(colors, svg_content, size=140, radius=28):
    """Create HTML for the icon."""
    symbol_size = int(size * 0.75)
    offset = (size - symbol_size) // 2

    return f'''<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    width: {size}px;
    height: {size}px;
    overflow: hidden;
    background: white;
}}
.icon {{
    width: {size}px;
    height: {size}px;
    border-radius: {radius}px;
    background: radial-gradient(circle at 30% 30%, {colors[0]} 0%, {colors[1]} 50%, {colors[2]} 100%);
    position: relative;
    overflow: hidden;
}}
.icon::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg,
        rgba(255,255,255,0.5) 0%,
        rgba(255,255,255,0.25) 20%,
        rgba(255,255,255,0.05) 50%,
        rgba(0,0,0,0.05) 80%,
        rgba(0,0,0,0.2) 100%);
    border-radius: inherit;
}}
.symbol {{
    position: absolute;
    top: {offset}px;
    left: {offset}px;
    width: {symbol_size}px;
    height: {symbol_size}px;
    opacity: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.symbol svg {{
    width: 100%;
    height: 100%;
}}
</style>
</head>
<body>
<div class="icon">
    <div class="symbol">{svg_content}</div>
</div>
</body>
</html>'''


def create_rounded_mask(size, radius):
    """Create a smooth anti-aliased rounded rectangle alpha mask using supersampling."""
    # Render at 4x resolution for smooth anti-aliasing
    scale = 4
    large_size = size * scale
    large_radius = radius * scale

    mask = Image.new('L', (large_size, large_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (large_size - 1, large_size - 1)], radius=large_radius, fill=255)

    # Scale down with high-quality resampling for smooth edges
    mask = mask.resize((size, size), Image.LANCZOS)
    return mask


def apply_transparency(image_path, radius):
    """Apply smooth rounded corner transparency to an image."""
    img = Image.open(image_path).convert('RGBA')
    size = img.size[0]

    mask = create_rounded_mask(size, radius)
    img.putalpha(mask)
    img.save(image_path, 'PNG')


async def main():
    """Generate all persona icon PNGs."""
    print("=" * 60)
    print("GENERATING PERSONA ICON PNGs")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for html_file, (persona, color) in HTML_FILES.items():
            # Handle special case where we reuse an HTML file with different symbol color
            actual_file = html_file.split(":")[0]
            html_path = INPUT_DIR / actual_file
            if not html_path.exists():
                print(f"\n  SKIP: {actual_file} (not found)")
                continue

            print(f"\n{persona.title()} ({color}):")

            colors, svg_content = extract_icon_data(html_path, color)
            if not svg_content:
                print(f"  ERROR: Could not extract SVG")
                continue

            # Large icon (280x280 @2x)
            large_html = create_icon_html(colors, svg_content, size=140, radius=28)
            large_temp = OUTPUT_DIR / f"_temp_{persona}_{color}.html"
            large_temp.write_text(large_html)

            page = await browser.new_page(
                viewport={"width": 140, "height": 140},
                device_scale_factor=2
            )
            await page.goto(f"file://{large_temp}")
            await page.wait_for_load_state("networkidle")

            large_output = OUTPUT_DIR / f"{persona}_{color}_large.png"
            await page.screenshot(path=str(large_output))
            await page.close()
            large_temp.unlink()

            # Apply transparency mask (280px, radius 56 for 2x)
            apply_transparency(large_output, 56)
            print(f"  Created: {large_output.name} (280x280)")

            # Small icon (70x70 @2x)
            small_html = create_icon_html(colors, svg_content, size=35, radius=7)
            small_temp = OUTPUT_DIR / f"_temp_small_{persona}_{color}.html"
            small_temp.write_text(small_html)

            page = await browser.new_page(
                viewport={"width": 35, "height": 35},
                device_scale_factor=2
            )
            await page.goto(f"file://{small_temp}")
            await page.wait_for_load_state("networkidle")

            small_output = OUTPUT_DIR / f"{persona}_{color}_small.png"
            await page.screenshot(path=str(small_output))
            await page.close()
            small_temp.unlink()

            # Apply transparency mask (70px, radius 14 for 2x)
            apply_transparency(small_output, 14)
            print(f"  Created: {small_output.name} (70x70)")

        await browser.close()

    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
