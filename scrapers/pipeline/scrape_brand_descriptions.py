#!/usr/bin/env python3
"""
Scrape brand about pages to populate description fields in Webflow.

Usage:
    python scrape_brand_descriptions.py
"""

import os
import re
import time
import requests
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# APIs
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
BRANDS_COLLECTION_ID = "67d1b1e4b94243aa9c881b7a"

# Brand website URLs and about page paths
BRAND_URLS = {
    "Tower 28 Beauty": {
        "website": "https://www.tower28beauty.com",
        "about": "https://www.tower28beauty.com/pages/about-us"
    },
    "Kosas": {
        "website": "https://kosas.com",
        "about": "https://kosas.com/pages/about"
    },
    "Ilia Beauty": {
        "website": "https://iliabeauty.com",
        "about": "https://iliabeauty.com/pages/about"
    },
    "RMS Beauty": {
        "website": "https://www.rmsbeauty.com",
        "about": "https://www.rmsbeauty.com/pages/about-us"
    },
    "Westman Atelier": {
        "website": "https://www.westman-atelier.com",
        "about": "https://www.westman-atelier.com/pages/the-atelier"
    },
    "Tata Harper Skincare": {
        "website": "https://tataharperskincare.com",
        "about": "https://tataharperskincare.com/pages/our-story"
    },
    "Indie Lee": {
        "website": "https://indielee.com",
        "about": "https://indielee.com/pages/about"
    },
    "True Botanicals": {
        "website": "https://truebotanicals.com",
        "about": "https://truebotanicals.com/pages/our-story"
    },
    "Osea": {
        "website": "https://oseamalibu.com",
        "about": "https://oseamalibu.com/pages/about-us"
    },
    "Marie Veronique": {
        "website": "https://www.marieveronique.com",
        "about": "https://www.marieveronique.com/pages/about-us"
    },
    "Ursa Major": {
        "website": "https://www.ursamajorvt.com",
        "about": "https://www.ursamajorvt.com/pages/about"
    },
    "lys BEAUTY": {
        "website": "https://lysbeauty.com",
        "about": "https://lysbeauty.com/pages/about-lys"
    },
    "Jillian Dempsey": {
        "website": "https://www.jilliandempsey.com",
        "about": "https://www.jilliandempsey.com/pages/about"
    },
    "Necessaire": {
        "website": "https://necessaire.com",
        "about": "https://necessaire.com/pages/about"
    },
    "Gen See": {
        "website": "https://genseebeauty.com",
        "about": "https://genseebeauty.com/pages/about"
    },
    "Mob Beauty": {
        "website": "https://mobbeauty.com",
        "about": "https://mobbeauty.com/pages/about-us"
    },
    "Grown Alchemist": {
        "website": "https://www.grownalchemist.com",
        "about": "https://www.grownalchemist.com/pages/about-us"
    },
    "Soshe Beauty": {
        "website": "https://soshebeauty.com",
        "about": "https://soshebeauty.com/pages/about"
    },
    "Finding Ferdinand": {
        "website": "https://findingferdinand.com",
        "about": "https://findingferdinand.com/pages/about-us"
    },
    "Exa": {
        "website": "https://exabeauty.com",
        "about": "https://exabeauty.com/pages/about"
    },
    "Rare Beauty": {
        "website": "https://www.rarebeauty.com",
        "about": "https://www.rarebeauty.com/pages/about"
    },
    "Rhode Skin": {
        "website": "https://www.rhodeskin.com",
        "about": "https://www.rhodeskin.com/pages/about"
    },
    "Milk makeup": {
        "website": "https://www.milkmakeup.com",
        "about": "https://www.milkmakeup.com/about-us.html"
    },
    "MERIT beauty": {
        "website": "https://meritbeauty.com",
        "about": "https://meritbeauty.com/pages/about"
    },
}

