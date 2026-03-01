# Domain Pitfalls: Fashion Product Scraping Pipeline

**Domain:** Automated fashion product scraping (COS menswear -> Airtable -> GPT-4o scoring)
**Researched:** 2026-03-02
**Overall confidence:** MEDIUM-HIGH (multiple sources corroborate most findings; some COS-specific claims are LOW confidence due to limited direct evidence)

---

## Critical Pitfalls

Mistakes that cause rewrites, total pipeline failures, or fundamentally broken data.

---

### Pitfall 1: Silent Data Corruption After Site Redesign (DOM Drift)

**What goes wrong:** COS (or any H&M Group brand) pushes a frontend update -- new CSS classes, restructured product cards, changed JSON-LD schema. The scraper keeps running without errors but extracts garbage data: product descriptions land in price fields, color names become empty strings, variant counts silently drop. The pipeline happily pushes corrupted records to Airtable and runs GPT-4o scoring on nonsense.

**Why it happens:** Selectors are inherently brittle. H&M Group has been investing in modern frontend architecture (React/Next.js based, per job postings for their Portfolio Brands Engineering team). Modern JS frameworks generate dynamic class names (e.g., CSS Modules, styled-components) that change on every build. A class like `.product-card_abc123` becomes `.product-card_def456` after a deploy. Your scraper sees zero matches and returns empty arrays -- no error thrown.

**Consequences:**
- Weeks of corrupted data in Airtable before anyone notices
- GPT-4o scores become meaningless (garbage in, garbage out)
- Non-technical client loses trust in the system
- Retroactive cleanup is painful -- which records are good vs. bad?

**Prevention:**
1. **Never rely solely on CSS class selectors.** Prefer data attributes (`data-testid`, `data-product-id`), ARIA roles, semantic HTML elements (`<h1>`, `<article>`, `<price>`), or structural patterns (nth-child relationships) that survive redesigns.
2. **Extract from structured data first.** Check for JSON-LD, `__NEXT_DATA__`, or internal API endpoints before touching the DOM. H&M Group sites likely embed product data as JSON in the page source or fetch from internal APIs -- scrape that structured data instead of visual elements.
3. **Build a validation layer.** After every scrape run, check: Does every product have a non-empty name? Is the price a valid number within a sane range (e.g., 10-5000 for COS menswear)? Are there at least N color variants? If validation fails, halt the pipeline and alert.
4. **Use canary products.** Maintain a list of 3-5 known products with known prices/colors. After each run, verify these match expected values. If they drift, the scraper is broken.
5. **Schema fingerprinting.** Hash the DOM structure around product data on each run. If the fingerprint changes, flag for human review before pushing to Airtable.

**Detection:** Record counts drop suddenly. Price values are NaN or $0. Color fields are empty. Product names contain HTML fragments. GPT-4o scores cluster at extremes.

**Confidence:** HIGH -- this is universally cited as the number-one production scraper failure mode across multiple authoritative sources (Scrapfly, Crawlbase, Oxylabs, Apify Academy).

**Phase mapping:** Must be addressed in Phase 1 (core scraper). Validation layer should be built alongside extraction, not bolted on later.

---

### Pitfall 2: Color Variant Extraction is Harder Than It Looks

**What goes wrong:** The scraper extracts the "default" product (first color shown) but misses other color variants, or extracts colors inconsistently. Common failures:
- Only scraping the initially loaded color, missing others behind JavaScript interactions
- Getting marketing color names ("Dusty Rose", "Ocean Breeze") that are useless for normalization
- Duplicate rows because the same product in different colors shares some data
- The first variant overwrites the main product line because it occupies the same DOM node
- Missing the mapping between swatch images and color names

**Why it happens:** Fashion color variants are implemented differently across every retailer:
- Some use dropdown selectors that require JavaScript interaction
- Some lazy-load variant data only when a swatch is clicked
- Some embed all variants in a hidden JSON blob, others fetch via XHR
- Color names are not standardized -- "Navy", "Dark Blue", "Midnight" may all be the same color
- COS specifically uses swatch elements that may require clicking to load variant-specific data (price, images, availability)

