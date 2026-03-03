#!/usr/bin/env python3
"""
Convert persona icon HTML files to PNG with transparent corners.
Screenshots original HTML directly to preserve liquid glass styling.
"""

import asyncio
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


def create_rounded_mask(size, radius):
    """Create a smooth anti-aliased rounded rectangle alpha mask using supersampling."""
    scale = 4
    large_size = size * scale
    large_radius = radius * scale

    mask = Image.new('L', (large_size, large_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (large_size - 1, large_size - 1)], radius=large_radius, fill=255)

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
    print("GENERATING PERSONA ICON PNGs (Liquid Glass)")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for html_file, (persona, color) in HTML_FILES.items():
            # Handle special case for reusing HTML with different symbol color
            actual_file = html_file.split(":")[0]
            override_color = html_file.split(":")[1] if ":" in html_file else None

            html_path = INPUT_DIR / actual_file
            if not html_path.exists():
                print(f"\n  SKIP: {actual_file} (not found)")
                continue

            print(f"\n{persona.title()} ({color}):")

            # Large icon (140px rendered at 2x = 280px)
            page = await browser.new_page(
                viewport={"width": 200, "height": 200},
                device_scale_factor=2
            )
            await page.goto(f"file://{html_path}")
            await page.wait_for_load_state("networkidle")

            # Force transparent background
            await page.evaluate("""
                document.body.style.background = 'transparent';
                document.documentElement.style.background = 'transparent';
            """)

            # If we need to override the symbol color (e.g., make genz black)
            if override_color == "black":
                await page.evaluate("""
                    document.querySelectorAll('path').forEach(p => {
                        p.setAttribute('fill', '#000000');
                    });
                """)

            # Screenshot the .icon element directly
            icon_element = await page.query_selector(".icon")
            if icon_element:
                large_output = OUTPUT_DIR / f"{persona}_{color}_large.png"
                await icon_element.screenshot(path=str(large_output), omit_background=True)

                # Apply smooth rounded transparency mask
                apply_transparency(large_output, 56)  # 28px radius * 2x scale
                print(f"  Created: {large_output.name} (280x280)")

            await page.close()

            # Small icon (35px rendered at 2x = 70px)
            page = await browser.new_page(
                viewport={"width": 100, "height": 100},
                device_scale_factor=2
            )
            await page.goto(f"file://{html_path}")
            await page.wait_for_load_state("networkidle")

            # Resize the icon to 35px for small version
            await page.evaluate("""
                document.body.style.background = 'transparent';
                document.documentElement.style.background = 'transparent';
                document.body.style.width = '50px';
                document.body.style.height = '50px';

                const wrapper = document.querySelector('.icon-wrapper');
                if (wrapper) wrapper.style.filter = 'none';  // Remove shadow for small

                const icon = document.querySelector('.icon');
                if (icon) {
                    icon.style.width = '35px';
                    icon.style.height = '35px';
                    icon.style.borderRadius = '7px';
                }

                const symbol = document.querySelector('.icon-symbol');
                if (symbol) {
                    symbol.style.width = '26px';
                    symbol.style.height = '26px';
                }

                const svg = document.querySelector('.icon-symbol svg');
                if (svg) {
                    svg.style.width = '26px';
                    svg.style.height = '26px';
                }
            """)

            if override_color == "black":
                await page.evaluate("""
                    document.querySelectorAll('path').forEach(p => {
                        p.setAttribute('fill', '#000000');
                    });
                """)

            icon_element = await page.query_selector(".icon")
            if icon_element:
                small_output = OUTPUT_DIR / f"{persona}_{color}_small.png"
                await icon_element.screenshot(path=str(small_output), omit_background=True)

                apply_transparency(small_output, 14)  # 7px radius * 2x scale
                print(f"  Created: {small_output.name} (70x70)")

            await page.close()

        await browser.close()

    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
