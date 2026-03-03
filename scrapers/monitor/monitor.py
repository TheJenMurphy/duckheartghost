#!/usr/bin/env python3
"""
🐇 iHeartClean.beauty - Weekly Monitoring System
"I am emergent from the rabbit hole."

This system automates the finding so you just triage on Monday mornings.
Run with: python monitor.py --all
"""

import json
import hashlib
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import time
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import html

# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"

# RSS Feeds to monitor
RSS_FEEDS = {
    # Regulatory & Science
    "cosmetics_business": "https://cosmeticsbusiness.com/feed",
    "gci_magazine": "https://www.gcimagazine.com/rss",
    "happi": "https://www.happi.com/rss",
    "beauty_independent": "https://www.beautyindependent.com/feed/",
    "beautymatter": "https://beautymatter.com/feed",
    
    # Beauty blogs with product launches
    "temptalia": "https://www.temptalia.com/feed/",
    "musings_of_muse": "https://www.musingsofamuse.com/feed",
}

# Keywords for content pillar classification
KEYWORDS = {
    "banned": ["banned", "prohibited", "annex ii", "restricted", "recalled", "unsafe", "carcinogen", "cmr", "endocrine disruptor"],
    "new_regulation": ["regulation", "sccs", "omnibus", "eu cosmetics", "directive", "annex iii", "compliance", "deadline"],
    "new_product": ["launch", "launches", "new product", "debut", "introduces", "releases", "drops", "collection"],
    "clean_beauty": ["clean beauty", "non-toxic", "natural", "organic", "sustainable", "vegan", "cruelty-free", "ewg"],
    "trending": ["viral", "tiktok", "trending", "bestseller", "sold out", "hype", "influencer"],
}

# User agent for requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: str
    summary: str
    pillars: List[str]  # Which content pillars this maps to
    
@dataclass  
class RegulationUpdate:
    title: str
    reference: str
    date: str
    substances: List[str]
    action: str  # banned, restricted, updated
    deadline: Optional[str]
    link: str

@dataclass
class DigestReport:
    generated_at: str
    period_start: str
    period_end: str
    hot_items: List[NewsItem]
    not_items: List[NewsItem]
    viral_items: List[NewsItem]
    regulation_updates: List[RegulationUpdate]
    all_items: List[NewsItem]

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def ensure_dirs():
    """Create necessary directories."""
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "cache").mkdir(exist_ok=True)
    (DATA_DIR / "history").mkdir(exist_ok=True)

def get_hash(content: str) -> str:
    """Generate hash for content deduplication."""
    return hashlib.md5(content.encode()).hexdigest()[:12]

def classify_content(title: str, summary: str) -> List[str]:
    """Classify content into pillars based on keywords."""
    text = f"{title} {summary}".lower()
    pillars = []
    
    for pillar, keywords in KEYWORDS.items():
        if any(kw in text for kw in keywords):
            pillars.append(pillar)
    
    return pillars if pillars else ["general"]

def clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500] + "..." if len(text) > 500 else text

def load_seen_items() -> set:
    """Load previously seen item hashes."""
    seen_file = DATA_DIR / "seen_items.json"
    if seen_file.exists():
        with open(seen_file) as f:
            return set(json.load(f))
    return set()

def save_seen_items(seen: set):
    """Save seen item hashes."""
    seen_file = DATA_DIR / "seen_items.json"
    # Keep only last 10000 items to prevent file bloat
    seen_list = list(seen)[-10000:]
    with open(seen_file, "w") as f:
        json.dump(seen_list, f)

# ============================================================
# RSS FEED MONITOR
# ============================================================

class RSSMonitor:
    """Monitor RSS feeds for news items."""
    
    def __init__(self, feeds: Dict[str, str]):
        self.feeds = feeds
        self.seen = load_seen_items()
        
    def fetch_feed(self, name: str, url: str) -> List[NewsItem]:
        """Fetch and parse a single RSS feed."""
        items = []
        try:
            print(f"  📡 Fetching {name}...")
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:20]:  # Last 20 items
                title = entry.get("title", "")
                link = entry.get("link", "")
                
                # Generate hash for deduplication
                item_hash = get_hash(f"{title}{link}")
                if item_hash in self.seen:
                    continue
                    
                self.seen.add(item_hash)
                
                # Parse published date
                published = ""
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6]).isoformat()
                    except:
                        published = entry.get("published", "")
                
                # Get summary
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                
                # Classify into pillars
                pillars = classify_content(title, summary)
                
                items.append(NewsItem(
                    title=title,
                    link=link,
                    source=name,
                    published=published,
                    summary=summary,
                    pillars=pillars
                ))
                
        except Exception as e:
            print(f"  ⚠️  Error fetching {name}: {e}")
            
        return items
    
    def fetch_all(self) -> List[NewsItem]:
        """Fetch all RSS feeds."""
        all_items = []
        print("\n🔍 Scanning RSS feeds...")
        
        for name, url in self.feeds.items():
            items = self.fetch_feed(name, url)
            all_items.extend(items)
            time.sleep(1)  # Be nice to servers
            
        save_seen_items(self.seen)
        print(f"  ✅ Found {len(all_items)} new items")
        return all_items