Research from DataWeave found 1000+ unique color values for a single apparel category at a single retailer, making lookup-table approaches fragile at scale.

**Consequences:**
- Incomplete dataset (missing 30-70% of actual variants)
- Duplicate records in Airtable (same product counted multiple times or inconsistently)
- Color normalization breaks downstream GPT-4o scoring
- Adding retailers later (SSENSE, Farfetch) requires completely different variant extraction logic per site

**Prevention:**
1. **Find the data source, not the UI.** Before writing click-interaction code, inspect network requests when clicking color swatches. The variant data likely comes from an API call or is pre-loaded in page JSON. Extract from the data source directly.
2. **Build a color normalization map early.** Create a mapping table (marketing name -> normalized name) and grow it incrementally. Use GPT-4o itself to help classify ambiguous colors into a fixed taxonomy (e.g., map "Dusty Rose" -> "Pink", "Ocean Breeze" -> "Blue").
3. **One row per variant, unique key = product_id + color_code.** Enforce this at the data model level. Use Airtable's upsert with this composite key to prevent duplicates.
4. **Test with products that have many variants.** Don't test with products that have 2 colors. Find COS products with 5+ color options and verify all are captured.

**Detection:** Count of variants per product is always 1. Color field has duplicates like "undefined" or empty strings. Airtable record count is suspiciously close to product count (should be higher due to variants).

**Confidence:** HIGH -- fashion variant extraction challenges are well-documented across Scrapfly, eScraper, PromptCloud, and DataWeave case studies.

**Phase mapping:** Core to Phase 1. The data model (one row per variant) must be designed before any extraction code is written.

---

### Pitfall 3: Airtable Hits Hard Limits and Breaks the Pipeline

**What goes wrong:** The pipeline silently stops inserting records when:
- The 5 requests/second rate limit is hit, causing 429 errors that cascade into data loss
- The 50,000 records/base limit (Team plan) is reached and new writes fail
- The 1,000 API calls/month limit (Free plan) is exhausted in the first few runs
- Batch operations exceed the 10-records-per-request limit

**Why it happens:** Airtable's limits are surprisingly low for an automated pipeline:
- **5 requests/second per base** -- a single scrape run of 500 products with 3 variants each = 1,500 records. At 10 records per batch = 150 API calls. That is fine for a single run, but add reads, updates, and GPT scoring writes and it compounds fast.
- **50,000 records/base on Team plan** -- COS menswear alone might be 500-1000 products x 3 variants = 1,500-3,000 records per scrape. If you store historical data (price tracking over time), you hit 50K within months. Adding SSENSE and Farfetch accelerates this dramatically.
- **429 errors trigger a 30-second lockout** -- if your retry logic is aggressive, you can spiral into a lockout loop.
- As of January 2025, Airtable reduced Free plan API calls from unlimited to 1,000/month, breaking many existing integrations overnight.

**Consequences:**
- Partial data loads (some products written, others lost)
- Non-idempotent runs create duplicate records
- Client sees "incomplete" data and doesn't know why
- Upgrading from Team ($20/user/mo) to Business ($45/user/mo) just for the 125K record limit is a painful cost jump

**Prevention:**
1. **Use batch upsert from day one.** Airtable's `performUpsert` endpoint finds, creates, or updates records in a single call. Batch 10 records per request. This is both faster and idempotent.
2. **Implement exponential backoff with jitter.** On 429, wait 30 seconds + random jitter. Cap at 5 retries. Log every 429 for monitoring.
3. **Design for the record limit from the start.** Decide: are you storing snapshots (current state only, upsert to replace) or time series (historical, append)? For time series, plan a data archival strategy (move old records to a separate base or external DB). For current-state, upsert keeps record count stable.
4. **Calculate your record budget.** COS: ~2,000 records. SSENSE: ~5,000? Farfetch: ~50,000+? If you plan to add Farfetch, you will exceed the Team plan limit. Plan for this now, not when it breaks.
5. **Batch writes with a queue.** Don't fire API calls as fast as extraction completes. Queue writes and drain at a controlled rate (4 req/sec to leave headroom).

