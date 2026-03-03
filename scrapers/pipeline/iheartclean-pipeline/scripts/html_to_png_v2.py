#!/usr/bin/env python3
"""
Convert persona icon HTML files to PNG images with transparent corners.
Uses Firefox + modified HTML for proper alpha transparency.
"""

import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

INPUT_DIR = Path("/Users/jenmurphy/Downloads")
OUTPUT_DIR = Path("/Users/jenmurphy/Downloads/persona_icons")
OUTPUT_DIR.mkdir(exist_ok=True)

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


def extract_icon_data(html_path):
    """Extract gradient colors and SVG from HTML file."""
    with open(html_path, 'r') as f:
        content = f.read()

    # Extract gradient colors
    gradient_match = re.search(
        r'radial-gradient\(circle at 30% 30%,\s*([#\w]+)\s+0%,\s*([#\w]+)\s+50%,\s*([#\w]+)\s+100%\)',
        content
    )
    colors = [gradient_match.group(i) for i in range(1, 4)] if gradient_match else ["#4a90d9", "#2d5a87", "#1a3a5c"]

    # Extract SVG content from the large icon
    svg_match = re.search(
        r'<div class="icon icon-squircle">.*?(<svg[^>]*>.*?</svg>)',
        content, re.DOTALL
    )
    svg_content = svg_match.group(1) if svg_match else ""

    return colors, svg_content


def create_transparent_html(colors, svg_content, size=140, radius=28):
    """Create minimal HTML with proper transparency for screenshot."""
    symbol_size = int(size * 0.75)
    offset = (size - symbol_size) // 2

    return f'''<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin: 0; padding: 0; }}
html, body {{
    background: transparent !important;
    width: {size}px;
    height: {size}px;
    overflow: hidden;
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
    opacity: 0.85;
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


async def main():
    """Generate all persona icon PNGs."""
    print("=" * 60)
    print("GENERATING PERSONA ICON PNGs (Firefox)")
    print("=" * 60)

    async with async_playwright() as p:
        # Use Firefox which handles transparency better
        browser = await p.firefox.launch()

        for html_file, (persona, color) in HTML_FILES.items():
            html_path = INPUT_DIR / html_file
            if not html_path.exists():
                print(f"\n  SKIP: {html_file} (not found)")
                continue

            print(f"\n{persona.title()} ({color}):")

            # Extract icon data
            colors, svg_content = extract_icon_data(html_path)
            if not svg_content:
                print(f"  ERROR: Could not extract SVG")
                continue

            # Create large icon (140px -> 280px @2x)
            large_html = create_transparent_html(colors, svg_content, size=140, radius=28)
            large_temp = OUTPUT_DIR / f"_temp_large_{persona}_{color}.html"
            large_temp.write_text(large_html)

            page = await browser.new_page(viewport={"width": 140, "height": 140})
            await page.goto(f"file://{large_temp}")
            await page.wait_for_load_state("networkidle")

            large_output = OUTPUT_DIR / f"{persona}_{color}_large.png"
            await page.screenshot(
                path=str(large_output),
                omit_background=True,
                scale="device"
            )
            # Take at 2x for retina
            await page.set_viewport_size({"width": 280, "height": 280})
            await page.evaluate("document.body.style.transform = 'scale(2)'; document.body.style.transformOrigin = 'top left';")
            await page.screenshot(
                path=str(large_output),
                omit_background=True,
                clip={"x": 0, "y": 0, "width": 280, "height": 280}
            )
            print(f"  Created: {large_output.name} (280x280)")
            await page.close()
            large_temp.unlink()

            # Create small icon (35px -> 70px @2x)
            small_html = create_transparent_html(colors, svg_content, size=35, radius=7)
            small_temp = OUTPUT_DIR / f"_temp_small_{persona}_{color}.html"
            small_temp.write_text(small_html)

            page = await browser.new_page(viewport={"width": 70, "height": 70})
            await page.goto(f"file://{small_temp}")
            await page.evaluate("document.body.style.transform = 'scale(2)'; document.body.style.transformOrigin = 'top left';")
            await page.wait_for_load_state("networkidle")

            small_output = OUTPUT_DIR / f"{persona}_{color}_small.png"
            await page.screenshot(
                path=str(small_output),
                omit_background=True,
                clip={"x": 0, "y": 0, "width": 70, "height": 70}
            )
            print(f"  Created: {small_output.name} (70x70)")
            await page.close()
            small_temp.unlink()

        await browser.close()

    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
