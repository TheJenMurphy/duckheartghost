#!/usr/bin/env python3
"""
Convert persona icon HTML files to PNG images using Playwright.
"""

import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Input files
INPUT_DIR = Path("/Users/jenmurphy/Downloads")
OUTPUT_DIR = Path("/Users/jenmurphy/Downloads/persona_icons")
OUTPUT_DIR.mkdir(exist_ok=True)

# HTML files to convert
HTML_FILES = [
    "Persona-Skeptic-Black-Icon.html",
    "Persona-Inclusion-White-Icon.html",
    "Persona-Inclusion-Black-Icon.html",
    "Persona-Gentle-White-Icon (1).html",
    "Persona-Gentle-Black-Icon (1).html",
    "Persona-Gen-Z-White-Icon.html",
    "Persona-Family-White-Icon.html",
    "Persona-Family-Black-Icon.html",
    "Persona-Professional-White-Icon.html",
    "Persona-Professional-Black-Icon.html",
]


async def capture_icon(page, html_path: Path, output_path: Path, size: int, selector: str):
    """Capture a specific icon element from the page."""
    await page.goto(f"file://{html_path}")
    await page.wait_for_load_state("networkidle")

    # Find the icon element
    element = await page.query_selector(selector)
    if element:
        await element.screenshot(path=str(output_path), omit_background=True)
        return True
    return False


async def main():
    """Generate all persona icon PNGs."""
    print("=" * 60)
    print("GENERATING PERSONA ICON PNGs")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Create page with transparent background
        page = await browser.new_page(
            viewport={"width": 400, "height": 600},
            device_scale_factor=2  # 2x for retina quality
        )

        for html_file in HTML_FILES:
            html_path = INPUT_DIR / html_file
            if not html_path.exists():
                # Try without spaces escaped
                alt_path = INPUT_DIR / html_file.replace(" ", " ")
                if alt_path.exists():
                    html_path = alt_path
                else:
                    print(f"  SKIP: {html_file} (not found)")
                    continue

            # Extract persona name and color from filename
            parts = html_file.replace(".html", "").replace(" (1)", "").split("-")
            persona = parts[1].lower()  # e.g., "skeptic", "family"
            color = parts[2].lower()    # e.g., "black", "white"

            print(f"\n{persona.title()} ({color}):")

            # Capture large icon (140px)
            large_output = OUTPUT_DIR / f"{persona}_{color}_large.png"
            try:
                await page.goto(f"file://{html_path}")
                await page.wait_for_load_state("networkidle")

                # Force transparent background and add clip-path for true squircle transparency
                await page.evaluate("""
                    document.body.style.background = 'transparent';
                    document.documentElement.style.background = 'transparent';

                    // Add clip-path to icons for true corner transparency
                    document.querySelectorAll('.icon').forEach(el => {
                        el.style.clipPath = 'inset(0 round 28px)';
                    });
                    document.querySelectorAll('.small-icon').forEach(el => {
                        el.style.clipPath = 'inset(0 round 7px)';
                    });
                """)

                # Screenshot the large icon with transparent background
                # Use .icon directly to avoid shadow wrapper issues
                large_icon = await page.query_selector(".icon")
                if large_icon:
                    await large_icon.screenshot(path=str(large_output), omit_background=True)
                    print(f"  Created: {large_output.name}")
            except Exception as e:
                print(f"  Error (large): {e}")

            # Capture small icon (35px)
            small_output = OUTPUT_DIR / f"{persona}_{color}_small.png"
            try:
                # Use .small-icon directly to avoid shadow wrapper issues
                small_icon = await page.query_selector(".small-icon")
                if small_icon:
                    await small_icon.screenshot(path=str(small_output), omit_background=True)
                    print(f"  Created: {small_output.name}")
            except Exception as e:
                print(f"  Error (small): {e}")

        await browser.close()

    print(f"\n{'=' * 60}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
