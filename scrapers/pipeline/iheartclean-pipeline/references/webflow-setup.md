# Webflow CMS Setup Guide

## 1. Get API Credentials

### API Token
1. Go to Webflow Dashboard → Site Settings → Apps & Integrations
2. Scroll to "API Access" section
3. Generate a new API token with CMS permissions
4. Copy and save securely

### Site ID
1. Go to Site Settings → General
2. Find "Site ID" in the URL or site info
3. Or use API: `GET /sites` returns list with IDs

### Collection ID
1. Open your Products collection in CMS
2. Collection ID is in the URL: `/collections/{COLLECTION_ID}/items`
3. Or use API: `GET /sites/{site_id}/collections`

## 2. Create Products Collection

Create a CMS collection with these fields:

### Required Fields
| Field Name | Type | Notes |
|------------|------|-------|
| name | Plain Text | Product name (max 100 chars) |
| slug | Plain Text | URL-friendly identifier |

### Product Info
| Field Name | Type | Notes |
|------------|------|-------|
| brand | Reference | Link to Brands collection (optional) |
| product-url | Link | Original product page |
| price | Number | Decimal |
| size | Plain Text | e.g., "1 oz" |
| rating | Number | 1-5 scale |
| shade-count | Number | For makeup |

### 9S Scores (Numbers, 1-5)
| Field Name | Type |
|------------|------|
| overall-score | Number |
| stars-score | Number |
| source-score | Number |
| safety-score | Number |
| support-score | Number |
| suitability-score | Number |
| structure-score | Number |
| substance-score | Number |
| sustainability-score | Number |
| spend-score | Number |

### Persona Relevance (Numbers, 0-100)
| Field Name | Type |
|------------|------|
| antiaging-relevance | Number |
| family-relevance | Number |
| cancer-relevance | Number |
| bipoc-relevance | Number |
| fluid-relevance | Number |
| genz-relevance | Number |
| best-for | Plain Text |

### Filter Switches
| Field Name | Type |
|------------|------|
| is-clean | Switch |
| is-vegan | Switch |
| is-cruelty-free | Switch |
| is-fragrance-free | Switch |
| is-pregnancy-safe | Switch |
| has-spf | Switch |

### Additional
| Field Name | Type |
|------------|------|
| attributes | Plain Text | Comma-separated detected attributes |
| ai-summary | Plain Text | Optional AI-generated summary |

## 3. Environment Setup

Create a `.env` file in your project root:

```bash
# Webflow API
WEBFLOW_API_TOKEN=your_api_token_here
WEBFLOW_SITE_ID=your_site_id_here
WEBFLOW_COLLECTION_ID=your_collection_id_here

# Optional: AI Enhancement
ANTHROPIC_API_KEY=your_claude_api_key_here
```

## 4. Test Connection

```bash
cd scripts
python webflow_client.py collections
```

Should output your collection list.

## 5. Field Name Mapping

If your Webflow field names differ from defaults, edit `webflow_client.py`:

```python
def product_to_webflow_fields(product: Dict) -> Dict:
    return {
        "name": product.get("name"),
        "your-custom-field-name": product.get("price"),
        # ... adjust as needed
    }
```

## 6. Common Issues

### Rate Limiting
- Webflow allows ~60 requests/minute
- Pipeline includes automatic rate limiting
- For large batches, add `time.sleep(1)` between items

### Field Type Mismatches
- Numbers must be actual numbers, not strings
- Booleans must be `True`/`False`, not `"true"`/`"false"`
- Check field types in Webflow match your data

### Slug Conflicts
- Each item needs unique slug
- Pipeline auto-generates from product name
- Duplicates will fail to create

## 7. Publishing

Items are created as drafts by default. To publish:

```python
# Publish specific items
client.publish_items(["item_id_1", "item_id_2"])

# Or publish entire site
client.publish_site()
```

## 8. Webflow Plan Limits

| Plan | CMS Items | API Requests |
|------|-----------|--------------|
| Basic | 1,000 | 60/min |
| CMS | 10,000 | 60/min |
| Business | 10,000 | 60/min |

For large catalogs, consider batch processing during off-peak hours.
