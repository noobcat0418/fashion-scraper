# Feature Landscape

**Domain:** Automated fashion product scraping and aggregation pipeline
**Researched:** 2026-03-02
**Target retailer:** COS (H&M Group) menswear, with multi-retailer extensibility
**Client profile:** Non-technical end-user consuming data in Airtable

---

## Table Stakes

Features the pipeline must have or it is fundamentally broken. Missing any of these means the scraper produces unusable output or fails silently.

### Scraping & Extraction

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Browser-automated page rendering** | COS is a Next.js site requiring JavaScript execution. Static HTTP requests will not yield product data. | Med | Playwright on Apify Cloud. COS (H&M Group) embeds product data in `__NEXT_DATA__` JSON script tags -- extract from there first, fall back to DOM selectors only if needed. [HIGH confidence -- verified via H&M scraping patterns and Next.js scraping guides] |
| **Product catalog traversal** | Must navigate category listings and pagination to discover all menswear products, not just a hardcoded URL list. | Med | COS uses server-rendered first page (`__NEXT_DATA__`) and REST API calls for subsequent pages. Pagination handler must support both patterns. |
| **Structured field extraction** | Product name, price, category, materials, fit description, color variants, and image URLs are the core deliverables. Without structured extraction, there is no pipeline. | Med | Map JSON fields from `__NEXT_DATA__` or API responses to a flat schema. Materials and fit may require parsing from description text. |
| **Color variant expansion (one row per variant)** | Client requirement: each color variant becomes its own Airtable row. Without this, downstream scoring and filtering break. | Low | COS product JSON typically includes a `colorVariants` or `articles` array. Iterate and emit one record per entry. |
| **Cookie banner dismissal** | COS (EU-based retailer) shows GDPR cookie consent modals that block page interaction. Scraper hangs or gets incomplete data without handling this. | Low | Use Ghostery adblocker integration for Playwright (Apify-recommended, handles 100+ consent providers including COS's OneTrust). Alternatively, `playwright-autoconsent` npm package. [HIGH confidence -- verified via Apify blog] |
| **Image URL extraction** | Client needs product images in Airtable. Image URLs are part of the core data contract. | Low | Extract from product JSON. COS CDN URLs follow predictable patterns. Store URL strings, not downloaded files (Airtable can render URLs as images). |

### Data Normalization

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Color normalization** | Raw colors like "navy", "dusty blue", "midnight" must map to canonical color names ("blue") for filtering and aggregation. Without this, the client cannot filter by color effectively. | Med | Build a static lookup table for the ~30 common fashion colors. Use LLM fallback only for genuinely ambiguous cases. A deterministic map is faster, cheaper, and more predictable than sending every color through GPT. |
| **Price normalization** | Prices must be numeric values with ISO 4217 currency codes. COS shows prices in various regional formats (EUR, GBP, SEK). Mixed formats break sorting and comparison. | Low | Parse price strings to `{ amount: number, currency: string }`. Handle comma vs dot decimal separators. Strip currency symbols. Store as separate `price` and `currency` fields. |
| **Category normalization** | COS category names may change or vary. Pipeline needs consistent category taxonomy. | Low | Map COS-specific categories (e.g., "Knitwear", "Coats and jackets") to a stable internal taxonomy. Store both raw and normalized values. |

### Data Delivery

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Airtable push (one row per color variant)** | This is the client's data consumption point. No Airtable = no value delivered. | Med | Use Airtable REST API with batch upsert (up to 10 records per request, 5 QPS per base). Upsert on a unique key (product ID + color code) to avoid duplicates on re-runs. [HIGH confidence -- verified via Airtable API docs] |
| **Idempotent re-runs** | Scraper will run on a schedule. Running twice must not create duplicate rows. | Med | Upsert (not append) using Airtable's `performUpsert` with a composite key field. This is the single most important data integrity feature. |
| **Basic error handling and retry** | Network failures, rate limits, and transient errors are routine in scraping. Pipeline must not silently lose data. | Med | Apify's Crawlee SDK has built-in request retry with backoff. Add Airtable write retry with exponential backoff for 429 responses. Log failed URLs for manual inspection. |

### GPT Scoring

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Single-score GPT-4o evaluation** | Client requirement: each product variant gets a 1-10 trendiness/quality score. | Med | Send product metadata (name, materials, category, price) to GPT-4o with a scoring prompt. Return single integer. Keep prompt simple and deterministic. |
| **Configurable scoring weights from Airtable** | Client (non-technical) must be able to adjust what factors matter in the score without touching code. | Med | Read weights from an Airtable "Config" table (rows like: "Material weight: 0.3", "Price weight: 0.2"). Inject weights into the GPT prompt dynamically. Client edits the table, scoring changes on next run. |

---

## Differentiators

Features that add meaningful value beyond the baseline. Not required for launch but create competitive advantage or significantly improve the client experience.

### Enhanced Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Score explanation / reasoning** | Instead of just "7/10", show WHY the product scored that way ("premium wool blend, on-trend oversized fit, above-average price point"). Client gains insight, not just numbers. | Low | Ask GPT-4o to return `{ score: 7, reasoning: "..." }` in a single call. Minimal extra cost. Store reasoning in a long-text Airtable field. |
| **Historical price tracking** | Track price changes over time per product. Detect sales, markdowns, and seasonal pricing patterns. | Med | Requires storing scrape timestamps and comparing against previous values. Add `last_price`, `price_change`, `first_seen`, `last_seen` fields. Airtable can handle this with formula fields. |
| **New product detection alerts** | Notify client when new products appear in a category. High value for trend-spotting. | Low | Compare current scrape results against existing Airtable records. Flag records where `first_seen == current_run_date`. Client can create an Airtable view filtering on this. |
| **Availability / stock monitoring** | Track which variants are in stock vs sold out. Useful for identifying popular items. | Low | Extract stock status from product JSON (COS includes availability per variant). Store as boolean field. |
| **Material quality classification** | Categorize materials into tiers (premium: cashmere, silk, merino; standard: cotton, polyester; budget: synthetic blends). | Low | Static lookup table, not LLM. ~50 common materials mapped to 3-4 tiers. Enables filtering by material quality in Airtable. |

### Multi-Retailer Extensibility

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Retailer adapter pattern** | Architecture that makes adding a new retailer a configuration task (new selectors + field mapping), not a rewrite. | Med | Define a `RetailerConfig` interface: base URL, pagination strategy, field mappings, normalization overrides. COS is the first adapter. Each new retailer is a new config file, not a new codebase. |
| **Shared normalization pipeline** | All retailers feed through the same color/price/category normalization. Consistency across sources. | Low | Already building normalization for COS. Make it retailer-agnostic from the start. Accept raw values in, emit normalized values out. |
| **Per-retailer scheduling** | Different retailers may need different scrape frequencies or have different rate-limit tolerances. | Low | Apify supports per-actor scheduling. Each retailer gets its own Actor task with its own cron. |

### Operational Quality

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Run summary dashboard in Airtable** | After each scrape, write a summary row: total products scraped, new products, errors, timestamp. Client sees pipeline health without technical tools. | Low | Write to a "Run Log" table in Airtable. One row per run. Client can see "last successful run was 2 hours ago, scraped 342 products, 0 errors." |
| **Structured logging with Apify monitoring** | Apify's built-in monitoring detects volume drops, failure spikes, and schema drift. Alerts via email/Slack. | Low | Enable Apify monitoring on the Actor. Configure alert thresholds (e.g., "alert if <100 products scraped" or "alert if error rate >5%"). [MEDIUM confidence -- Apify docs describe this feature] |
| **Data validation layer** | Validate each record against a schema before pushing to Airtable. Catch malformed data before it pollutes the client's workspace. | Med | Use Zod or a similar schema validator. Check: price > 0, name non-empty, color present, image URL valid. Reject invalid records to a separate error log. |

---

## Anti-Features

Features to deliberately NOT build. These are common mistakes or scope-creep traps in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Downloading and storing product images locally** | Massive storage costs, CDN bandwidth waste, copyright risk, and Airtable attachment limits (per-base storage caps). COS CDN URLs are stable and publicly accessible. | Store image URLs as text fields. Airtable renders them as thumbnails natively. If the client needs offline copies, that is a separate manual step. |
| **Real-time / continuous scraping** | COS updates inventory at most daily. Continuous scraping wastes compute, risks IP blocks, and violates rate-limit etiquette. Over-engineering for zero marginal value. | Schedule daily or twice-daily scrapes via Apify cron. Sufficient for fashion retail where product turnover is weekly, not hourly. |
| **Building a custom dashboard / web UI** | The client is non-technical and already uses Airtable. Building a separate UI is massive scope creep and the client must learn a new tool. | Use Airtable views, filters, and the Interfaces feature as the presentation layer. Zero custom UI code. |
| **Multi-language / multi-region scraping** | Scraping COS in 15 countries simultaneously adds enormous complexity (different prices, different catalogs, different cookie laws) with unclear value. | Start with one region (the client's market). Add regions only when client explicitly requests it, and then as separate Actor tasks with region-specific config. |
| **Scraping user reviews / social proof** | COS has minimal on-site reviews. The effort-to-value ratio is terrible. Fashion retail reviews are sparse and low-signal compared to Amazon. | Skip entirely. GPT scoring replaces the need for review aggregation. If review data becomes valuable later, it is a separate Actor. |
| **Complex LLM-powered category inference** | Using GPT to categorize products when COS already provides explicit category data is burning money for no reason. | Use COS's own category taxonomy. Map it with a static lookup. LLMs are for scoring (where human judgment is needed), not for classification (where the source provides the data). |
| **Price alert / notification system** | Building email/SMS/push notifications for price drops is a separate product, not a scraping pipeline feature. | Store price history. Let the client build Airtable automations (built-in feature) to email themselves when a formula field detects a price change. |
| **Full-text search across products** | Airtable already has search. Building Elasticsearch or similar is absurd scope creep for a pipeline that serves one client. | Use Airtable's built-in search and filter views. |
| **Scraping competitor pricing for comparison** | Adding non-COS retailers "for comparison" before the COS scraper is solid is premature. Multi-retailer is a future phase, not an MVP feature. | Build COS first with the retailer adapter pattern. The architecture supports adding competitors later, but do not build them now. |

---

## Feature Dependencies

```
Cookie Banner Handling
  |
  v
Browser Automation (Playwright on Apify)
  |
  v
Catalog Traversal (pagination)
  |
  v
Structured Field Extraction (__NEXT_DATA__ parsing)
  |
  +--> Color Variant Expansion
  |      |
  |      v
  |    Color Normalization --> Price Normalization --> Category Normalization
  |                                  |
  |                                  v
  |                          Data Validation Layer
  |                                  |
  |                                  v
  |                          Airtable Upsert (idempotent)
  |                                  |
  |                                  v
  |                          GPT-4o Scoring (reads from Airtable config)
  |                                  |
  |                                  v
  |                          Score Written Back to Airtable
  |
  +--> Image URL Extraction (parallel with variant expansion)
```

**Key dependency chains:**

1. **Scraping before normalization:** You cannot normalize data you have not extracted. Extraction must be solid before investing in normalization logic.
2. **Normalization before Airtable push:** Pushing raw, un-normalized data creates cleanup debt in the client's workspace.
3. **Airtable push before GPT scoring:** Scoring needs the config weights from Airtable, and scoring results write back to the same row. The Airtable schema must be stable first.
4. **Cookie handling before everything:** If the cookie banner is not dismissed, the scraper sees an overlay, not product data. This is a prerequisite for all extraction.
5. **Retailer adapter pattern is a design decision, not a phase:** The COS scraper should be structured as the first adapter from day one. This is an architectural choice, not a feature to add later.

---

## MVP Recommendation

For MVP, build these in order:

1. **Apify Actor with Playwright + cookie banner handling** -- The foundation. Without browser automation that handles consent modals, nothing works.
2. **COS catalog traversal and `__NEXT_DATA__` extraction** -- Get raw product data flowing. Validate against the COS site manually.
3. **Color variant expansion + normalization pipeline** -- Transform raw data into the one-row-per-variant format the client expects. Includes color, price, and category normalization.
4. **Airtable upsert with idempotency** -- Deliver data to where the client consumes it. Use composite key upsert from day one.
5. **GPT-4o scoring with Airtable-driven weights** -- The intelligence layer. Read weights from config table, score each variant, write score back.
6. **Basic monitoring and error handling** -- Run summary table, Apify monitoring alerts, retry logic for transient failures.

**Defer to post-MVP:**
- Historical price tracking: Requires multiple runs of stable data before it provides value. Add after the pipeline has run reliably for 1-2 weeks.
- Multi-retailer support: The adapter pattern should be in the architecture from day one, but the second retailer adapter is a separate milestone.
- Score reasoning/explanation: Low-effort but low-priority. Add once the client has validated the scoring is useful.
- Data validation layer (Zod schema): Important for robustness but the pipeline can ship with basic checks (non-null fields) and add strict validation iteratively.

---

## Sources

**HIGH confidence (official docs, verified):**
- [Apify cookie modal blocking](https://blog.apify.com/how-to-block-cookie-modals/) -- Ghostery adblocker integration for Playwright
- [Apify Airtable integration](https://docs.apify.com/platform/integrations/airtable) -- Native OAuth integration with field mapping and dedup
- [Airtable API rate limits](https://airtable.com/developers/web/api/rate-limits) -- 5 QPS per base, 10 records per batch
- [Apify monitoring](https://docs.apify.com/platform/monitoring) -- Built-in alert system for Actor runs
- [Next.js `__NEXT_DATA__` scraping](https://www.trickster.dev/post/scraping-nextjs-web-sites-in-2025/) -- Techniques for extracting data from Next.js hydration

**MEDIUM confidence (multiple sources agree):**
- [H&M scraper patterns](https://github.com/emastra/actor-hm-scraper) -- H&M Group sites use `__NEXT_DATA__` JSON for product data
- [LLM data normalization](https://scrapingant.com/blog/llm-powered-data-normalization-cleaning-scraped-data) -- Hybrid approach: deterministic extractors for stable fields, LLM for ambiguous data
- [LLM rubric scoring](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/) -- Weighted criteria rubrics for LLM evaluation
- [Ecommerce scraper features](https://tendem.ai/blog/ecommerce-data-scraping-guide) -- Standard data fields and pipeline patterns
- [Multi-retailer architecture](https://github.com/orgs/community/discussions/174081) -- Plugin/adapter pattern with per-site configs
- [Apify error handling](https://docs.apify.com/academy/api/retry-failed-requests) -- Built-in retry with backoff
- [playwright-autoconsent](https://github.com/peixotorms/npm-playwright-autoconsent) -- Handles 100+ cookie consent providers

**LOW confidence (single source, unverified):**
- COS-specific product JSON structure: Inferred from H&M Group patterns. Needs validation against actual COS pages during development.
- Airtable Sync API (10,000 rows per CSV request): Mentioned in community discussions but not verified against official docs. May be relevant for bulk loading.
