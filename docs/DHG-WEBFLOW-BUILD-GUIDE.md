# DHG Card - Webflow Designer Build Guide

Step-by-step instructions for building the DHG Card natively in Webflow Designer.

---

## SETUP: Add Custom Code First

Before building, add the CSS and JS to your site:

1. **Site Settings → Custom Code → Head Code**
   - Paste contents of `dhg-webflow-head.html`

2. **Site Settings → Custom Code → Footer Code**
   - Paste contents of `dhg-webflow-footer.html`

3. **Publish** to activate the code

---

## YOUR CURRENT STRUCTURE

You have:
```
product-card
└── card-inner
    ├── card-front
    │   ├── approval-badge
    │   ├── product-image-container
    │   │   ├── gallery-container/gallery-slides
    │   │   └── gradient bar
    │   └── card-header
    └── card-back
        └── back-to-categories
```

---

## STEP 1: Add Class to Product Card

**Select:** `product-card`

**Add class:** `dhg-card`

This enables the flip functionality.

---

## STEP 2: Build CARD-FRONT

### 2.1 Add Top Bar (at the TOP of card-front)

1. **Select** `card-front`
2. **Add Div Block** at the very top (drag above approval-badge)
3. **Class:** `dhg-top-bar`

Inside `dhg-top-bar`, add:

| Element | Type | Class | Content |
|---------|------|-------|---------|
| Category | Div Block | `dhg-category` | (contains icon + text) |
| → Icon | Text Block | `dhg-category-icon` | 🎨 (or connect to CMS) |
| → Text | Text Block | `dhg-category-text` | Connect to CMS: Category |
| Actions | Div Block | `dhg-top-actions` | (contains buttons) |
| → Search | Link Block | `dhg-icon-btn dhg-search-btn` | 🔍 |
| → Heart | Link Block | `dhg-icon-btn dhg-heart-btn` | ❤️ |

---

### 2.2 Keep Your Image Area (modify slightly)

Your `product-image-container` is good. Add inside it:

1. **Add Div Block** at bottom of image container
2. **Class:** `dhg-monitor-badge`
3. **Custom Attribute:** `data-badge` = Connect to CMS: Monitor Status

Inside `dhg-monitor-badge`:

| Element | Type | Class | Content |
|---------|------|-------|---------|
| Icon | Text Block | `dhg-badge-icon` | 🔥 |
| Text | Text Block | `dhg-badge-text` | Connect to CMS: Monitor Status |

**Conditional Visibility:** Set the badge to only show when Monitor Status is set.

---

### 2.3 Add Product Info Section

1. **Add Div Block** below image container
2. **Class:** `dhg-product-info`

Inside `dhg-product-info`:

| Element | Type | Class | CMS Connection |
|---------|------|-------|----------------|
| Name | Heading (H2) | `dhg-product-name` | Product Name |
| Brand | Link Block | `dhg-brand-link` | Brand Name + " →" → links to /brands/{{Brand Slug}} |

---

### 2.4 Add Front Panels (HYPE + DEAL)

1. **Add Div Block** below product info
2. **Class:** `dhg-front-panels`

#### HYPE Panel

Inside `dhg-front-panels`, add:

1. **Div Block** with class: `dhg-panel dhg-panel-hype`

Inside the HYPE panel:

```
dhg-panel dhg-panel-hype
├── dhg-panel-header (Div Block)
│   ├── dhg-panel-title (Text Block) → "HYPE"
│   └── dhg-panel-chevron (Text Block) → "▸"
└── dhg-panel-content (Div Block)
    ├── dhg-stat dhg-stat-love (Text Block) → "❤️ {{Community Love}}%"
    ├── dhg-stat dhg-stat-influencer (Text Block) → "👥 {{Influencer Pct}}%"
    └── dhg-stat dhg-stat-rating (Text Block) → "{{Star Rating}}★"
```

#### DEAL Panel

Add another panel inside `dhg-front-panels`:

1. **Div Block** with class: `dhg-panel dhg-panel-deal`

Inside the DEAL panel:

```
dhg-panel dhg-panel-deal
├── dhg-panel-header (Div Block)
│   ├── dhg-panel-title (Text Block) → "DEAL"
│   └── dhg-panel-chevron (Text Block) → "▸"
└── dhg-panel-content (Div Block)
    ├── dhg-price (Text Block) → "{{Price}}"
    └── dhg-tag dhg-tag-dupe (Text Block) → "Dupe" (conditional)
```

---

### 2.5 Add Flip Button

1. **Add Button** at bottom of `card-front`
2. **Class:** `dhg-flip-btn`
3. **Text:** FLIP

---

## STEP 3: Build CARD-BACK

### 3.1 Add Top Bar (same as front)

1. **Select** `card-back`
2. **Add Div Block** at top
3. **Class:** `dhg-top-bar`
4. **Copy** the same structure as front (category + actions)

---

### 3.2 Add Facts Header

1. **Add Div Block** below top bar
2. **Class:** `dhg-facts-header`

Inside `dhg-facts-header`:

| Element | Type | Class | Content |
|---------|------|-------|---------|
| Title | Heading (H3) | `dhg-facts-title` | "Product Facts" (static text) |
| Product | Text Block | `dhg-facts-product` | Connect to CMS: Product Name |
| Brand | Link Block | `dhg-brand-link` | Brand Name + " →" |

---

### 3.3 Add Facts Panels Container

1. **Add Div Block** below facts header
2. **Class:** `dhg-facts-panels`

---

### 3.4 Add Each Facts Panel

Create 5 panels inside `dhg-facts-panels`. Each follows this pattern:

#### BENEFITS Panel

```
dhg-facts-panel dhg-panel-benefits (Div Block)
├── dhg-facts-panel-header (Div Block)
│   ├── dhg-facts-panel-title (Text Block) → "BENEFITS"
│   └── dhg-panel-chevron (Text Block) → "▸"
└── dhg-facts-panel-content (Div Block)
    └── dhg-tags (Div Block)
        └── [Collection List or individual tags]
```

**For the tags inside:**
- If using Multi-Reference field: Add a nested Collection List
- If using text field: Add individual Text Blocks with class `dhg-tag`

#### All 5 Panels:

| Panel Class | Title | Color | CMS Field |
|-------------|-------|-------|-----------|
| `dhg-facts-panel dhg-panel-benefits` | BENEFITS | Magenta | Benefits multi-ref |
| `dhg-facts-panel dhg-panel-skin` | SKIN TYPE | Cyan | Skin Types multi-ref |
| `dhg-facts-panel dhg-panel-ethics` | ETHICS | Purple | Ethics multi-ref |
| `dhg-facts-panel dhg-panel-ingredients` | INGREDIENTS | Teal | Key Ingredients multi-ref |
| `dhg-facts-panel dhg-panel-safety` | SAFETY & CERTS | Gold | (special layout) |

---

### 3.5 Safety Panel (Special Layout)

The SAFETY & CERTS panel has a different inner structure:

```
dhg-facts-panel dhg-panel-safety
├── dhg-facts-panel-header
│   ├── dhg-facts-panel-title → "SAFETY & CERTS"
│   └── dhg-panel-chevron → "▸"
└── dhg-facts-panel-content
    └── dhg-safety-grid (Div Block - CSS Grid 2 columns)
        ├── dhg-safety-item (Div Block)
        │   ├── dhg-safety-label (Text) → "EWG Score"
        │   └── dhg-ewg-score (Text) → {{EWG Score}}
        ├── dhg-safety-item
        │   ├── dhg-safety-label → "Pregnancy Safe"
        │   └── dhg-safety-value → "✓" (conditional)
        ├── dhg-safety-item
        │   ├── dhg-safety-label → "Derm Tested"
        │   └── dhg-safety-value → "✓" (conditional)
        └── dhg-safety-item
            ├── dhg-safety-label → "Hypoallergenic"
            └── dhg-safety-value → "✓" (conditional)
```