# ============================================================
# EU REGULATION MONITOR
# ============================================================

class EURegulationMonitor:
    """Monitor EU cosmetics regulations and SCCS opinions."""
    
    SCCS_URL = "https://health.ec.europa.eu/scientific-committees/scientific-committee-consumer-safety-sccs/sccs-opinions_en"
    EURLEX_SEARCH = "https://eur-lex.europa.eu/search.html?SUBDOM_INIT=LEGISLATION&DTS_SUBDOM=LEGISLATION&textScope=ti-te&qid=&DTS_DOM=EU_LAW&type=advanced&lang=en&SEARCH_TYPE=textAdvanced&sortOne=DD&sortOneOrder=desc"
    
    def __init__(self):
        self.cache_dir = DATA_DIR / "cache"
        
    def fetch_sccs_opinions(self) -> List[RegulationUpdate]:
        """Fetch recent SCCS opinions."""
        updates = []
        print("\n🔬 Checking SCCS opinions...")
        
        try:
            response = requests.get(self.SCCS_URL, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find opinion sections
            for section in soup.find_all(["h3", "h4", "p", "li"]):
                text = section.get_text()
                
                # Look for SCCS opinion references
                if "SCCS/" in text or "Scientific Opinion" in text.lower():
                    # Extract substance names (often in the title)
                    substances = []
                    # Common patterns: "on X", "of X", substance names often in parentheses
                    matches = re.findall(r'on\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)', text)
                    substances.extend(matches)
                    
                    link_tag = section.find("a")
                    link = link_tag["href"] if link_tag and link_tag.get("href") else self.SCCS_URL
                    if link.startswith("/"):
                        link = "https://health.ec.europa.eu" + link
                    
                    updates.append(RegulationUpdate(
                        title=text[:200],
                        reference=re.search(r'SCCS/\d+/\d+', text).group() if re.search(r'SCCS/\d+/\d+', text) else "",
                        date=datetime.now().isoformat(),
                        substances=substances[:5],
                        action="opinion",
                        deadline=None,
                        link=link
                    ))
                    
            print(f"  ✅ Found {len(updates)} SCCS items")
            
        except Exception as e:
            print(f"  ⚠️  Error fetching SCCS: {e}")
            
        return updates[:10]  # Limit to most recent
    
    def fetch_cosmetics_news(self) -> List[NewsItem]:
        """Fetch cosmetics-specific regulatory news from ChemLinked and CosLaw."""
        items = []
        
        sources = [
            ("ChemLinked", "https://cosmetic.chemlinked.com/news"),
            ("CosLaw", "https://coslaw.eu"),
        ]
        
        print("\n📋 Checking regulatory news sites...")
        
        for name, url in sources:
            try:
                print(f"  📡 Fetching {name}...")
                response = requests.get(url, headers=HEADERS, timeout=30)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Generic article finder
                for article in soup.find_all(["article", "div"], class_=re.compile(r"(post|article|news|item)", re.I))[:10]:
                    title_tag = article.find(["h1", "h2", "h3", "h4", "a"])
                    if not title_tag:
                        continue
                        
                    title = title_tag.get_text().strip()
                    if len(title) < 10:
                        continue
                        
                    link = ""
                    if title_tag.name == "a":
                        link = title_tag.get("href", "")
                    else:
                        link_tag = article.find("a")
                        if link_tag:
                            link = link_tag.get("href", "")
                    
                    if link and not link.startswith("http"):
                        link = url.rstrip("/") + "/" + link.lstrip("/")
                    
                    items.append(NewsItem(
                        title=title,
                        link=link or url,
                        source=name,
                        published=datetime.now().isoformat(),
                        summary="",
                        pillars=classify_content(title, "")
                    ))
                    
                time.sleep(1)
                
            except Exception as e:
                print(f"  ⚠️  Error fetching {name}: {e}")
                
        print(f"  ✅ Found {len(items)} regulatory news items")
        return items

# ============================================================
# RETAILER MONITOR
# ============================================================

class RetailerMonitor:
    """Monitor retailer new arrivals pages."""
    
    RETAILERS = {
        "Sephora New": "https://www.sephora.com/shop/new-skin-care-products",
        "Ulta New": "https://www.ulta.com/shop/new-beauty-products",
        "Credo Beauty": "https://credobeauty.com/collections/new",
    }
    
    def fetch_new_products(self) -> List[NewsItem]:
        """Fetch new product listings from retailers."""
        items = []
        print("\n🛍️  Checking retailer new arrivals...")
        
        for name, url in self.RETAILERS.items():
            try:
                print(f"  📡 Checking {name}...")
                response = requests.get(url, headers=HEADERS, timeout=30)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for product cards/tiles
                products = soup.find_all(["div", "article"], class_=re.compile(r"(product|item|card)", re.I))[:15]
                
                for product in products:
                    title_tag = product.find(["h2", "h3", "h4", "a", "span"], class_=re.compile(r"(name|title|product)", re.I))
                    if not title_tag:
                        continue
                        
                    title = title_tag.get_text().strip()
                    if len(title) < 5:
                        continue
                    
                    items.append(NewsItem(
                        title=f"[{name}] {title}",
                        link=url,
                        source=name,
                        published=datetime.now().isoformat(),
                        summary="New product arrival",
                        pillars=["new_product"]
                    ))
                    
                time.sleep(2)  # Be respectful of retailer sites
                
            except Exception as e:
                print(f"  ⚠️  Error fetching {name}: {e}")
                
        print(f"  ✅ Found {len(items)} new products")
        return items

# ============================================================
# DIGEST GENERATOR
# ============================================================

class DigestGenerator:
    """Generate weekly digest report."""
    
    def __init__(self):
        self.output_dir = OUTPUT_DIR
        
    def generate(self, 
                 news_items: List[NewsItem],
                 regulation_updates: List[RegulationUpdate]) -> DigestReport:
        """Generate digest report."""
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        # Categorize items
        hot_items = [i for i in news_items if "new_product" in i.pillars or "clean_beauty" in i.pillars]
        not_items = [i for i in news_items if "banned" in i.pillars or "new_regulation" in i.pillars]
        viral_items = [i for i in news_items if "trending" in i.pillars]
        
        report = DigestReport(
            generated_at=now.isoformat(),
            period_start=week_ago.isoformat(),
            period_end=now.isoformat(),
            hot_items=hot_items[:20],
            not_items=not_items[:20],
            viral_items=viral_items[:20],
            regulation_updates=regulation_updates[:10],
            all_items=news_items
        )
        
        return report
    
    def save_json(self, report: DigestReport, filename: str = None):
        """Save report as JSON."""
        if not filename:
            filename = f"digest_{datetime.now().strftime('%Y%m%d')}.json"
        
        filepath = self.output_dir / filename
        
        # Convert to dict
        report_dict = {
            "generated_at": report.generated_at,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "summary": {
                "hot_count": len(report.hot_items),
                "not_count": len(report.not_items),
                "viral_count": len(report.viral_items),
                "regulation_count": len(report.regulation_updates),
                "total_items": len(report.all_items)
            },
            "hot_items": [asdict(i) for i in report.hot_items],
            "not_items": [asdict(i) for i in report.not_items],
            "viral_items": [asdict(i) for i in report.viral_items],
            "regulation_updates": [asdict(r) for r in report.regulation_updates],
        }
        
        with open(filepath, "w") as f:
            json.dump(report_dict, f, indent=2)
            
        print(f"\n💾 Saved JSON digest to: {filepath}")
        return filepath
    
    def save_markdown(self, report: DigestReport, filename: str = None):
        """Save report as Markdown for easy reading."""
        if not filename:
            filename = f"digest_{datetime.now().strftime('%Y%m%d')}.md"
        
        filepath = self.output_dir / filename
        
        md = []
        md.append("# 🐇 iHeartClean Weekly Digest")
        md.append(f"\n**Generated:** {report.generated_at[:10]}")
        md.append(f"\n*\"I am emergent from the rabbit hole.\"*\n")
        md.append("---\n")
        
        # Summary
        md.append("## 📊 This Week's Haul\n")
        md.append(f"- 🔥 **Hot:** {len(report.hot_items)} items")
        md.append(f"- 🚫 **Not:** {len(report.not_items)} items")
        md.append(f"- 📱 **Viral:** {len(report.viral_items)} items")
        md.append(f"- 📋 **Regulations:** {len(report.regulation_updates)} updates")
        md.append(f"- **Total scanned:** {len(report.all_items)} items\n")
        
        # 🔥 HOT Section
        if report.hot_items:
            md.append("---\n## 🔥 HOT - New & Noteworthy\n")
            for item in report.hot_items[:10]:
                md.append(f"### [{item.title}]({item.link})")
                md.append(f"*{item.source}* | {item.published[:10] if item.published else 'Recent'}\n")
                if item.summary:
                    md.append(f"> {item.summary[:200]}...\n")
                md.append("")
        
        # 🚫 NOT Section
        if report.not_items:
            md.append("---\n## 🚫 NOT - Banned, Restricted, Flagged\n")
            for item in report.not_items[:10]:
                md.append(f"### [{item.title}]({item.link})")
                md.append(f"*{item.source}* | {item.published[:10] if item.published else 'Recent'}\n")
                if item.summary:
                    md.append(f"> {item.summary[:200]}...\n")
                md.append("")
        
        # 📋 Regulation Updates
        if report.regulation_updates:
            md.append("---\n## 📋 Regulation Watch\n")
            for reg in report.regulation_updates[:5]:
                md.append(f"### {reg.title[:100]}")
                if reg.reference:
                    md.append(f"**Reference:** {reg.reference}")
                if reg.substances:
                    md.append(f"**Substances:** {', '.join(reg.substances)}")
                md.append(f"[Read more]({reg.link})\n")
        
        # 📱 Viral Section
        if report.viral_items:
            md.append("---\n## 📱 VIRAL - Trending (30 min timer reminder! ⏱️)\n")
            for item in report.viral_items[:5]:
                md.append(f"- [{item.title}]({item.link}) - *{item.source}*")
            md.append("")
        
        # Footer
        md.append("---\n")
        md.append("*Scrapers did the rabbit hole finding. Now you triage.*\n")
        md.append("🐇")
        
        with open(filepath, "w") as f:
            f.write("\n".join(md))
            
        print(f"📝 Saved Markdown digest to: {filepath}")
        return filepath

# ============================================================
# MAIN ORCHESTRATOR
# ============================================================

def run_full_scan():
    """Run complete monitoring scan."""
    ensure_dirs()
    
    print("\n" + "="*60)
    print("🐇 iHeartClean Weekly Monitor")
    print("   \"I am emergent from the rabbit hole.\"")
    print("="*60)
    
    all_news = []
    all_regulations = []
    
    # 1. RSS Feeds
    rss_monitor = RSSMonitor(RSS_FEEDS)
    all_news.extend(rss_monitor.fetch_all())
    
    # 2. EU Regulations
    eu_monitor = EURegulationMonitor()
    all_regulations.extend(eu_monitor.fetch_sccs_opinions())
    reg_news = eu_monitor.fetch_cosmetics_news()
    all_news.extend(reg_news)
    
    # 3. Retailer New Products (optional - can be slow)
    # retailer_monitor = RetailerMonitor()
    # all_news.extend(retailer_monitor.fetch_new_products())
    
    # 4. Generate Digest
    generator = DigestGenerator()
    report = generator.generate(all_news, all_regulations)
    
    # 5. Save outputs
    json_path = generator.save_json(report)
    md_path = generator.save_markdown(report)
    
    print("\n" + "="*60)
    print("✅ SCAN COMPLETE")
    print("="*60)
    print(f"\n📊 Results Summary:")
    print(f"   🔥 Hot items: {len(report.hot_items)}")
    print(f"   🚫 Not items: {len(report.not_items)}")
    print(f"   📱 Viral items: {len(report.viral_items)}")
    print(f"   📋 Regulations: {len(report.regulation_updates)}")
    print(f"   📰 Total scanned: {len(report.all_items)}")
    print(f"\n📁 Output files:")
    print(f"   {json_path}")
    print(f"   {md_path}")
    print("\n🐇 The robots found things. Now go triage!\n")
    
    return report

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="🐇 iHeartClean Weekly Monitor - Automated content finding"
    )
    parser.add_argument("--all", action="store_true", help="Run full scan")
    parser.add_argument("--rss", action="store_true", help="Scan RSS feeds only")
    parser.add_argument("--regulations", action="store_true", help="Scan regulations only")
    parser.add_argument("--retailers", action="store_true", help="Scan retailer sites only")
    
    args = parser.parse_args()
    
    ensure_dirs()
    
    if args.all or not any([args.rss, args.regulations, args.retailers]):
        run_full_scan()
    else:
        all_news = []
        all_regulations = []
        
        if args.rss:
            rss_monitor = RSSMonitor(RSS_FEEDS)
            all_news.extend(rss_monitor.fetch_all())
            
        if args.regulations:
            eu_monitor = EURegulationMonitor()
            all_regulations.extend(eu_monitor.fetch_sccs_opinions())
            all_news.extend(eu_monitor.fetch_cosmetics_news())
            
        if args.retailers:
            retailer_monitor = RetailerMonitor()
            all_news.extend(retailer_monitor.fetch_new_products())
        
        if all_news or all_regulations:
            generator = DigestGenerator()
            report = generator.generate(all_news, all_regulations)
            generator.save_json(report)
            generator.save_markdown(report)

if __name__ == "__main__":
    main()
