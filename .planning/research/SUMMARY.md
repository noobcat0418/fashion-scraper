# Project Research Summary

**Project:** Fashion Scraper Pipeline (COS Menswear -> Airtable -> GPT-4o Scoring)
**Domain:** Automated e-commerce product scraping and AI-enriched data pipeline
**Researched:** 2026-03-02
**Confidence:** HIGH (stack and pitfalls); MEDIUM-HIGH (architecture and features)

## Executive Summary

This project is a scheduled scraping pipeline targeting COS (H&M Group) menswear. It extracts product data including color variants, normalizes it, pushes it to Airtable as one row per color variant, and enriches each product with a GPT-4o trendiness/quality score configurable by a non-technical client. The domain is well-understood: Apify Cloud with Crawlee and Playwright is the unambiguous choice for this stack, and all major components have well-documented patterns. The critical insight from research is that COS runs on Next.js, which means product data is available in structured `__NEXT_DATA__` JSON before touching the DOM -- extracting from that source eliminates the most common class of scraper failures (DOM drift) before it starts.

The recommended architecture is a five-stage linear pipeline: crawl -> normalize -> dataset -> Airtable sync -> GPT-4o score. These stages must remain decoupled. The most important architectural decision is the retailer adapter pattern, which must be designed into Phase 1 even though only COS is being built initially. This single decision determines whether adding a second retailer is a day of work or a rewrite. The second most important decision is the Airtable data model: snapshot mode (upsert, current state only) versus time series (append, historical). Snapshot mode is strongly recommended for MVP because it keeps record counts stable and prevents three separate pitfalls simultaneously.

The top risks are not technical complexity -- they are operational fragility. Cookie consent banners block all extraction until solved, bot detection returns empty pages without errors, and DOM drift silently corrupts data if the pipeline falls back to CSS selectors. All three are preventable with architectural choices made in Phase 1: use Ghostery/pre-set cookies for consent, use stealth plugins plus residential proxies for bot detection, and extract from `__NEXT_DATA__` JSON rather than selectors. The Airtable integration adds a separate risk surface (rate limits, record caps, duplicate writes) that requires batch upsert with composite keys from day one.

---

## Key Findings

### Recommended Stack

The stack is TypeScript on Node.js 22 LTS, deployed as an Apify Actor using Crawlee v3.16 with PlaywrightCrawler. This combination is the official Apify recommendation and the most mature option in the scraping ecosystem. Crawlee handles request queuing, retries, proxy rotation, session management, and anti-blocking out of the box -- writing any of this from scratch would add weeks of work with lower reliability.

AI scoring uses the OpenAI SDK (v6.25+) with GPT-4o and Zod's `zodResponseFormat()` to guarantee structured JSON output. Airtable integration uses the official `airtable` JS package (or falls back to direct `fetch()` if ESM compatibility issues arise). All secrets and configuration go through Apify's Actor Input system (defined in `input_schema.json`), giving the non-technical client a UI to adjust settings without touching code.

**Core technologies:**
- **Node.js 22 LTS + TypeScript 5.x:** Apify's recommended runtime; Crawlee is TypeScript-first with full type declarations
- **Crawlee v3.16 + @crawlee/playwright:** Core scraping orchestration; handles retries, proxy rotation, request queues, anti-blocking headers automatically
- **Playwright 1.58.x:** Browser automation via the official Apify Docker image `apify/actor-node-playwright-chrome`; preferred over Puppeteer for auto-waiting and multi-browser support
- **Apify SDK v3.6:** Actor lifecycle, storage (datasets, key-value stores), and structured input/output
- **OpenAI SDK v6.25 + GPT-4o:** AI scoring with structured outputs via `zodResponseFormat()`
- **Zod v4.3:** Schema validation for both scraped data and OpenAI response parsing
- **airtable v0.12.2:** Official JS client for CRUD with built-in rate limit retry
- **Apify Cloud:** Deployment target with built-in scheduling, proxy infrastructure, and monitoring UI