# Pre-compiled brand descriptions (from research)
BRAND_DESCRIPTIONS = {
    "Tower 28 Beauty": {
        "description": "Tower 28 is the first beauty brand that's 100% clean, vegan, and free of every known skin irritant. Founded by Amy Liu, who struggled with eczema, the brand creates makeup that's safe for even the most sensitive skin.",
        "story": "After 15 years as a beauty executive at Smashbox, Kate Somerville, and Josie Maran, founder Amy Liu launched Tower 28 in 2019. As an eczema sufferer, she couldn't find makeup that didn't irritate her skin. Tower 28 was born to prove that clean, sensitive-skin-friendly makeup can also be fun and effective. The brand also founded Clean Beauty Summer School to support BIPOC beauty founders.",
        "founded": 2019
    },
    "Kosas": {
        "description": "Kosas creates clean makeup that feels like skincare. Founded by chemist Sheena Yaitanes, the brand is known for comfortable, flattering formulas in elevated neutrals that make you look like the best version of yourself.",
        "story": "Born out of what founder Sheena Yaitanes calls 'comfy glam,' Kosas launched in 2015 with four lipsticks in flattering neutrals. With a background in biological sciences and fine arts, Yaitanes couldn't find makeup with both flattering color and comfortable formulas. The name comes from the five Koshas—layers of the self from Vedic philosophy.",
        "founded": 2015
    },
    "Ilia Beauty": {
        "description": "ILIA is a clean beauty brand that believes in skin that looks like skin. Founded by Sasha Plavsic in 2011, ILIA creates makeup powered by skincare actives for a naturally radiant look.",
        "story": "ILIA started when founder Sasha Plavsic's mother encouraged her to read the ingredient list on her favorite lip balm. Shocked by what she found, Sasha set out to recreate her favorite products using safe, natural ingredients. What began as a single lip balm in her Vancouver garage has grown into a full line of award-winning clean beauty products.",
        "founded": 2011
    },
    "RMS Beauty": {
        "description": "RMS Beauty pioneered the clean beauty movement. Founded in 2009 by celebrity makeup artist Rose-Marie Swift, RMS creates organic, non-toxic makeup that enhances natural beauty while nourishing the skin.",
        "story": "Rose-Marie Swift, a master makeup artist for over 30 years who worked with Gisele Bündchen and Miranda Kerr, experienced mysterious health problems in her late 30s. Lab tests revealed high levels of chemicals—which her doctor traced to cosmetics. Swift went on to create RMS Beauty, proving that makeup could be both beautiful and safe.",
        "founded": 2009
    },
    "Westman Atelier": {
        "description": "Westman Atelier offers clean luxury makeup created by celebrity makeup artist Gucci Westman. The brand is known for its you-but-better aesthetic and formulas made with nourishing ingredients.",
        "story": "Gucci Westman, one of the most sought-after makeup artists in the world, launched Westman Atelier in 2018 with her husband David Neville (co-founder of Rag & Bone). After stints as artistic director for Lancôme and Revlon, Westman wanted to create a clean luxury line that reflected her signature natural, radiant aesthetic.",
        "founded": 2018
    },
    "Tata Harper Skincare": {
        "description": "Tata Harper Skincare is 100% natural, nontoxic, high-performance luxury skincare made on an organic farm in Vermont. Every product is ECOCERT certified, cruelty-free, and made with non-GMO ingredients.",
        "story": "When Tata Harper's stepfather was diagnosed with cancer, she discovered how many harmful ingredients were hidden in everyday products. Unable to find 100% natural products that met her standards, she founded Tata Harper Skincare in 2010 on her 1,200-acre Vermont organic farm, where every product is still conceived, produced, and packaged today.",
        "founded": 2010
    },
    "Indie Lee": {
        "description": "Indie Lee creates clean, naturally-derived skincare products that are safe and effective. Founded after a life-changing brain tumor diagnosis, the brand is dedicated to educating and empowering people to live their healthiest lives.",
        "story": "In 2008, Indie Lee was diagnosed with a life-threatening brain tumor believed to be environmentally derived. Given six months to live, she underwent successful surgery on Earth Day 2009. When her doctor asked 'What do you put on your skin?', it sparked a mission. Indie Lee launched in 2010 to create clean products and raise awareness about ingredient safety.",
        "founded": 2010
    },
    "True Botanicals": {
        "description": "True Botanicals creates luxury clean skincare that's clinically proven to outperform conventional products. Every product is MADE SAFE certified, EWG Verified, and cruelty-free.",
        "story": "After being diagnosed with thyroid cancer at 32, founder Hillary Peterson took a hard look at the products she was using. Unable to find clean skincare that actually worked, she founded True Botanicals to prove that prioritizing health doesn't mean sacrificing results. The brand became the first to clinically prove clean products can outperform conventional alternatives.",
        "founded": 2014
    },
    "Osea": {
        "description": "OSEA creates seaweed-powered skincare that harnesses the healing power of the ocean. Founded in 1996, this family-owned brand has grown from kitchen-sink formulations to a beloved clean beauty line.",
        "story": "OSEA—meaning ocean, sun, earth, and atmosphere—was inspired by founder Jenefer Palmer's grandmother, who turned to the sea for healing after an accident. Started in 1996 from Jenefer's kitchen sink, the family-owned brand is now led by her daughter Melissa as CEO. The Palmers bootstrapped for 24 years to maintain ingredient quality and control their destiny.",
        "founded": 1996
    },
    "Marie Veronique": {
        "description": "Marie Veronique creates science-backed skincare formulated for real skin issues. Founded by a chemist and former chemistry teacher, the brand pioneers microbiome-friendly and barrier-supporting formulations.",
        "story": "Marie-Veronique Nadeau, a trained esthetician with degrees in math and science, founded Marie Veronique in 2002 after struggling with rosacea. The former high school chemistry teacher couldn't find products that were both clean and effective, so she created her own. She collaborates with her daughter, a physicist and biomedical engineer, on formulations.",
        "founded": 2002
    },
    "Ursa Major": {
        "description": "Ursa Major makes forest-infused, adventure-inspired clean skincare essentials from Waterbury, Vermont. The brand is a Certified B Corp with a score of 96.6.",
        "story": "Founded in 2010 by Emily Doyle and Oliver Sweatman—two beauty industry veterans who became disenchanted with the lack of integrity in the business—Ursa Major creates skincare that captures the restorative power of the great outdoors. Based in Vermont, the brand earned B Corp certification in 2020 after working toward it for a decade.",
        "founded": 2010
    },
    "lys BEAUTY": {
        "description": "LYS Beauty (Love Yourself) is the first Black-owned clean beauty brand to launch at Sephora. Founded by Tisha Thompson, the brand creates affordable, high-performance makeup for all skin types and tones.",
        "story": "After 15 years in the beauty industry as a makeup artist and VP of Marketing at PÜR, Tisha Thompson launched LYS Beauty in 2021 to dispel the myth that clean beauty, deep shade ranges, and high-performance products at affordable prices cannot coexist. The brand addresses specific concerns like hyperpigmentation and sensitive skin.",
        "founded": 2021
    },
    "Jillian Dempsey": {
        "description": "Jillian Dempsey creates clean makeup, skincare, and haircare that translates A-list artistry into everyday wear. Founded by celebrity makeup artist Jillian Dempsey, the brand is known for its viral Gold Bar.",
        "story": "With 30+ years as a celebrity makeup artist working with Kristen Stewart, Emilia Clarke, and photographed by Annie Leibovitz, Jillian Dempsey launched her eponymous line in 2015. She wanted to share her professional techniques and clean formulas with everyone. Her Japanese-crafted Gold Bar has become a viral sensation.",
        "founded": 2015
    },
    "Necessaire": {
        "description": "Nécessaire is a Certified B Corp body care brand that takes a skincare approach to the body. Founded by Randi Christiansen, the brand is Climate Neutral certified and a 1% For The Planet member.",
        "story": "Randi Christiansen spent 15 years at Estée Lauder Companies working on La Mer and Tom Ford before co-founding Nécessaire in 2018 with Nick Axelrod-Welk. The brand was born from a conversation in the Seoul airport about creating thoughtful body care. Nécessaire achieved B Corp certification in 2022 with an impressive score of 98.4.",
        "founded": 2018
    },
    "Gen See": {
        "description": "Gen See creates clean, effective makeup with a focus on multi-use products. The Latina-owned brand believes beauty should be simple, sustainable, and accessible.",
        "story": "Founded by Gina Mari, Gen See (a play on 'Gina, see') is a Latina-owned clean beauty brand focused on multi-functional products that simplify beauty routines. The brand emphasizes inclusivity and sustainability while making clean beauty accessible.",
        "founded": 2020
    },
    "Mob Beauty": {
        "description": "MOB Beauty is a clean makeup brand built on sustainability, offering refillable products and customizable palettes to reduce waste without compromising performance.",
        "story": "Co-founded by Shanna Duval and cosmetics industry veteran Victor Casale, MOB Beauty launched to reimagine what sustainable beauty could look like. The brand's refillable system lets customers build custom palettes, reducing packaging waste while delivering professional-quality makeup.",
        "founded": 2020
    },
    "Grown Alchemist": {
        "description": "Grown Alchemist is an Australian clean beauty brand that uses advanced natural technologies to deliver age-repair and wellness benefits through skincare, body care, and hair care.",
        "story": "Founded in Melbourne, Australia, Grown Alchemist combines cutting-edge biotechnology with natural ingredients to create products that work at a cellular level. The brand's philosophy centers on the belief that skin can be treated and repaired using advanced natural formulations.",
        "founded": 2008
    },
    "Rare Beauty": {
        "description": "Rare Beauty, founded by Selena Gomez, celebrates individuality and challenges unrealistic beauty standards. The brand donates 1% of sales to the Rare Impact Fund supporting mental health.",
        "story": "Selena Gomez launched Rare Beauty in 2020 with a mission to break down unrealistic standards of perfection. The brand's name comes from her third studio album and embodies the idea that being rare is about accepting yourself. Through the Rare Impact Fund, the brand has committed $100 million over 10 years to mental health services.",
        "founded": 2020
    },
    "Rhode Skin": {
        "description": "Rhode is a skincare brand founded by Hailey Bieber focused on glazed, dewy skin through barrier-supporting ingredients. The brand emphasizes simple, effective routines.",
        "story": "Hailey Bieber launched Rhode in 2022, named after her middle name. The brand emerged from her personal skincare philosophy of keeping things simple while prioritizing skin barrier health. Rhode focuses on peptides and nourishing ingredients to achieve the 'glazed donut' skin Bieber is known for.",
        "founded": 2022
    },
    "Milk makeup": {
        "description": "Milk Makeup creates vegan, cruelty-free products with innovative formulas and cool-girl aesthetic. Born from Milk Studios in NYC, the brand champions self-expression and effortless beauty.",
        "story": "Milk Makeup launched in 2016 from Milk Studios, the legendary NYC creative space that has hosted everyone from Beyoncé to fashion week shows. The brand was created for the Milk community—artists, musicians, models—who needed products as hardworking and expressive as they are. 100% vegan and cruelty-free.",
        "founded": 2016
    },
    "MERIT beauty": {
        "description": "MERIT creates luxury minimalist makeup for effortless beauty. The brand focuses on fewer, better products that simplify routines without sacrificing quality.",
        "story": "Founded by Katherine Power (co-founder of Who What Wear), MERIT launched in 2021 as a luxury minimalist beauty brand. Frustrated by overwhelming product options, Power created a streamlined collection of multitasking essentials. MERIT proves that a complete makeup routine doesn't require dozens of products.",
        "founded": 2021
    },
    "Soshe Beauty": {
        "description": "Soshe Beauty creates clean, sustainable makeup with a focus on natural ingredients and eco-conscious packaging.",
        "story": "Soshe Beauty was founded with a commitment to clean formulas and sustainability. The female-founded brand creates makeup that's both effective and environmentally responsible.",
        "founded": 2019
    },
    "Finding Ferdinand": {
        "description": "Finding Ferdinand creates customizable, clean lip products. The brand is known for its lipstick customization bar where customers can create their perfect shade.",
        "story": "Finding Ferdinand revolutionized the lipstick experience by letting customers create their own custom shades. The female-founded brand combines clean ingredients with personalization, making each product unique to the wearer.",
        "founded": 2016
    },
    "Exa": {
        "description": "Exa Beauty creates high-performance, clean makeup designed for all skin tones. The brand focuses on inclusive shade ranges and skin-loving ingredients.",
        "story": "Exa Beauty was founded to fill the gap between clean beauty and inclusive shade ranges. The female-founded brand creates makeup that performs while caring for skin.",
        "founded": 2020
    },
}


