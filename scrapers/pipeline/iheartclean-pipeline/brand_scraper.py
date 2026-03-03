#!/usr/bin/env python3
"""
Brand/Collection Scraper for iHeartClean Pipeline
Scrapes all products from a brand's collection page, then processes each.

Usage:
  # Scrape entire brand collection
  python brand_scraper.py "https://tower28beauty.com/collections/all" --push
  
  # Scrape with product limit
  python brand_scraper.py "https://kosas.com/collections/all" --limit 20
  
  # Just discover URLs (no processing)
  python brand_scraper.py "https://brand.com/collections/all" --discover-only
"""

import json
import re
import sys
import time
import argparse
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install requests beautifulsoup4 --break-system-packages")
    sys.exit(1)

# Try to import pipeline components
try:
    from pipeline import process_product, process_batch
    from webflow_client import WebflowClient, WebflowConfig
except ImportError:
    process_product = None
    process_batch = None

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# PRODUCT URL DISCOVERY
# =============================================================================

# Common product URL patterns by platform
PRODUCT_PATTERNS = {
    "shopify": [
        r'/products/[a-z0-9-]+',
        r'/collections/[^/]+/products/[a-z0-9-]+',
    ],
    "woocommerce": [
        r'/product/[a-z0-9-]+',
        r'/shop/[^/]+/[a-z0-9-]+',
    ],
    "magento": [
        r'/[a-z0-9-]+\.html',
    ],
    "generic": [
        r'/products?/[a-z0-9-]+',
        r'/item/[a-z0-9-]+',
        r'/p/[a-z0-9-]+',
        r'/pd/[a-z0-9-]+',
    ],
}

# URLs to skip
SKIP_PATTERNS = [
    r'/cart', r'/checkout', r'/account', r'/login', r'/register',
    r'/pages/', r'/blogs/', r'/policies/', r'/search',
    r'\.(jpg|jpeg|png|gif|svg|css|js|pdf)$',
    r'/collections/?$', r'/collections/all/?$',
]


def detect_platform(html: str, url: str) -> str:
    """Detect e-commerce platform from page HTML."""
    html_lower = html.lower()
    
    if 'shopify' in html_lower or 'cdn.shopify.com' in html_lower:
        return 'shopify'
    elif 'woocommerce' in html_lower or 'wp-content' in html_lower:
        return 'woocommerce'
    elif 'magento' in html_lower or 'mage' in html_lower:
        return 'magento'
    else:
        return 'generic'


def is_product_url(url: str, platform: str) -> bool:
    """Check if URL looks like a product page."""
    url_lower = url.lower()
    
    # Skip non-product URLs
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, url_lower):
            return False
    
    # Check platform-specific patterns
    patterns = PRODUCT_PATTERNS.get(platform, []) + PRODUCT_PATTERNS['generic']
    for pattern in patterns:
        if re.search(pattern, url_lower):
            return True
    
    return False


def extract_product_urls(html: str, base_url: str, platform: str) -> Set[str]:
    """Extract all product URLs from a page."""
    soup = BeautifulSoup(html, 'html.parser')
    domain = urlparse(base_url).netloc
    product_urls = set()
    
    # Find all links
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Make absolute URL
        if href.startswith('/'):
            full_url = urljoin(base_url, href)
        elif href.startswith('http'):
            full_url = href
        else:
            continue
        
        # Check if same domain
        if urlparse(full_url).netloc != domain:
            continue
        
        # Check if product URL
        if is_product_url(full_url, platform):
            # Normalize URL (remove query params, trailing slash)
            clean_url = full_url.split('?')[0].split('#')[0].rstrip('/')
            product_urls.add(clean_url)
    
    return product_urls


def get_pagination_urls(html: str, base_url: str) -> List[str]:
    """Find pagination links for multi-page collections."""
    soup = BeautifulSoup(html, 'html.parser')
    pagination_urls = []
    
    # Common pagination patterns
    pagination_selectors = [
        'a.pagination__item',
        'a.page-number',
        '.pagination a',
        'a[href*="page="]',
        'a[href*="/page/"]',
        '.next-page a',
        'a[rel="next"]',
    ]
    
    for selector in pagination_selectors:
        try:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href:
                    full_url = urljoin(base_url, href)
                    if full_url not in pagination_urls:
                        pagination_urls.append(full_url)
        except:
            continue
    
    return pagination_urls