**What not to use:** Puppeteer (inferior to Playwright), Cheerio (COS is an SPA, needs full rendering), LangChain (overkill for a single GPT-4o call), Scrapy (wrong language/ecosystem), any custom scheduler (Apify has one built in), any custom database (Airtable is the database per requirements).

### Expected Features

The feature landscape is clear, with a strict dependency order. Cookie consent handling is a blocker for everything else; `__NEXT_DATA__` extraction unlocks reliable structured data; color variant expansion is the core data transformation; Airtable upsert with composite keys is the non-negotiable data integrity mechanism; GPT-4o scoring is the intelligence layer.

**Must have (table stakes):**
- Browser-automated page rendering (Playwright) -- COS is a Next.js SPA, static HTTP fails
- `__NEXT_DATA__` JSON extraction with DOM fallback -- structured source eliminates selector fragility
- Cookie banner dismissal (Ghostery or pre-set cookies) -- GDPR consent modal blocks all extraction
- Product catalog traversal with pagination -- must discover all products, not just hardcoded URLs
- Color variant expansion: one Airtable row per color variant -- core client requirement
- Color, price, and category normalization -- raw data is unusable for filtering/sorting
- Airtable batch upsert with composite key idempotency -- prevents duplicates on every re-run
- GPT-4o scoring with Airtable-configurable weights -- client adjusts scoring without touching code
- Basic error handling, retry logic, and run summary in Airtable -- essential for non-technical operator

**Should have (differentiators, post-MVP):**
- Score explanation/reasoning field ("why 7/10") -- low cost, high client insight value
- New product detection (flag `first_seen` on current run date) -- trend-spotting value
- Availability/stock status tracking -- identifies popular sold-out items
- Material quality tier classification (premium/standard/budget) -- static lookup, no LLM cost
- Retailer adapter pattern enabling second retailer addition -- architecture decision, not a feature

**Defer to v2+:**
- Historical price tracking -- requires stable data from multiple runs before providing value
- Multi-retailer scraping (SSENSE, Farfetch) -- adapter pattern enables it; actual second adapter is separate milestone
- Multi-region/multi-language scraping -- enormous complexity, unclear incremental value
- Custom dashboard or notification system -- Airtable views and automations replace these

**Do not build:**
- Image downloading/storage (store URLs, not files -- Airtable renders them as thumbnails)
- Real-time/continuous scraping (daily schedule is sufficient for fashion retail)
- Complex LLM-based category classification (COS provides categories; use static mapping)

### Architecture Approach

The system is a five-stage linear data pipeline with a retailer adapter abstraction layer. Each stage has a single responsibility and communicates through well-defined TypeScript interfaces. The pipeline is: Apify Scheduler -> Actor Entry Point -> Retailer Adapter -> Crawlee PlaywrightCrawler + Router -> Normalizer Pipeline -> Crawlee Dataset -> Airtable Sync -> GPT-4o Scoring -> Airtable Score Write-back.

The two-mode Actor pattern (single actor with `mode: 'scrape' | 'score'` input) is preferred over two separate actors for MVP. This keeps deployment simple while maintaining internal separation of concerns. Scraping and scoring should not be coupled in a single execution flow because scoring is slow, expensive, and may need to run independently.

**Major components:**
1. **Retailer Adapter** (`src/retailers/cos/`) -- all COS-specific selectors, URL patterns, cookie handling, and raw extraction; implements `RetailerAdapter` interface so future retailers slot in without touching the rest of the codebase
2. **Crawlee Router** (`src/routes.ts`) -- label-based dispatch: `LISTING` pages discover product URLs and enqueue them as `DETAIL`; `DETAIL` pages extract and normalize; prevents monolithic handler anti-pattern
3. **Normalizer Pipeline** (`src/normalizers/`) -- pure transformation functions: color mapping, price parsing, material extraction, variant explosion (one product -> N rows); shared across all future retailers; unit testable in isolation
4. **Airtable Sync** (`src/integrations/airtable.ts`) -- batch upsert (10 records/request, 4 req/s to stay under the 5 req/s limit) with exponential backoff on 429s; composite key = `retailer + productId + colorNormalized`
5. **GPT-4o Scorer** (`src/integrations/scorer.ts`) -- reads scoring config from Airtable config table, calls OpenAI with structured output, writes scores back; runs as a post-crawl phase

