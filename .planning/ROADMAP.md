# Roadmap: Fashion Scraper

## Overview

This roadmap delivers an automated COS menswear scraping pipeline that flows structured product data into Airtable with GPT-4o scoring. The build order follows hard dependencies: reliable extraction before normalization, stable Airtable schema before scoring, working pipeline before operational hardening. Four phases take the project from raw browser automation to a fully scheduled, client-operable shopping board.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scraper Infrastructure** - Reliable COS product extraction with retailer adapter pattern
- [ ] **Phase 2: Data Pipeline** - Normalization and Airtable delivery with idempotent upsert
- [ ] **Phase 3: AI Scoring** - GPT-4o trendiness/quality scoring with client-configurable weights
- [ ] **Phase 4: Operations and Tracking** - Scheduling, monitoring, price tracking, and client handoff

## Phase Details

### Phase 1: Scraper Infrastructure
**Goal**: The Apify Actor reliably navigates COS menswear, extracts structured product data for all color variants, and outputs clean records to a Crawlee Dataset -- with the retailer adapter pattern in place from day one
**Depends on**: Nothing (first phase)
**Requirements**: SCRAPE-01, SCRAPE-02, SCRAPE-03, SCRAPE-04, SCRAPE-05, SCRAPE-06, ARCH-01
**Success Criteria** (what must be TRUE):
  1. Actor runs on Apify Cloud and renders COS menswear pages via Playwright without being blocked or hitting cookie consent walls
  2. Actor discovers and traverses all COS menswear categories and paginated listings automatically -- no hardcoded URLs
  3. Each product yields one record per color variant in the Crawlee Dataset, with variant-specific URL, image URL, product name, price, category, materials, fit description, and color name
  4. COS extraction logic lives behind a RetailerAdapter interface -- adding a second retailer does not require modifying any shared pipeline code
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Data Pipeline
**Goal**: Raw product data is normalized and pushed to Airtable as one idempotent row per color variant, with the client seeing real, filterable data for the first time
**Depends on**: Phase 1
**Requirements**: NORM-01, NORM-02, NORM-03, NORM-04, NORM-05, DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. Color names in Airtable use standard families (navy appears as "blue", dusty rose as "pink"), prices show as numeric values with currency codes, and categories use a stable internal taxonomy
  2. Every record passes Zod schema validation before reaching Airtable -- malformed records are logged and rejected, never silently pushed
  3. Re-running the scraper updates existing Airtable records (composite key: product ID + color code) instead of creating duplicates
  4. Airtable base includes pre-built views for filtering by color family, category, price range, and material quality tier
  5. Each scrape run logs a summary record (products found, new products, errors, timestamp) to a Run Log table in Airtable
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: AI Scoring
**Goal**: Every product in Airtable has a GPT-4o trendiness/quality score that the non-technical client can understand, filter by, and reconfigure without touching code
**Depends on**: Phase 2
**Requirements**: SCORE-01, SCORE-02, SCORE-03, SCORE-04
**Success Criteria** (what must be TRUE):
  1. Each product variant in Airtable has a trendiness/quality score (1-10) and a brief text explanation of why it received that score
  2. Scoring weights are stored in an Airtable config table that the client can edit -- changing weights and re-running produces different scores
  3. A computed value ratio metric (score relative to price) is visible in Airtable, surfacing underpriced quality items
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Operations and Tracking
**Goal**: The pipeline runs on a schedule with zero manual intervention, the client can monitor health through Airtable, and historical product data accumulates across runs
**Depends on**: Phase 3
**Requirements**: TRACK-01, TRACK-02, TRACK-03, TRACK-04, TRACK-05, ARCH-02, ARCH-03
**Success Criteria** (what must be TRUE):
  1. The scraper runs on a configurable schedule via Apify Cloud scheduler (daily, weekly, or custom) without manual triggering
  2. Price changes are tracked over time per variant -- the client can see when a product's price dropped or increased
  3. New products are flagged on first appearance, items on sale or with price drops are flagged, and stock/size availability is tracked per variant
  4. Step-by-step documentation exists that a non-technical client can follow to adjust scoring weights, add a new retailer adapter, change the schedule, and troubleshoot common issues
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. Scraper Infrastructure | 0/TBD | Not started | - |
| 2. Data Pipeline | 0/TBD | Not started | - |
| 3. AI Scoring | 0/TBD | Not started | - |
| 4. Operations and Tracking | 0/TBD | Not started | - |
