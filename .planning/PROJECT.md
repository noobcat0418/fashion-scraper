# Fashion Scraper

## What This Is

An automated pipeline that scrapes fashion retailer websites (starting with COS menswear), extracts structured product data including all color variants, pushes it into Airtable with one row per variant, and runs a GPT-4o scoring step to rate each product's trendiness and quality. The result is a clean, filterable Airtable shopping board for a non-technical client.

## Core Value

Reliable, structured product data flows from COS into Airtable with zero manual effort — every color variant captured, every product scored, every run automated.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Scrape all COS menswear products (all categories: tops, bottoms, outerwear, accessories, etc.)
- [ ] Extract product name, price, category, materials, fit description, color variants, and main image URL
- [ ] Output one row per color variant with its own product URL
- [ ] Normalize prices as numeric value + ISO 4217 currency code
- [ ] Normalize color names to standard color families (navy → blue, light-grey → grey)
- [ ] Handle cookie banners and consent dialogs automatically
- [ ] Push all data to Airtable via API
- [ ] Run GPT-4o scoring step producing a single trendiness/quality score (1-10) per product
- [ ] Store scoring criteria/weights in an Airtable config table the client can edit
- [ ] Run on configurable schedule via Apify Cloud scheduler
- [ ] Create Airtable base with structured schema and useful views (filters, sorts)
- [ ] Architecture supports adding new retailers without rewriting core logic
- [ ] Documentation: step-by-step guide for adding retailers, adjusting scoring, and maintaining the system

### Out of Scope

- Multiple retailers in v1 — COS only; SSENSE/Farfetch are future work
- Personalized taste matching — scoring is objective (materials, price, trendiness), not user-preference-based
- Womenswear/kidswear — menswear only for v1
- Purchase/checkout automation — this is a discovery/browsing tool, not a buying agent
- Mobile app or custom UI — Airtable IS the interface

## Context

- **Client profile**: Non-technical end user. Cannot edit code. All configuration must be via Airtable tables or Apify's web UI.
- **COS website**: H&M Group brand. Product pages have multiple color variants, each potentially with a different URL. Site uses cookie consent banners. Product data is structured but may require browser rendering (not just static HTML).
- **Airtable**: Client does not have an existing workspace — the entire base, schema, and views will be created as part of this deliverable.
- **Scaling path**: Architecture must be retailer-agnostic at the core, with COS-specific scraping logic isolated so new retailers can be added as separate modules.

## Constraints

- **Platform**: Apify Cloud — scraper must be an Apify Actor, not a standalone script
- **Browser automation**: Playwright (Apify's Crawlee library) for rendering JS-heavy pages and handling cookie banners
- **Database**: Airtable — no alternative databases; client uses Airtable for their workflow
- **AI**: OpenAI GPT-4o API for the scoring step
- **Client skill level**: All docs and config must be accessible to a non-technical user
- **Budget-conscious**: Apify free/low tier where possible; GPT-4o calls should be batched efficiently

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Apify Cloud over self-hosted | Built-in scheduling, monitoring, and web UI for non-technical client | — Pending |
| GPT-4o for scoring | Best balance of quality and speed for structured scoring tasks | — Pending |
| Single score (1-10) over multi-dimensional | Simpler for client to filter/sort; avoids decision fatigue | — Pending |
| Scoring config in Airtable table | Client can adjust weights without touching code or Apify | — Pending |
| One row per color variant | Client wants to see/filter by specific colors, not just products | — Pending |
| COS-only v1 with retailer-agnostic architecture | Deliver working product fast, but don't paint into a corner | — Pending |

---
*Last updated: 2026-03-02 after initialization*
