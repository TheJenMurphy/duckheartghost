# 🐇 iHeartClean Weekly Monitor

*"I am emergent from the rabbit hole."*

Automated monitoring system for iHeartClean.beauty that scans ingredient databases, regulatory news, trade publications, and retailer sites to power your weekly content pillars.

## 🎯 What It Does

The robots do the finding so your ADHD brain just triages on Monday mornings.

| Pillar | Sources Monitored |
|--------|------------------|
| 🔥 **Hot** | Trade pubs, retailer new arrivals, brand launches |
| 🚫 **Not** | EU regulations, SCCS opinions, banned ingredient news |
| 📱 **Viral** | Beauty blogs, trending product mentions |
| 🐇 **Rabbit Hole** | You decide from the flagged items |

## 📦 Installation

```bash
# Navigate to the monitor directory
cd iheartclean_monitor

# Install dependencies
pip install -r requirements.txt

# Or with pip3
pip3 install -r requirements.txt --break-system-packages
```

## 🚀 Usage

### Full Weekly Scan (Recommended)
```bash
python monitor.py --all
```

### Scan Specific Sources
```bash
# RSS feeds only (trade pubs, beauty blogs)
python monitor.py --rss

# Regulations only (SCCS, EU updates)
python monitor.py --regulations

# Retailer new arrivals only
python monitor.py --retailers
```

## 📁 Output Files

After running, you'll find in the `output/` folder:

- `digest_YYYYMMDD.json` - Machine-readable data
- `digest_YYYYMMDD.md` - Human-readable Markdown for quick review

## ⏰ Recommended Schedule

Set up a cron job to run Sunday night so results are ready Monday morning:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 11pm Sunday)
0 23 * * 0 cd /path/to/iheartclean_monitor && python monitor.py --all
```

Or use macOS launchd, Windows Task Scheduler, or any automation tool.

## 📰 RSS Feeds Monitored

### Trade Publications
- Cosmetics Business
- Global Cosmetic Industry (GCI)
- HAPPI
- Beauty Independent
- BeautyMatter

### Beauty Blogs
- Temptalia
- Musings of a Muse

### Regulatory Sources
- EU SCCS Opinions page
- ChemLinked Cosmetics
- CosLaw EU

## 🔧 Customization

### Add More RSS Feeds

Edit `monitor.py` and add to the `RSS_FEEDS` dictionary:

```python
RSS_FEEDS = {
    # ... existing feeds ...
    "your_new_feed": "https://example.com/rss",
}
```

### Adjust Keywords

Edit the `KEYWORDS` dictionary to change how content is classified:

```python
KEYWORDS = {
    "banned": ["banned", "prohibited", ...],
    "new_product": ["launch", "debut", ...],
    # Add your own categories
}
```

## 🐇 Monday Morning Workflow

1. **Open the Markdown digest** - `output/digest_YYYYMMDD.md`
2. **Skim the summary** - See counts for each pillar
3. **Flag items** for each content pillar:
   - 🔥 Hot → Wednesday write-up
   - 🚫 Not → Wednesday write-up
   - 📱 Viral → 30 MIN TIMER then Wednesday
   - 🐇 Rabbit Hole → Schedule deep dive for Friday
4. **Done in 20-30 minutes** - Scrapers did the finding!

## ⚠️ Notes

- **Rate limiting**: The scraper waits between requests to be respectful of servers
- **Deduplication**: Items are tracked by hash, so you won't see the same item twice
- **History**: Seen items stored in `data/seen_items.json`

## 🛠️ Troubleshooting

### "No module named feedparser"
```bash
pip install feedparser --break-system-packages
```

### Permission errors on Mac
```bash
chmod +x monitor.py
```

### RSS feed not working
Some sites block automated requests. The scraper will show a warning and continue with other sources.

---

*The robots do the finding. Alice does the knowing.*

🐇