---

### 3.6 Add Flip Button (Back)

1. **Add Button** at bottom of `card-back`
2. **Class:** `dhg-flip-btn`
3. **Text:** FLIP

---

## STEP 4: Clean Up Old Elements

You can now remove or repurpose:
- `approval-badge` (replaced by monitor badge)
- `card-header` / `card-type` (replaced by dhg-top-bar)
- `back-to-categories` (replaced by facts panels)

---

## STEP 5: CMS Field Mapping

### Required CMS Fields:

| Field Name | Type | Used For |
|------------|------|----------|
| Product Name | Plain Text | Name display |
| Brand | Reference | Brand link |
| Category | Plain Text | Top bar category |
| Category Icon | Plain Text | Emoji icon |
| Monitor Status | Option | Viral/Trending/New/etc |
| Price | Plain Text | Price display |
| Star Rating | Number | Rating display |
| Community Love Pct | Number | HYPE panel |
| Influencer Pct | Number | HYPE panel |
| Is Dupe | Switch | Dupe tag |
| EWG Score | Number | Safety panel |
| Pregnancy Safe | Switch | Safety panel |
| Derm Tested | Switch | Safety panel |
| Hypoallergenic | Switch | Safety panel |
| Benefits | Multi-Reference | Benefits tags |
| Skin Types | Multi-Reference | Skin type tags |
| Ethics | Multi-Reference | Ethics tags |
| Key Ingredients | Multi-Reference | Ingredient tags |
| Product Images | Multi-Image | Gallery |

---

## STEP 6: Test

1. **Publish** the site
2. **Open** a product page
3. **Test:**
   - [ ] Card flips when clicking FLIP
   - [ ] HYPE/DEAL panels expand/collapse
   - [ ] Facts panels expand/collapse (accordion)
   - [ ] Heart button toggles
   - [ ] All CMS data displays correctly

---

## Quick Reference: All Classes

### Container Classes
- `dhg-card` - Main card container
- `dhg-card-inner` - For 3D flip
- `dhg-card-front` - Front face
- `dhg-card-back` - Back face

### Top Bar
- `dhg-top-bar`
- `dhg-category`
- `dhg-category-icon`
- `dhg-category-text`
- `dhg-top-actions`
- `dhg-icon-btn`
- `dhg-search-btn`
- `dhg-heart-btn`

### Front Elements
- `dhg-image-area`
- `dhg-image-container`
- `dhg-rainbow-edge`
- `dhg-monitor-badge`
- `dhg-badge-icon`
- `dhg-badge-text`
- `dhg-product-info`
- `dhg-product-name`
- `dhg-brand-link`

### Front Panels
- `dhg-front-panels`
- `dhg-panel`
- `dhg-panel-hype`
- `dhg-panel-deal`
- `dhg-panel-header`
- `dhg-panel-title`
- `dhg-panel-chevron`
- `dhg-panel-content`
- `dhg-stat`
- `dhg-stat-love`
- `dhg-stat-influencer`
- `dhg-stat-rating`
- `dhg-price`
- `dhg-tag`
- `dhg-tag-dupe`

### Back Elements
- `dhg-facts-header`
- `dhg-facts-title`
- `dhg-facts-product`

### Back Panels
- `dhg-facts-panels`
- `dhg-facts-panel`
- `dhg-panel-benefits`
- `dhg-panel-skin`
- `dhg-panel-ethics`
- `dhg-panel-ingredients`
- `dhg-panel-safety`
- `dhg-facts-panel-header`
- `dhg-facts-panel-title`
- `dhg-facts-panel-content`
- `dhg-tags`
- `dhg-safety-grid`
- `dhg-safety-item`
- `dhg-safety-label`
- `dhg-safety-value`
- `dhg-ewg-score`

### Buttons
- `dhg-flip-btn`