**Key patterns to follow:**
- Retailer Adapter Interface: site-specific logic never leaks into shared pipeline code
- Crawlee Router with Labels: clean separation of listing vs. detail page handling
- Canonical TypeScript Schema: `NormalizedProductRow` is the contract between extraction and storage
- Crawlee Dataset as staging layer: write to dataset during crawl, sync to Airtable in a separate batch phase (eliminates rate-limit coupling between scraping speed and Airtable writes)
- GPT-4o Scoring as separate phase: decouples expensive/slow scoring from time-sensitive scraping

### Critical Pitfalls

1. **Silent data corruption from DOM drift** -- COS redesigns their frontend; CSS class selectors break silently, returning empty arrays with no error. Prevention: extract from `__NEXT_DATA__` JSON first; build a validation layer that checks price range, name non-empty, variant count plausible; maintain canary products with known values. This is the number-one production scraper failure mode across all sources.

2. **Color variant extraction is harder than it looks** -- scraping only the default color and missing 30-70% of variants is common. Fashion retailers implement variant selection differently (dropdown, swatch click, lazy XHR). Prevention: inspect network requests when clicking color swatches; the data is usually in an API call or pre-loaded JSON, not DOM interaction. Test with products that have 5+ colors.

3. **Airtable rate limits and record caps break the pipeline** -- 5 req/s per base, 10 records per batch, and the Team plan's 50,000 record cap are all reachable. As of January 2025, Airtable cut Free plan API calls to 1,000/month. Prevention: batch upsert from day one, exponential backoff on 429, design for snapshot mode (stable record count), calculate your record budget before adding retailers.

4. **Cookie consent banner blocks all extraction** -- COS is EU-based, cookie consent is aggressive (likely OneTrust in a shadow DOM). Prevention: use Ghostery's adblocker for Playwright (Apify's recommendation as of 2025/2026) or pre-set consent cookies in `preNavigationHook`; this must be solved before any other extraction work begins.

5. **Bot detection returns empty/blocked pages without throwing errors** -- H&M Group uses enterprise bot protection; the scraper may silently process a CAPTCHA page as if it were a product page. Prevention: stealth plugin (`playwright-extra` + stealth), residential proxies from day one, implement blocked-page detection (check response length, expected elements, status code) on every page load.

---

## Implications for Roadmap

Based on the combined research, the feature dependency chain and architecture build order converge on a clear 5-phase structure. The phases are ordered by hard dependencies: you cannot normalize data you have not extracted, cannot push to Airtable before normalizing, cannot score before the Airtable schema is stable.

### Phase 1: Foundation (Scraper Infrastructure)

**Rationale:** Cookie consent handling, bot detection, and the retailer adapter pattern are all blockers. Nothing else can be built until a browser can reliably land on a COS product page and extract raw data. This phase also locks in the canonical TypeScript schema and adapter interface, which constrain all future decisions. Changing the schema after Airtable is set up is painful; getting it right now costs an hour.

**Delivers:** An Apify Actor that can navigate COS category pages, handle cookie consent, avoid bot detection, extract raw product JSON from `__NEXT_DATA__`, and output to a local Crawlee Dataset. The retailer adapter interface is defined, making COS the first implementation.

**Addresses (from FEATURES.md):** Browser-automated rendering, `__NEXT_DATA__` extraction, cookie banner dismissal, catalog traversal with pagination.

**Avoids (from PITFALLS.md):** DOM drift (extract from JSON, not selectors), bot detection (stealth plugin + proxy from day one), cookie consent blocking (Ghostery or pre-set cookies), memory/timeout limits (set 2048-4096 MB, implement page batching), geolocation mismatch (pin country URL in config).