class BrandDescriptionScraper:
    """Scrape and update brand descriptions."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _request(self, method, endpoint, data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'
        try:
            if method == 'GET':
                resp = self.session.get(url)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                return None
            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data)
            if not resp.ok:
                print(f'  Error: {resp.status_code} - {resp.text[:100]}')
                return None
            return resp.json() if resp.text else {}
        except requests.RequestException as e:
            print(f'  Request error: {e}')
            return None

    def get_brands(self):
        """Get all brands from Webflow."""
        brands = []
        offset = 0
        while True:
            result = self._request('GET',
                f'/collections/{BRANDS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not result:
                break
            items = result.get('items', [])
            if not items:
                break
            brands.extend(items)
            offset += 100
            if len(items) < 100:
                break
        return brands

    def update_brand(self, item_id, data):
        """Update brand with description data."""
        update_data = {'fieldData': data}
        result = self._request('PATCH',
            f'/collections/{BRANDS_COLLECTION_ID}/items/{item_id}',
            update_data)
        return result is not None

    def run(self):
        """Update all brands with descriptions."""
        print("Fetching brands from Webflow...")
        brands = self.get_brands()
        print(f"Found {len(brands)} brands\n")

        stats = {'updated': 0, 'skipped': 0, 'no_data': 0}

        for brand in brands:
            fd = brand.get('fieldData', {})
            item_id = brand.get('id')
            name = fd.get('name', '')

            # Check if already has description
            existing_desc = fd.get('description', '')
            if existing_desc and len(existing_desc.strip()) > 20:
                print(f"  {name}: Already has description, skipping")
                stats['skipped'] += 1
                continue

            # Get pre-compiled description
            brand_data = BRAND_DESCRIPTIONS.get(name)
            if not brand_data:
                print(f"  {name}: No description data available")
                stats['no_data'] += 1
                continue

            # Build update data
            update_fields = {}

            if brand_data.get('description'):
                update_fields['description'] = f"<p>{brand_data['description']}</p>"

            if brand_data.get('story'):
                update_fields['brand-story'] = f"<p>{brand_data['story']}</p>"

            if brand_data.get('founded'):
                update_fields['founded'] = brand_data['founded']

            # Add website if we have it
            url_data = BRAND_URLS.get(name)
            if url_data and url_data.get('website'):
                update_fields['website'] = url_data['website']

            if not update_fields:
                print(f"  {name}: No fields to update")
                stats['no_data'] += 1
                continue

            print(f"  {name}: Updating {len(update_fields)} fields...")
            if self.update_brand(item_id, update_fields):
                stats['updated'] += 1
                print(f"    ✓ Updated")
            else:
                print(f"    ✗ Failed")

        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Brands updated: {stats['updated']}")
        print(f"Already had data: {stats['skipped']}")
        print(f"No data available: {stats['no_data']}")


if __name__ == '__main__':
    scraper = BrandDescriptionScraper()
    scraper.run()
