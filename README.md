# 🦆❤️👻 Duck Heart Ghost

**Clean beauty product discovery — finally honest.**

Duck Heart Ghost (DHG) is a card-based beauty discovery platform where users vote on products by swiping Duck 🦆 (maybe), Heart ❤️ (love/save), or Ghost 👻 (filter out). Every card discloses conflicts of interest. No scores. No prescriptive recommendations. Just data and transparency.

---

## What Makes DHG Different

- **Conflict of interest disclosure on every card** — affiliate relationships are shown, not hidden
- **Vote-gated social proof** — community data only reveals after you vote
- **Rabbit hole linking** — every ingredient, brand, and retailer connects to its own card
- **No numerical scores shown to users** — you form your own opinion
- **Ghost is private** — your Ghost votes are never shown to brands or retailers

---

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React / Next.js (Vercel) |
| CMS | Webflow (headless) |
| Database / Auth | Supabase |
| Product Categorizer API | Node.js + OpenAI Agents SDK on Render.com |
| Scraping | Custom Python scripts |
| Version Control | GitHub |

---

## Project Structure

```
app/src/
  app/
    test-back/          ← staging route for card back
    test-back-v10/      ← comparison staging route
    brands/             ← brand rabbit hole cards
    ingredients/        ← ingredient rabbit hole cards
  components/
    ProductCard.tsx     ← main card component (front + back)
    ProductFactsBack.jsx ← card back (Product Facts panel)
    IngredientCard.tsx
    BrandCard.tsx
```

---

## Running Locally

```bash
cd /Users/jenmurphy/Desktop/duckheartghost
npm install
npm run dev
```

Then open **http://localhost:3000**

---

## Deploying

Push to `main` — Vercel auto-deploys.

```bash
git add .
git commit -m "your message"
git push
```

---

## Staging / Testing

Always test on staging routes before touching production components:

- **https://duckheartghost.vercel.app/test-back** — current card back
- **https://duckheartghost.vercel.app/test-back-v10** — comparison version

---

## Card Back — Product Facts Sections

| Section | Color | Contents |
|---|---|---|
| IS IT SAFE? | `#e9455c` | EWG score, certifications, regulatory |
| WHAT DOES IT DO? | `#ff6eb0` | Benefits, finish, coverage |
| WHO'S IT FOR? | `#9955ff` | Skin type, skin concerns, best for, not ideal for |
| WHAT IS IT? | `#3f8def` | Key ingredients, full ingredient deck, formula, packaging |
| WHAT'S THE DEAL? | `#00c4b0` | Price, retailers, affiliate disclosure |

---

## Color System

| Use | Hex |
|---|---|
| Rabbit hole links (all navigation) | `#ff8c2a` |
| Ingredient pills | `#44ddee` |
| IS IT SAFE? | `#e9455c` |
| WHAT DOES IT DO? | `#ff6eb0` |
| WHO'S IT FOR? | `#9955ff` |
| WHAT IS IT? | `#3f8def` |
| WHAT'S THE DEAL? | `#00c4b0` |

---

## Environment Variables

Set these in Vercel dashboard → Settings → Environment Variables:

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
OPENAI_API_KEY=
```

**Never hardcode these in component files.**

---

## Affiliate Disclosure

DHG earns a commission on purchases made through retailer links. Every card shows this disclosure. This is intentional and non-negotiable — transparency is the whole point.

---

*Built by a cosmetic formulator who got tired of not being able to trust beauty recommendations.*
