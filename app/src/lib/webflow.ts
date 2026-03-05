const WEBFLOW_API_TOKEN = process.env.WEBFLOW_API_TOKEN!;
const COLLECTION_ID = "697d3803e654519eef084068";

function parsePills(str: string | undefined): { label: string; tooltip: string }[] {
  if (!str) return [];
  return str.split(",").map(s => s.trim()).filter(Boolean).map(s => {
    const [name, ...rest] = s.split(":");
    return { label: name.trim(), tooltip: rest.join(":").trim() };
  });
}

function getPriceTier(price: number): string {
  if (price < 20) return "Budget";
  if (price < 50) return "Accessible";
  if (price < 100) return "Prestige";
  return "Luxury";
}

function getPricePerOz(price: number, size: string): string {
  if (!size || size === "N/A") return "";
  const ozMatch = size.match(/([\d.]+)\s*oz/i);
  const mlMatch = size.match(/([\d.]+)\s*ml/i);
  const gMatch = size.match(/([\d.]+)\s*g/i);
  if (ozMatch) {
    const oz = parseFloat(ozMatch[1]);
    if (oz > 0) return `$${(price / oz).toFixed(2)}/oz`;
  }
  if (mlMatch) {
    const ml = parseFloat(mlMatch[1]);
    const oz = ml / 29.5735;
    if (oz > 0) return `$${(price / oz).toFixed(2)}/oz`;
  }
  if (gMatch) {
    const g = parseFloat(gMatch[1]);
    if (g > 0) return `$${(price / g).toFixed(2)}/g`;
  }
  return "";
}

function stripHtml(html: string | undefined): string {
  if (!html) return "";
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

export async function getFirstPublishedProduct() {
  const res = await fetch(
    `https://api.webflow.com/v2/collections/${COLLECTION_ID}/items?limit=100`,
    {
      headers: { Authorization: `Bearer ${WEBFLOW_API_TOKEN}` },
      next: { revalidate: 3600 },
    }
  );
  const data = await res.json();
  const items = data.items || [];
  const item = items.find(
    (i: any) => !i.isDraft && !i.isArchived && i.fieldData["affiliate-url"]
  );
  if (!item) return null;
  return mapWebflowToProduct(item.fieldData);
}

export async function getProductBySlug(slug: string) {
  let offset = 0;
  const limit = 100;
  while (offset < 1200) {
    const res = await fetch(
      `https://api.webflow.com/v2/collections/${COLLECTION_ID}/items?limit=${limit}&offset=${offset}`,
      {
        headers: { Authorization: `Bearer ${WEBFLOW_API_TOKEN}` },
        next: { revalidate: 3600 },
      }
    );
    const data = await res.json();
    const items = data.items || [];
    const item = items.find((i: any) => i.fieldData.slug === slug);
    if (item) return mapWebflowToProduct(item.fieldData);
    if (items.length < limit) break;
    offset += limit;
  }
  return null;
}

function mapWebflowToProduct(f: any) {
  const price = f["product-price"] || 0;
  const size = f["size"] || "";

  const safetyRaw = parsePills(f["safety-attributes"]);
  const certKeywords = ["verified", "tested", "free", "certified", "vegan", "cruelty", "organic", "natural", "clean", "ecocert", "cosmos", "usda", "leaping bunny", "b corp", "made safe", "ewg"];
  const certifications = safetyRaw.filter(p => certKeywords.some(k => p.label.toLowerCase().includes(k)));
  const regulations = safetyRaw.filter(p => !certKeywords.some(k => p.label.toLowerCase().includes(k)));

  const suitabilityRaw = parsePills(f["suitability-attributes"]);
  const skinTypeKeywords = ["dry", "oily", "combination", "sensitive", "normal", "mature", "dehydrated", "acne"];
  const notForKeywords = ["not for", "avoid", "not ideal", "not recommended"];
  const skinTypes = suitabilityRaw.filter(p => skinTypeKeywords.some(k => p.label.toLowerCase().includes(k)));
  const notFor = suitabilityRaw.filter(p => notForKeywords.some(k => p.label.toLowerCase().includes(k)));
  const personas = suitabilityRaw.filter(p =>
    !skinTypeKeywords.some(k => p.label.toLowerCase().includes(k)) &&
    !notForKeywords.some(k => p.label.toLowerCase().includes(k))
  );

  return {
    name: f["name"] || "",
    brand: f["brand-name"] || "",
    brandSlug: (f["brand-name"] || "").toLowerCase().replace(/\s+/g, "-"),
    price: price ? `$${price}` : "",
    pricePerOz: getPricePerOz(price, size),
    priceTier: getPriceTier(price),
    size: size,
    category: "",
    type: "",
    formulation: "",
    packaging: "",
    verified: "Mar 2026",
    sections: {
      safe: {
        ewgScore: "",
        ewgLabel: "",
        certifications,
        regulations,
      },
      does: {
        spf: f["spf-value"] || null,
        benefits: parsePills(f["support-attributes"]),
        finish: [],
        coverage: [],
      },
      for: {
        skinTypes,
        skinConcerns: parsePills(f["skin-concerns"]),
        personas,
        notFor,
        shadeCount: f["shade-count"] || null,
      },
      is: {
        keyIngredients: parsePills(f["key-actives"]).map(p => {
        const [name, ...rest] = p.label.split(":");
        return { label: name.trim(), tooltip: rest.join(":").trim(), slug: name.trim().toLowerCase().replace(/\s+/g, "-") };
      }),
        allIngredients: [],
        rawIngredients: stripHtml(f["ingredients-2"]),
        description: stripHtml(f["what-it-is-2"]) || "",
        formulaBase: parsePills(f["formula-base"]),
        packaging: [],
      },
      deal: {
        price: price ? `$${price}` : "",
        pricePerOz: getPricePerOz(price, size),
        priceTier: getPriceTier(price),
        retailers: f["affiliate-url"] ? [
          { label: "Credo Beauty", url: f["affiliate-url"], active: true },
        ] : [],
        affiliateNote: "DHG earns a small commission when you shop these links — disclosed because that's the whole point.",
      },
    },
  };
}