**Detection:** 429 errors in logs. Record counts plateau at exactly 50,000. Airtable API call counter approaching monthly limit (visible in Airtable dashboard). Products appearing in scrape output but missing from Airtable.

**Confidence:** HIGH -- rate limits verified via Airtable's official API documentation and multiple community reports.

**Phase mapping:** Architecture decision needed in Phase 1 (snapshot vs. time series). Rate limiting and upsert logic are Phase 2 (pipeline integration). Record limit planning is pre-Phase 1.

---

### Pitfall 4: Cookie Consent Banners Block Content Extraction

**What goes wrong:** European cookie consent banners (mandatory under GDPR) overlay the page and prevent scraping. Common failures:
- The banner uses a "lock" mechanism that prevents the actual content from scrolling or rendering until consent is given
- Clicking "Accept" triggers a page reload that resets scraper state
- The banner DOM overlays product elements, causing click interception failures
- Cookie modal adds 200-500 tokens of junk text to any text extraction
- Different COS country stores show different consent implementations

**Why it happens:** COS is an H&M Group brand headquartered in Europe. Their cookie consent implementation is likely aggressive and well-maintained (EU regulators actively enforce GDPR cookie requirements). The consent dialog may:
- Load asynchronously after the initial page render
- Use a shadow DOM or iframe that standard selectors can't penetrate
- Require accepting all/specific cookie categories before product data is interactive
- Persist state via cookies, meaning a fresh browser context sees it on every page

**Consequences:**
- Scraper hangs waiting for elements that are behind the consent overlay
- Extracted data is polluted with consent banner text
- Inconsistent behavior between runs (cached consent vs. fresh browser)

**Prevention:**
1. **Use Ghostery's adblocker for Playwright.** Apify's own team found this is the most reliable approach as of 2025/2026, after the "I don't care about cookies" extension became unmaintained (last update November 2023). Ghostery has out-of-box Playwright support and is actively maintained.
2. **Pre-set consent cookies.** Instead of clicking the banner, inject the consent cookies directly into the browser context before navigation. Inspect what cookies COS sets after clicking "Accept All" and replay them. This is faster and more reliable than UI interaction.
3. **Handle it in `preNavigationHook`.** In Crawlee, use the pre-navigation hook to inject cookies or CSS that hides the banner before any page interaction.
4. **Test with a fresh browser context every time.** Don't assume cookie persistence. Apify actors start fresh on each run by default -- verify this is actually happening.

**Detection:** Scraper timeouts on first page. Extracted text contains "We use cookies" or "Accept all". Product elements report as "not visible" or "intercepted by another element".

**Confidence:** HIGH -- verified through Apify's official blog post on blocking cookie modals, which documents their own trial-and-error with this exact problem.

**Phase mapping:** Must be solved in Phase 1 before any reliable extraction can happen. This is a blocker, not an enhancement.

---

### Pitfall 5: Bot Detection Blocks Scraper Without Clear Error

**What goes wrong:** COS/H&M Group sites serve a CAPTCHA page, a blank page, or a "403 Forbidden" response instead of product data. The scraper may not detect this and processes the error page as if it were a product page, extracting zero products with no error thrown.

**Why it happens:** H&M Group sites use enterprise-grade bot protection. While the specific provider for COS was not directly confirmed in research, the common stack for major fashion retailers includes:
- **Akamai Bot Manager** (confirmed used by Farfetch)
- **Cloudflare** (confirmed used by SSENSE)
- **PerimeterX/HUMAN** (common in fashion ecommerce)