def discover_products(collection_url: str, max_pages: int = 10, 
                      delay: float = 1.0) -> dict:
    """
    Discover all product URLs from a collection/brand page.
    Handles pagination automatically.
    
    Returns:
        {
            "brand": "Brand Name",
            "collection_url": "...",
            "platform": "shopify",
            "product_urls": ["...", "..."],
            "pages_scraped": 3,
        }
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    
    all_product_urls = set()
    pages_scraped = 0
    urls_to_scrape = [collection_url]
    scraped_pages = set()
    
    print(f"\n{'='*60}")
    print(f"DISCOVERING PRODUCTS: {collection_url}")
    print(f"{'='*60}")
    
    # Get first page to detect platform
    try:
        resp = requests.get(collection_url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": str(e), "collection_url": collection_url}
    
    platform = detect_platform(html, collection_url)
    print(f"Platform detected: {platform}")
    
    # Extract brand name
    soup = BeautifulSoup(html, 'html.parser')
    brand = ""
    og_site = soup.find("meta", {"property": "og:site_name"})
    if og_site:
        brand = og_site.get("content", "")
    elif soup.title:
        brand = soup.title.get_text().split('|')[0].split('-')[0].strip()
    
    print(f"Brand: {brand or 'Unknown'}")
    
    # Scrape pages
    while urls_to_scrape and pages_scraped < max_pages:
        current_url = urls_to_scrape.pop(0)
        
        if current_url in scraped_pages:
            continue
        
        scraped_pages.add(current_url)
        pages_scraped += 1
        
        print(f"\nPage {pages_scraped}: {current_url[:60]}...")
        
        try:
            if current_url != collection_url:
                time.sleep(delay)
                resp = requests.get(current_url, headers=headers, timeout=15)
                resp.raise_for_status()
                html = resp.text
            
            # Extract products
            products = extract_product_urls(html, current_url, platform)
            new_products = products - all_product_urls
            all_product_urls.update(products)
            print(f"   Found {len(new_products)} new products (total: {len(all_product_urls)})")
            
            # Find more pages
            if pages_scraped < max_pages:
                pagination = get_pagination_urls(html, current_url)
                for page_url in pagination:
                    if page_url not in scraped_pages and page_url not in urls_to_scrape:
                        urls_to_scrape.append(page_url)
                        
        except Exception as e:
            print(f"   Error: {e}")
            continue
    
    return {
        "brand": brand,
        "collection_url": collection_url,
        "platform": platform,
        "product_urls": sorted(list(all_product_urls)),
        "product_count": len(all_product_urls),
        "pages_scraped": pages_scraped,
    }


# =============================================================================
# SHOPIFY JSON API (Faster for Shopify stores)
# =============================================================================

def discover_shopify_products(base_url: str, max_products: int = 250) -> dict:
    """
    Use Shopify's JSON API for faster product discovery.
    Works on most Shopify stores. Returns full product data including images!
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    domain = urlparse(base_url).netloc
    
    print(f"\n{'='*60}")
    print(f"SHOPIFY API DISCOVERY: {base_url}")
    print(f"{'='*60}")
    
    all_products = []
    page = 1
    
    while len(all_products) < max_products:
        # Shopify products.json endpoint
        api_url = f"https://{domain}/products.json?limit=250&page={page}"
        
        try:
            resp = requests.get(api_url, headers=headers, timeout=15)
            
            if resp.status_code == 404:
                # Fallback to HTML scraping
                print("Shopify API not available, falling back to HTML scraping...")
                return discover_products(base_url)
            
            resp.raise_for_status()
            data = resp.json()
            
            products = data.get('products', [])
            if not products:
                break
            
            all_products.extend(products)
            print(f"Page {page}: Found {len(products)} products (total: {len(all_products)})")
            
            if len(products) < 250:
                break
            
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"API error: {e}")
            break
    
    # Build product URLs
    product_urls = [f"https://{domain}/products/{p['handle']}" for p in all_products]
    
    # Get brand name
    brand = all_products[0].get('vendor', '') if all_products else ''
    
    # Extract rich product data (images, descriptions, etc.)
    enriched_products = []
    for p in all_products[:max_products]:
        # Get all image URLs
        images = [img.get('src', '') for img in p.get('images', [])]
        
        # Get description and look for ingredients
        description = p.get('body_html', '') or ''
        ingredients = extract_ingredients_from_html(description)
        
        enriched_products.append({
            "handle": p.get('handle', ''),
            "title": p.get('title', ''),
            "vendor": p.get('vendor', ''),
            "product_type": p.get('product_type', ''),
            "url": f"https://{domain}/products/{p['handle']}",
            "images": images,
            "main_image": images[0] if images else '',
            "description": description,
            "ingredients": ingredients,
            "tags": p.get('tags', []),
            "variants": [{
                "price": v.get('price', ''),
                "sku": v.get('sku', ''),
                "title": v.get('title', ''),
            } for v in p.get('variants', [])[:5]],
        })
    
    return {
        "brand": brand,
        "collection_url": base_url,
        "platform": "shopify",
        "product_urls": product_urls[:max_products],
        "product_count": len(product_urls[:max_products]),
        "pages_scraped": page,
        "method": "shopify_api",
        "products_enriched": enriched_products,  # Full product data with images!
    }