**Needs research-phase:** Yes. The exact COS `__NEXT_DATA__` structure, cookie consent provider, and bot detection level are LOW confidence -- they need validation against the live site before extraction code is written.

---

### Phase 2: Data Pipeline (Normalize + Airtable)

**Rationale:** Once raw data flows reliably, normalization and Airtable delivery are the next logical step. These are tightly coupled: the normalization output shape is determined by the Airtable schema, which must be finalized before any records are written. Idempotency (composite key upsert) must be in the first write, not added later.

**Delivers:** Full end-to-end pipeline: scrape -> normalize (color, price, category, variant explosion) -> push to Airtable as one idempotent row per color variant. Client can see real data in Airtable for the first time.

**Addresses (from FEATURES.md):** Color/price/category normalization, one-row-per-variant expansion, Airtable batch upsert with idempotency, image URL extraction, basic error handling and retry.

**Avoids (from PITFALLS.md):** Non-idempotent duplicate writes (composite key upsert from day one), Airtable rate limit cascades (batch 10 records, 4 req/s, exponential backoff on 429), color variant incompleteness (validate variant count per product), price format corruption (extract from structured JSON, store raw string alongside parsed value).

**Needs research-phase:** No. Airtable rate limits, batch API, and upsert patterns are HIGH confidence from official docs.

---

### Phase 3: Intelligence Layer (GPT-4o Scoring)

**Rationale:** Scoring depends on a stable Airtable schema (Phase 2) and must read the scoring config from Airtable itself. It runs as a separate post-crawl phase, not inline with scraping. Cost controls (score per product not per variant, change detection hash, Batch API) should be built at the start, not after the first billing surprise.

**Delivers:** GPT-4o scoring for each product (applied to all its color variants), configurable weights stored in an Airtable config table editable by the non-technical client, scores written back to product rows. Optionally includes reasoning text ("why this score").

**Addresses (from FEATURES.md):** Single-score GPT-4o evaluation, Airtable-configurable scoring weights, score explanation/reasoning (low-effort add).

**Avoids (from PITFALLS.md):** GPT-4o cost spiral (score per product not per variant, hash-based change detection to skip unchanged products, Batch API for 50% discount), scoring failures corrupting upstream data (decoupled phase: scrape failure never invalidates existing scores).

**Needs research-phase:** No. OpenAI structured outputs and scoring patterns are HIGH confidence. Cost model is verified.

---

### Phase 4: Operational Hardening (Monitoring + Scheduling)

**Rationale:** Before handing off to a non-technical client, the pipeline needs observable failure modes, run summary data in Airtable, and scheduling configured with overlap prevention. These are not blocking features for the pipeline to function, but they are blocking features for the client to operate it independently.

**Delivers:** Apify monitoring alerts (volume drop, error rate spike), a "Run Log" Airtable table with per-run summary (products scraped, new products, errors, timestamp), run locking to prevent scheduler overlap, and a client-facing runbook ("what to do when X").

**Addresses (from FEATURES.md):** Run summary dashboard in Airtable, structured logging with Apify monitoring, Apify scheduling configuration.

**Avoids (from PITFALLS.md):** Non-technical client black box (Airtable status table + failure notifications), scheduling overlap race conditions (run locking + idempotent upsert), canary product validation as a production monitoring mechanism.

**Needs research-phase:** No. Apify monitoring and webhook documentation are HIGH confidence.

---

### Phase 5: Multi-Retailer Expansion (SSENSE, Farfetch)

**Rationale:** This phase is enabled by the adapter interface designed in Phase 1. Each new retailer is a new adapter config file implementing the `RetailerAdapter` interface. Normalization, scoring, and Airtable sync are shared. However, SSENSE (Cloudflare) and Farfetch (Akamai + marketplace data model) each require their own anti-bot strategy research.

**Delivers:** Second and third retailer adapters (SSENSE, Farfetch). Each retailer runs as its own Apify Actor task with its own schedule. The shared pipeline handles the rest.