These systems detect automation via:
- `navigator.webdriver` property (Playwright sets this to `true` by default)
- TLS/JA3 fingerprinting (Playwright's TLS handshake differs from real Chrome)
- Behavioral analysis (no mouse movements, instant page loads, sequential navigation patterns)
- IP reputation (Apify's datacenter IPs are known scraping infrastructure)

**Consequences:**
- Intermittent failures that are hard to reproduce
- Complete pipeline failure if bot detection is aggressive
- IP bans that affect other Apify actors sharing the same IP pool
- Escalation: sites may increase protection after detecting scraping attempts

**Prevention:**
1. **Use `playwright-extra` with the stealth plugin.** This is the baseline -- patches `navigator.webdriver`, simulates plugins, fixes WebGL metadata. Install via `puppeteer-extra-plugin-stealth` (compatible with Playwright via `playwright-extra`).
2. **Use residential proxies, not datacenter.** Apify offers residential proxy tiers. Datacenter IPs get blocked quickly by sophisticated bot protection. Budget for this cost.
3. **Add human-like behavior.** Random delays between page loads (2-8 seconds, not fixed intervals). Random mouse movements. Don't navigate pages in alphabetical/sequential order. Visit non-product pages occasionally.
4. **Try Firefox over Chromium.** Crawlee supports Firefox, and it is less commonly used for scraping, making its fingerprint less suspicious. Apify's own documentation recommends this.
5. **Implement request pacing.** Never hit more than 1 page per 3-5 seconds. Spread scraping across hours, not minutes. A 500-product catalog can be scraped in 30-40 minutes with 3-second delays -- there is no reason to rush.
6. **Detect blocked responses.** After every page load, check: Does the page contain expected product elements? Is the response status 200? Is the page content length above a minimum threshold? If not, the page was blocked -- retry with backoff, don't process the empty page.

**Detection:** Sudden drop in extracted product count. Response bodies shorter than 10KB. HTML contains "Access Denied", "Please verify", or CAPTCHA iframe. Scrape run completes in suspiciously short time.

**Confidence:** MEDIUM -- bot detection methods are well-documented across multiple sources, but COS's specific anti-bot provider was not confirmed. The protection level could be lighter than assumed (some H&M Group brands are more permissive) or heavier.

**Phase mapping:** Must be addressed in Phase 1. Stealth setup and proxy configuration are prerequisites for any reliable scraping. Test bot detection tolerance early before building the rest of the pipeline.

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or recurring maintenance burden.

---

### Pitfall 6: Geolocation Redirects Serve Wrong Country/Currency

**What goes wrong:** COS operates in 38+ countries. When the scraper accesses `cos.com`, it gets redirected to the wrong country store based on the Apify server's IP location. Prices appear in euros instead of expected currency. Product availability differs. Some products are region-exclusive and don't appear.

**Why it happens:** H&M Group sites use geolocation to redirect users to their local store. Apify's servers may be in a different region than the target market. The country selector on COS uses cookies/session state that isn't being set correctly.

**Prevention:**
1. **Use the explicit country URL** (e.g., `cos.com/en-gb/` for UK) rather than the root domain.
2. **Set geolocation headers and cookies** before navigation. Inspect what COS sets for country preference and inject those.
3. **Use Apify proxy with a specific country** (`RESIDENTIAL` group with country code) to match the target market.
4. **Validate currency in extracted data.** Assert that all prices are in the expected currency before pushing to Airtable.

**Detection:** Prices are in unexpected currency. Product catalog size differs from expected. URL redirects visible in navigation logs.

**Confidence:** MEDIUM -- COS's specific geolocation behavior was not directly tested, but this is standard for H&M Group international sites.

**Phase mapping:** Phase 1 configuration. Set the target country/locale before building extraction logic.

---

### Pitfall 7: Non-Idempotent Pipeline Creates Duplicate Records

**What goes wrong:** The scraper runs twice (manual re-run, scheduler overlap, retry after partial failure) and creates duplicate records in Airtable. The client sees the same product listed 2-3 times. GPT-4o scoring runs on duplicates, wasting API credits.

**Why it happens:**
- Using Airtable's "create" endpoint instead of "upsert"
- No unique key defined for products (or key doesn't include color variant)
- Scheduler fires a new run before the previous one completes
- Partial failures leave the pipeline in an inconsistent state -- some records written, scraper retries from the beginning

**Prevention:**
1. **Always use upsert with a composite key.** Key = `product_id` + `color_code` (or `sku` if available). This makes every run idempotent.
2. **Track run state.** Store the current run's status (running/complete/failed) and prevent concurrent runs.
3. **Use Apify's dataset deduplication.** Write to an Apify dataset first (serves as staging), deduplicate, then push to Airtable.
4. **Log every Airtable write** with the operation type (created vs. updated) for audit trail.

**Detection:** Record count in Airtable exceeds expected product count. Same `product_id` appears in multiple rows with identical data. Airtable's "Created Time" shows clusters of exact same timestamps.

**Confidence:** HIGH -- idempotency failures are a universally documented data pipeline problem, verified across multiple engineering sources.

**Phase mapping:** Must be designed into Phase 1 data model. The upsert key strategy must be decided before writing Airtable integration.

---

### Pitfall 8: GPT-4o Scoring Costs Spiral Without Controls

**What goes wrong:** GPT-4o scoring runs on every product/variant on every scrape run, even when the product hasn't changed. At $2.50/M input + $10.00/M output tokens, costs grow linearly with product count and run frequency. Adding SSENSE and Farfetch could 5-10x the catalog size.

**Why it happens:**
- No change detection -- scoring re-runs on unchanged products
- Prompts are too long (sending full product descriptions when only key attributes matter)
- No caching of previous scores
- Each variant scored independently when the scoring criteria may be identical across colors of the same product

**Prevention:**
1. **Only score new or changed products.** Hash the product data. If the hash matches the previous run, skip scoring and reuse the cached score.
2. **Score at the product level, not variant level.** If scoring is about design/style, it is the same across color variants. Score once, apply to all variants.
3. **Use GPT-4o-mini for initial filtering.** At $0.15/M input tokens (16x cheaper), use mini to do a first pass, then GPT-4o only for products that pass the filter.
4. **Use the Batch API for 50% discount.** Product scoring is not time-sensitive. Submit via OpenAI's Batch API and wait up to 24 hours for results.
5. **Set a cost ceiling.** Calculate expected cost per run: (products x avg tokens x price per token). Set an alert if actual cost exceeds 2x expected.

**Detection:** OpenAI bill increasing month over month. Scoring run duration growing linearly with catalog. Same products receiving identical scores run after run.

**Confidence:** HIGH -- GPT-4o pricing verified via OpenAI's official pricing page (current as of 2026). Batch API 50% discount confirmed.

**Phase mapping:** Change detection and caching belong in Phase 2 or 3 (optimization). But the cost model should be calculated in Phase 1 planning to set expectations.

---

### Pitfall 9: Multi-Retailer Expansion Requires Near-Complete Rewrite

**What goes wrong:** The scraper is built tightly coupled to COS's specific DOM structure, URL patterns, and data format. When adding SSENSE (Cloudflare-protected, different product structure) or Farfetch (Akamai-protected, marketplace with multiple sellers per product), none of the extraction code is reusable. Each retailer requires a from-scratch implementation.

**Why it happens:**
- Selectors, URL patterns, and data schemas are hardcoded for COS
- No abstraction layer between "site-specific extraction" and "common pipeline"
- Different retailers use different anti-bot providers (Cloudflare vs. Akamai vs. PerimeterX) requiring different stealth strategies
- Product data schemas differ fundamentally (COS: single-brand, fixed prices; Farfetch: marketplace, multiple sellers, varied pricing)

**Prevention:**
1. **Design a retailer adapter interface from the start.** Even with only COS initially, structure the code as: `RetailerAdapter` (site-specific: selectors, URLs, parsing) -> `NormalizedProduct` (common schema) -> `Pipeline` (Airtable, GPT scoring). The COS adapter is the first implementation.
2. **Define a normalized product schema.** All retailers must map to the same output: `{ product_id, retailer, name, price, currency, color_normalized, color_original, url, image_url, ... }`. This schema becomes your contract.
3. **Isolate proxy/stealth configuration per retailer.** SSENSE needs Cloudflare bypass; Farfetch needs Akamai bypass. Don't bake one approach into the core.
4. **Document COS-specific assumptions.** Every time you write COS-specific code, add a comment: `// COS-SPECIFIC: [what and why]`. This becomes the checklist for new retailer adapters.

**Detection:** Adding a second retailer requires touching >50% of existing code. "Common" functions have COS-specific logic buried inside. Farfetch products don't fit the existing data model.

**Confidence:** HIGH -- multi-retailer scraper architecture is a well-documented pattern in the scraping industry.

**Phase mapping:** The adapter abstraction should be designed (not necessarily implemented) in Phase 1. It costs almost nothing to put extraction behind an interface, but costs a rewrite to add it later.

---

### Pitfall 10: Apify Actor Memory/Timeout Limits Cause Incomplete Runs

**What goes wrong:** The Apify actor runs out of memory (Playwright browsers are RAM-hungry) or hits the timeout limit mid-scrape. The run terminates with a partial dataset. If the pipeline doesn't detect this, it pushes incomplete data to Airtable, or worse, the upsert logic marks missing products as "deleted."

**Why it happens:**
- Playwright requires minimum 1,024 MB memory per Apify's documentation. Complex sites like COS may need 2,048-4,096 MB.
- Default build timeout is 1,800 seconds (30 minutes). A full catalog scrape with 3-5 second delays between pages for 500+ products = 25-40 minutes, dangerously close to the limit.
- Memory leaks from unclosed browser contexts accumulate over long runs.
- Apify Free plan limits total concurrent memory to 8,192 MB. Running other actors in parallel reduces available memory.

**Prevention:**
1. **Allocate 2,048-4,096 MB for Playwright actors.** Don't try to run lean at 1,024 MB -- you will hit OOM on complex pages.
2. **Process in batches, not all at once.** Scrape in chunks of 50-100 products. Save progress to Apify's key-value store after each chunk. On restart, resume from the last checkpoint.
3. **Close browser contexts aggressively.** Don't keep multiple pages open. Open page -> extract -> close page -> next.
4. **Set the actor timeout to at least 2x your expected runtime.** If you expect 30 minutes, set to 60 minutes.
5. **Validate completeness after run.** Compare the count of scraped products against the expected catalog size (scrape the category page count first). If the scrape returned significantly fewer products, flag as incomplete.

**Detection:** Actor run status is "TIMED-OUT" or "FAILED" in Apify console. Memory usage graph shows a steady climb without plateauing (memory leak). Product count is significantly lower than previous runs.

**Confidence:** HIGH -- Apify platform limits verified via official documentation (docs.apify.com/platform/limits). Memory requirements for Playwright confirmed.

**Phase mapping:** Phase 1 infrastructure setup. Memory allocation and batching must be configured from the first working scraper.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable without major rework.

---

### Pitfall 11: Price Extraction Gets Wrong Format/Currency

**What goes wrong:** Prices are extracted as strings with locale-specific formatting and converted incorrectly. "1.234,56" (European format for one-thousand-two-hundred-thirty-four and 56 cents) is parsed as "1234.56" or "1.23456" depending on naive parsing logic. VAT-inclusive vs. exclusive prices are mixed.

**Prevention:**
1. **Always extract raw price data from structured sources** (JSON-LD, API responses) where prices are numeric, not display strings.
2. **If parsing display prices, detect the locale first** and use locale-aware parsing. COS UK uses "GBP 89.00"; COS EU might use "89,00 EUR".
3. **Store both the raw extracted price string and the parsed numeric value** for debugging.
4. **Assert currency consistency** within a single scrape run.

**Confidence:** HIGH -- well-documented problem across ecommerce scraping literature.

**Phase mapping:** Phase 1. Build into the extraction logic from the start.

---

### Pitfall 12: Apify Scheduling Overlap and Timezone Confusion

**What goes wrong:** The Apify scheduler fires a new run while the previous run is still in progress. Two actors compete for the same Airtable base, causing race conditions and 429 errors. Alternatively, the schedule is set in UTC but the client expects runs aligned to their local timezone, causing confusion about data freshness.

**Prevention:**
1. **Use Apify's run locking** -- check if a previous run is still active before starting a new one. If it is, skip or queue.
2. **Document the schedule in the client's local timezone** and implement in UTC with the offset clearly noted.
3. **Set run frequency based on actual data change frequency.** COS doesn't update prices hourly. Daily or twice-daily is sufficient for most fashion product monitoring.

**Confidence:** MEDIUM -- general scheduling pitfall, not COS-specific.

**Phase mapping:** Phase 2 (automation/scheduling).

---

### Pitfall 13: Non-Technical Client Cannot Debug or Modify the System

**What goes wrong:** The scraper breaks (site redesign, new bot protection, Airtable limit hit) and the non-technical client cannot diagnose or fix the issue. They see "no new data" in Airtable and don't know if the scraper failed, the site changed, or Airtable is full. The system becomes a black box that requires developer intervention for every issue.

**Prevention:**
1. **Build a status dashboard in Airtable.** A separate table showing: last run time, products scraped, errors encountered, next scheduled run. The client checks one table to see system health.
2. **Send email/Slack notifications on failure.** Apify supports webhooks. On actor failure or validation check failure, notify the client with a plain-English message ("COS scraper failed: site may have changed. No action needed if this resolves within 24 hours. Contact developer if it persists.").
3. **Document the "what to do when" runbook.** A simple document: "If you see X, do Y. If you see Z, contact the developer." Keep it to one page.
4. **Make the Apify console accessible** but read-only for the client. They can see run history, logs, and datasets without accidentally breaking anything.

**Confidence:** HIGH -- this is a known challenge for any automated system maintained by non-technical users.

**Phase mapping:** Phase 3 (handoff/operations). But the monitoring hooks should be designed in Phase 1.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Severity |
|-------------|---------------|------------|----------|
| **Core scraper build** | Cookie banner blocks all extraction | Solve consent handling first with Ghostery adblocker or pre-set cookies | Critical |
| **Core scraper build** | Bot detection returns empty pages | Implement stealth plugin + residential proxies from day one | Critical |
| **Core scraper build** | Selectors break on first COS deploy | Extract from JSON/API sources, not DOM selectors | Critical |
| **Color variant extraction** | Only default color scraped | Inspect network requests for variant data API; don't rely on UI clicks | Critical |
| **Data model design** | Non-idempotent writes create duplicates | Use upsert with composite key (product_id + color_code) from day one | Critical |
| **Airtable integration** | Rate limiting causes partial writes | Batch upsert (10 records/request) with exponential backoff | Moderate |
| **Airtable integration** | Record limit hit when adding retailers | Plan record budget upfront; design for snapshot mode (upsert, not append) | Moderate |
| **GPT-4o scoring** | Costs spiral with catalog growth | Score per product (not per variant); cache scores; use Batch API | Moderate |
| **Multi-retailer expansion** | COS-specific code blocks reuse | Design adapter interface before building COS-specific extraction | Moderate |
| **Scheduling/automation** | Overlapping runs cause race conditions | Implement run locking; set appropriate frequency | Minor |
| **Client handoff** | Black box system client cannot debug | Build status table in Airtable; send failure notifications | Moderate |
| **Geolocation** | Wrong country/currency data scraped | Pin country URL and validate currency in every extraction | Minor |

---

## Decision Points That Prevent Multiple Pitfalls

These decisions, made early, prevent cascading problems:

### Decision 1: Snapshot vs. Time Series Data Model
- **Snapshot** (upsert, replace current state): Keeps record count stable, simpler, fits Airtable limits. Prevents Pitfalls 3, 7.
- **Time Series** (append, track historical prices): Record count grows unboundedly, will exceed Airtable limits. Requires archival strategy.
- **Recommendation:** Start with snapshot. If historical tracking is needed, store history in a separate system (Google Sheets, a simple database) and keep Airtable as the "current state" view.

### Decision 2: Extract from API/JSON vs. DOM
- **API/JSON**: More resilient to redesigns, structured data, easier parsing. Prevents Pitfalls 1, 2, 11.
- **DOM selectors**: Fragile, locale-dependent, requires handling of dynamic rendering.
- **Recommendation:** Invest time upfront to find COS's internal API endpoints or embedded JSON data. This single decision eliminates or mitigates 3 critical pitfalls.

### Decision 3: Proxy Strategy
- **Datacenter proxies**: Cheap, fast, easily blocked.
- **Residential proxies**: Expensive ($5-15/GB), reliable for fashion sites with bot protection.
- **Recommendation:** Budget for residential proxies from the start. Prevents Pitfall 5. The cost of a few dollars per scrape run is far less than the cost of debugging intermittent blocking issues.

---

## Sources

### Official Documentation (HIGH confidence)
- [Airtable Rate Limits](https://airtable.com/developers/web/api/rate-limits)
- [Apify Platform Limits](https://docs.apify.com/platform/limits)
- [Apify Anti-Scraping Academy](https://docs.apify.com/academy/anti-scraping)
- [Apify Usage and Resources](https://docs.apify.com/platform/actors/running/usage-and-resources)
- [Crawlee Playwright Stealth Plugin](https://crawlee.dev/js/docs/3.11/examples/crawler-plugins)
- [OpenAI API Pricing](https://openai.com/api/pricing/)

### Verified Blog Posts (MEDIUM confidence)
- [Apify: How We Stopped Cookie Modals From Polluting Scraped Data](https://blog.apify.com/how-to-block-cookie-modals/)
- [Apify: How to Scrape the Web with Playwright](https://blog.apify.com/playwright-web-scraping/)
- [DataWeave: Normalizing Size and Color in Fashion](https://dataweave.com/blog/normalizing-size-and-color-in-fashion-using-ai-to-power-competitive-price-intelligence)
- [Airtable: When Your Growing Business Hits the 50,000 Record Wall](https://servalian.com/blog/airtable-record-limits)
- [Scrapfly: How to Scrape in Another Language or Currency](https://scrapfly.io/blog/posts/how-to-scrape-in-another-language-or-currency)
- [How to Build an E-Commerce Scraper That Survives a Website Redesign](https://medium.com/@hasdata/how-to-build-an-e-commerce-scraper-that-survives-a-website-redesign-86216e96cbd9)

### Community Sources (LOW confidence -- patterns observed but not officially verified)
- [ScrapeOps: SSENSE Anti-Bots](https://scrapeops.io/websites/ssense.com/antibots) -- SSENSE uses Cloudflare
- [Crawlbase: How to Scrape Retail Data from Farfetch](https://crawlbase.com/blog/how-to-scrape-retail-data-from-farfetch/) -- Farfetch uses Akamai
- [eScraper: Fashion Websites Scraping Challenges](https://e-scraper.com/useful-articles/fashion-websites-scraping/)
- [Medium: Web Scraping Monitoring - The Silent Data Quality Crisis](https://medium.com/@arman-bd/web-scraping-monitoring-the-silent-data-quality-crisis-no-one-talks-about-9949a2b5a361)
- [DEV: Stop Silent Failures Using LLMs to Validate Scraper Output](https://dev.to/anderecit/stop-silent-failures-using-llms-to-validate-web-scraper-output-24gf)