def extract_ingredients_from_html(html_text: str) -> str:
    """Extract ingredients from HTML description."""
    if not html_text:
        return ""
    
    # Remove HTML tags for searching
    text = re.sub(r'<[^>]+>', ' ', html_text)
    
    # Look for ingredients section
    patterns = [
        r'(?:full\s+)?ingredients?\s*[:\-]\s*([^<]{50,2000})',
        r'(?:key\s+)?ingredients?\s*[:\-]\s*([^<]{30,1000})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""


# =============================================================================
# MAIN
# =============================================================================

def scrape_brand(collection_url: str, push: bool = False, use_ai: bool = False,
                 limit: Optional[int] = None, discover_only: bool = False,
                 output_file: Optional[str] = None) -> dict:
    """
    Main function: discover products and optionally process them.
    Uses Shopify API data when available to avoid redundant scraping.
    """
    # Detect if Shopify and try API first
    discovery = None
    try:
        discovery = discover_shopify_products(collection_url, max_products=limit or 250)
    except:
        pass
    
    if not discovery or 'error' in discovery:
        discovery = discover_products(collection_url)
    
    if 'error' in discovery:
        return discovery
    
    product_urls = discovery['product_urls']
    enriched_data = discovery.get('products_enriched', [])
    
    # Apply limit
    if limit and len(product_urls) > limit:
        print(f"\nLimiting to {limit} products (found {len(product_urls)})")
        product_urls = product_urls[:limit]
        enriched_data = enriched_data[:limit]
    
    print(f"\n{'='*60}")
    print(f"DISCOVERED {len(product_urls)} PRODUCTS")
    if enriched_data:
        print(f"(With images and data from Shopify API - faster processing!)")
    print(f"{'='*60}")
    
    # Just discovery?
    if discover_only:
        result = {
            "brand": discovery['brand'],
            "collection_url": collection_url,
            "product_count": len(product_urls),
            "product_urls": product_urls,
        }
        
        # Include enriched data if available
        if enriched_data:
            result["products_enriched"] = enriched_data
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nURLs saved to: {output_file}")
        
        return result
    
    # Process products
    if process_batch is None:
        print("\nError: pipeline.py not found. Run from scripts/ directory.")
        return {"error": "pipeline not found", "product_urls": product_urls}
    
    # Setup Webflow client if pushing
    webflow_client = None
    if push:
        try:
            config = WebflowConfig.from_env()
            if config.api_token:
                webflow_client = WebflowClient(config)
                print("Webflow client initialized")
            else:
                print("Warning: WEBFLOW_API_TOKEN not set, skipping push")
                push = False
        except Exception as e:
            print(f"Webflow setup error: {e}")
            push = False
    
    # If we have enriched Shopify data, use fast processing
    if enriched_data:
        results = process_batch_with_shopify_data(
            enriched_products=enriched_data,
            use_ai=use_ai,
            push_to_webflow=push,
            webflow_client=webflow_client,
        )
    else:
        # Fall back to URL-by-URL scraping
        results = process_batch(
            urls=product_urls,
            use_ai=use_ai,
            push_to_webflow=push,
            webflow_client=webflow_client,
        )
    
    # Add brand info
    results['brand'] = discovery['brand']
    results['collection_url'] = collection_url
    
    # Save results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    return results


def process_batch_with_shopify_data(enriched_products: list, use_ai: bool = False,
                                     push_to_webflow: bool = False,
                                     webflow_client = None) -> dict:
    """
    Process products using pre-fetched Shopify API data.
    Much faster - no need to scrape individual pages!
    """
    from classifier import classify_product
    from webflow_client import product_to_webflow_fields
    
    print(f"\n{'#'*60}")
    print(f"FAST PROCESSING: {len(enriched_products)} products (using Shopify data)")
    print(f"{'#'*60}")
    
    results = []
    failed = []
    
    for i, ep in enumerate(enriched_products, 1):
        print(f"\n[{i}/{len(enriched_products)}] {ep.get('title', 'Unknown')[:50]}...")
        
        try:
            # Build text for classification from Shopify data
            text_parts = [
                ep.get('title', ''),
                ep.get('vendor', ''),
                ep.get('product_type', ''),
                ep.get('description', ''),
                ' '.join(ep.get('tags', [])),
            ]
            text = ' '.join(text_parts)
            
            # Classify
            product = classify_product(
                text=text,
                product_name=ep.get('title', ''),
                brand=ep.get('vendor', ''),
            )
            
            # Add URL and images from Shopify data
            product['url'] = ep.get('url', '')
            product['main_image'] = ep.get('main_image', '')
            product['images'] = ep.get('images', [])
            product['ingredients_full'] = ep.get('ingredients', '')
            
            # Parse ingredients
            if product['ingredients_full']:
                product['ingredients_list'] = [
                    ing.strip() for ing in product['ingredients_full'].split(',')
                    if ing.strip()
                ]
            else:
                product['ingredients_list'] = []
            
            # Get price from variants
            variants = ep.get('variants', [])
            if variants and variants[0].get('price'):
                try:
                    product['price'] = float(variants[0]['price'])
                except:
                    pass
            
            print(f"   ✓ Classified: {product['attribute_count']} attributes, score {product['overall_score']}")
            print(f"   Images: {len(product['images'])}, Ingredients: {'Yes' if product['ingredients_full'] else 'No'}")
            
            # Push to Webflow
            if push_to_webflow and webflow_client:
                try:
                    field_data = product_to_webflow_fields(product)
                    result = webflow_client.upsert_item(field_data)
                    product['webflow_id'] = result.get('id')
                    product['webflow_status'] = 'pushed'
                    print(f"   ✓ Pushed to Webflow")
                except Exception as e:
                    product['webflow_status'] = f'error: {e}'
                    print(f"   ✗ Webflow error: {e}")
            
            results.append(product)
            
        except Exception as e:
            failed.append({"title": ep.get('title'), "error": str(e)})
            print(f"   ✗ Error: {e}")
        
        # Small delay for rate limiting
        if push_to_webflow:
            time.sleep(0.5)
    
    return {
        "products": results,
        "failed": failed,
        "summary": {
            "total": len(enriched_products),
            "success": len(results),
            "failed": len(failed),
            "total_cost": "$0.00",
            "method": "shopify_api_fast",
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scrape all products from a brand/collection page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover all products
  python brand_scraper.py "https://tower28beauty.com/collections/all" --discover-only
  
  # Scrape and classify all products
  python brand_scraper.py "https://kosas.com/collections/all" --output kosas.json
  
  # Scrape, classify, and push to Webflow
  python brand_scraper.py "https://tower28beauty.com/collections/all" --push
  
  # Limit to 20 products
  python brand_scraper.py "https://brand.com/collections/all" --limit 20 --push
  
  # With AI enhancement
  python brand_scraper.py "https://brand.com/collections/all" --ai --push
        """
    )
    
    parser.add_argument("url", help="Brand collection URL (e.g., /collections/all)")
    parser.add_argument("--push", action="store_true", help="Push to Webflow CMS")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement")
    parser.add_argument("--limit", type=int, help="Max products to process")
    parser.add_argument("--discover-only", action="store_true", help="Only discover URLs, don't process")
    parser.add_argument("--output", "-o", help="Output JSON file")
    
    args = parser.parse_args()
    
    results = scrape_brand(
        collection_url=args.url,
        push=args.push,
        use_ai=args.ai,
        limit=args.limit,
        discover_only=args.discover_only,
        output_file=args.output,
    )
    
    if not args.output and not args.discover_only:
        print("\n" + json.dumps(results.get('summary', results), indent=2))


if __name__ == "__main__":
    main()
