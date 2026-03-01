# Requirements: Fashion Scraper

**Defined:** 2026-03-02
**Core Value:** Reliable, structured product data flows from COS into Airtable with zero manual effort — every color variant captured, every product scored, every run automated.

## v1 Requirements

### Scraping & Extraction

- [ ] **SCRAPE-01**: Scraper renders COS menswear pages via Playwright on Apify Cloud
- [ ] **SCRAPE-02**: Scraper traverses all COS menswear categories and handles pagination automatically
- [ ] **SCRAPE-03**: Scraper extracts product name, price, category, materials, fit description, color variants, and image URLs from `__NEXT_DATA__` JSON
- [ ] **SCRAPE-04**: Scraper auto-dismisses cookie/consent banners without manual intervention
- [ ] **SCRAPE-05**: Each color variant expanded into its own record with variant-specific URL and image
- [ ] **SCRAPE-06**: Main product image URL captured per variant

### Normalization

- [ ] **NORM-01**: Color names normalized to standard families via static lookup (navy → blue, dusty rose → pink)
- [ ] **NORM-02**: Prices normalized to numeric value + ISO 4217 currency code
- [ ] **NORM-03**: COS categories mapped to a stable internal taxonomy
- [ ] **NORM-04**: Records validated against Zod schema before Airtable push; malformed records logged and rejected
- [ ] **NORM-05**: Materials auto-classified into quality tiers (premium/standard/budget) via static lookup

### Airtable Delivery

- [ ] **DATA-01**: One Airtable row per color variant with all extracted and normalized fields
- [ ] **DATA-02**: Idempotent upsert on composite key (product ID + color code) — re-runs update, not duplicate
- [ ] **DATA-03**: Run summary table logging each scrape (products found, new products, errors, timestamp)
- [ ] **DATA-04**: Pre-built Airtable views for filtering by color family, category, score, price range, material tier

### AI Scoring

- [ ] **SCORE-01**: GPT-4o produces a single trendiness/quality score (1-10) per product variant
- [ ] **SCORE-02**: GPT-4o returns brief reasoning text explaining each score
- [ ] **SCORE-03**: Scoring weights stored in Airtable config table the client can edit without code changes
- [ ] **SCORE-04**: Computed value ratio metric (score relative to price) surfacing underpriced quality items

### Tracking & Monitoring

- [ ] **TRACK-01**: Historical price tracking — store price changes over time per variant
- [ ] **TRACK-02**: New product detection — flag variants first seen in the current scrape run
- [ ] **TRACK-03**: Stock/availability status tracked per variant (in-stock vs sold-out)
- [ ] **TRACK-04**: Sale/markdown detection — flag items on sale, detect price drops between runs
- [ ] **TRACK-05**: Size availability tracked per variant (which sizes in stock)

### Architecture & Operations

- [ ] **ARCH-01**: Retailer adapter pattern — COS as first adapter, architecture supports adding new retailers
- [ ] **ARCH-02**: Configurable schedule via Apify Cloud scheduler (daily/weekly/custom)
- [ ] **ARCH-03**: Step-by-step documentation for non-technical client: adding retailers, adjusting scoring, maintenance

## v2 Requirements

### Multi-Retailer

- **MULTI-01**: SSENSE adapter with site-specific extraction logic
- **MULTI-02**: Farfetch adapter with marketplace data model support
- **MULTI-03**: Per-retailer scheduling with independent cron configs

### Expansion

- **EXPAND-01**: Multi-region scraping (different prices/catalogs per country)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Image downloading/local storage | Store URLs only — Airtable renders thumbnails natively, avoids storage costs and copyright risk |
| Real-time/continuous scraping | Daily schedule sufficient for fashion retail; continuous wastes compute and risks IP blocks |
| Custom web UI/dashboard | Airtable IS the interface — building a separate UI is scope creep for a non-technical client |
| Multi-language/multi-region | One region for v1; add regions as separate Actor tasks later |
| Reviews/social proof scraping | COS has minimal on-site reviews; GPT scoring replaces this need |
| LLM-powered category inference | COS provides categories — use static mapping, not expensive LLM calls |
| Price alert notifications | Client can build Airtable automations for email alerts on price changes |
| Full-text search | Airtable's built-in search and filter views are sufficient |

## Traceability

Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCRAPE-01 | Phase 1 | Pending |
| SCRAPE-02 | Phase 1 | Pending |
| SCRAPE-03 | Phase 1 | Pending |
| SCRAPE-04 | Phase 1 | Pending |
| SCRAPE-05 | Phase 1 | Pending |
| SCRAPE-06 | Phase 1 | Pending |
| NORM-01 | Phase 2 | Pending |
| NORM-02 | Phase 2 | Pending |
| NORM-03 | Phase 2 | Pending |
| NORM-04 | Phase 2 | Pending |
| NORM-05 | Phase 2 | Pending |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| SCORE-01 | Phase 3 | Pending |
| SCORE-02 | Phase 3 | Pending |
| SCORE-03 | Phase 3 | Pending |
| SCORE-04 | Phase 3 | Pending |
| TRACK-01 | Phase 4 | Pending |
| TRACK-02 | Phase 4 | Pending |
| TRACK-03 | Phase 4 | Pending |
| TRACK-04 | Phase 4 | Pending |
| TRACK-05 | Phase 4 | Pending |
| ARCH-01 | Phase 1 | Pending |
| ARCH-02 | Phase 4 | Pending |
| ARCH-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-03-02*
*Last updated: 2026-03-02 after roadmap creation*