**Addresses (from FEATURES.md):** Multi-retailer extensibility, per-retailer scheduling, shared normalization pipeline.

**Avoids (from PITFALLS.md):** Multi-retailer rewrite risk (adapter interface from Phase 1 prevents this), Airtable record cap (plan the record budget now: COS ~2K rows + SSENSE ~5K rows + Farfetch can easily exceed 50K -- may require upgrading Airtable plan or separating bases before adding Farfetch).

**Needs research-phase:** Yes. SSENSE (Cloudflare bypass) and Farfetch (Akamai bypass, marketplace data model with multiple sellers per product) both need dedicated anti-bot and extraction research before building. Their data models differ from COS significantly.

---

### Phase Ordering Rationale

- **Phase 1 before anything:** Cookie consent, bot detection, and the adapter interface are hard blockers. No extraction is possible without them; no architecture is sound without the adapter pattern.
- **Phase 2 before Phase 3:** Airtable schema must be finalized before GPT-4o scoring writes back to it. Normalization quality determines scoring input quality (garbage in, garbage out).
- **Phase 3 before Phase 4:** Scoring must be validated before handoff. The client must see scores working before the pipeline is handed off as "production."
- **Phase 4 before Phase 5:** Operational visibility for COS must be proven before expanding to more retailers. Monitoring complexity scales with retailer count.
- **Phase 5 is independent:** Multi-retailer is a separate milestone, not a prerequisite for anything. The adapter interface in Phase 1 enables it; nothing else depends on it being built.

### Research Flags

Phases requiring deeper research during planning (run `/gsd:research-phase` before building):
- **Phase 1:** COS-specific `__NEXT_DATA__` structure, cookie consent provider, bot detection level, and pagination API pattern are all LOW confidence. Manual browser inspection of the live COS site is required before writing extraction code. Do not assume H&M Group patterns -- verify COS specifically.
- **Phase 5:** SSENSE (Cloudflare bypass strategy) and Farfetch (Akamai bypass, marketplace product model) both need retailer-specific anti-bot research. Do not assume COS's stealth strategy works for them.

Phases with well-documented patterns (skip research-phase):
- **Phase 2:** Airtable rate limits, batch upsert API, and Crawlee dataset patterns are verified from official docs. Normalization patterns are straightforward.
- **Phase 3:** OpenAI structured outputs, GPT-4o pricing, and Batch API are verified. Scoring architecture follows documented patterns.
- **Phase 4:** Apify monitoring, webhooks, and scheduling are documented platform features.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core technologies verified via official Apify/Crawlee/OpenAI docs. Version numbers confirmed. Alternatives considered and dismissed with documented rationale. |
| Features | HIGH | Table stakes features derived from clear requirements and verified API capabilities. Differentiators and anti-features based on medium-confidence community sources but consistent across multiple. |
| Architecture | MEDIUM-HIGH | Crawlee/Apify patterns are HIGH confidence from official docs. Retailer adapter pattern synthesized from multiple verified scraper architectures. COS-specific data structure (\_\_NEXT\_DATA\_\_) is MEDIUM -- inferred from H&M Group patterns, not verified against live COS site. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (DOM drift, Airtable rate limits, cookie consent, bot detection) are HIGH confidence, verified across multiple authoritative sources. COS-specific anti-bot provider is unconfirmed (MEDIUM). Geolocation behavior is MEDIUM. |

**Overall confidence:** HIGH for architectural and technology decisions; MEDIUM for COS-specific implementation details that require live site validation.

### Gaps to Address

- **COS \_\_NEXT\_DATA\_\_ structure:** Inferred from H&M Group patterns (verified via H&M scraper actor). COS may use newer Next.js App Router with `self.__next_f.push()` Flight data format instead. Validate against live COS site in Phase 1 before building extraction logic. Budget time for this discovery.
- **COS cookie consent provider:** Assumed to be OneTrust based on H&M Group usage patterns. Must be verified via browser inspection. The pre-set cookie strategy requires knowing the exact cookie names COS sets.
- **COS bot detection level:** H&M Group's specific provider and aggressiveness are unconfirmed. Could be lighter than assumed (making datacenter proxies viable) or heavier (requiring residential proxies from day one). Test early with datacenter, escalate to residential if blocked.
- **Airtable upsert via `performUpsert`:** The official `airtable.js` package's upsert capability via `performUpsert` needs implementation validation. The library is not actively maintained; if it doesn't support upsert, fall back to direct `fetch()` against the REST API.
- **COS pagination strategy:** Whether COS uses server-rendered first page + REST API for subsequent pages (common in Next.js) or another pattern must be verified during Phase 1 crawl development.
- **Snapshot vs. time series decision:** This must be made before Airtable schema is finalized. The recommendation is snapshot mode for MVP, but the client may request price history tracking. If they do, this becomes a significant architectural change and should add a separate archive mechanism rather than switching to append mode in the main table.

---

## Sources

### Primary (HIGH confidence)
- [Crawlee GitHub releases v3.16.0](https://github.com/apify/crawlee/releases) -- Crawlee version and stability
- [Crawlee Official Docs - Router](https://crawlee.dev/js/api/core/class/Router) -- Routing pattern
- [Crawlee Official Docs - PlaywrightCrawler](https://crawlee.dev/js/api/playwright-crawler) -- Crawler configuration
- [Crawlee Result Storage](https://crawlee.dev/js/docs/guides/result-storage) -- Dataset pattern
- [Apify Actor Development](https://docs.apify.com/platform/actors/development) -- Actor structure
- [Apify input schema specification](https://docs.apify.com/platform/actors/development/actor-definition/input-schema/specification/v1) -- Actor input UI
- [Apify base Docker images](https://docs.apify.com/platform/actors/development/actor-definition/dockerfile) -- Container setup
- [Apify Platform Limits](https://docs.apify.com/platform/limits) -- Memory, timeout constraints
- [Airtable Rate Limits](https://airtable.com/developers/web/api/rate-limits) -- 5 req/s, 10 records/batch
- [OpenAI structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs/) -- GPT-4o JSON output
- [OpenAI API Pricing](https://openai.com/api/pricing/) -- GPT-4o cost model
- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch) -- 50% cost discount
- [Apify cookie modal blocking](https://blog.apify.com/how-to-block-cookie-modals/) -- Ghostery approach

### Secondary (MEDIUM confidence)
- [H&M Scraper Actor](https://github.com/emastra/actor-hm-scraper) -- H&M Group `__NEXT_DATA__` patterns
- [Next.js Scraping in 2025](https://www.trickster.dev/post/scraping-nextjs-web-sites-in-2025/) -- `__NEXT_DATA__` and App Router Flight data format
- [Apify: Playwright vs Puppeteer](https://blog.apify.com/playwright-vs-puppeteer/) -- Framework choice rationale
- [DataWeave: Normalizing Color in Fashion](https://dataweave.com/blog/normalizing-size-and-color-in-fashion-using-ai-to-power-competitive-price-intelligence) -- Color normalization complexity
- [Apify Anti-Scraping Academy](https://docs.apify.com/academy/anti-scraping) -- Bot detection patterns
- [playwright-autoconsent](https://github.com/peixotorms/npm-playwright-autoconsent) -- Cookie consent alternative
- [Airtable record limit wall](https://servalian.com/blog/airtable-record-limits) -- 50K record cap implications

### Tertiary (LOW confidence -- needs validation)
- COS-specific `__NEXT_DATA__` structure -- inferred from H&M Group patterns, not verified against live COS
- COS cookie consent provider (assumed OneTrust) -- needs manual browser inspection
- COS bot detection provider -- unconfirmed; assumed enterprise-grade based on H&M Group profile
- COS pagination API pattern -- inferred from Next.js conventions, not verified

---
*Research completed: 2026-03-02*
*Ready for roadmap: yes*
