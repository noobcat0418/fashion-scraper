# Architecture Patterns

**Domain:** Automated fashion product scraping pipeline (COS menswear, extensible to SSENSE/Farfetch)
**Researched:** 2026-03-02
**Confidence:** MEDIUM-HIGH (Crawlee/Apify patterns verified via official docs; adapter pattern synthesized from multiple verified sources)

## Recommended Architecture

The system is a **multi-stage data pipeline** with a **retailer adapter pattern** running on Apify Cloud. Each stage has a single responsibility and communicates through well-defined data contracts.

```
[Apify Scheduler]
       |
       v
[Actor Entry Point]  <-- reads Actor Input (retailer, config)
       |
       v
[Retailer Adapter]   <-- site-specific: selectors, navigation, cookie handling
       |
       v
[Crawlee PlaywrightCrawler + Router]
       |  (raw scraped data per product page)
       v
[Normalizer Pipeline]  <-- color mapping, price normalization, material extraction
       |  (one normalized row per color variant)
       v
[Crawlee Dataset]  <-- append-only structured storage (local or Apify cloud)
       |
       v
[Airtable Sync]  <-- upsert rows to Airtable via REST API
       |
       v
[GPT-4o Scoring]  <-- reads scoring config from Airtable, scores each product
       |
       v
[Airtable Update]  <-- writes scores back to product rows
```

### Component Boundaries

| Component | Responsibility | Communicates With | Build Phase |
|-----------|---------------|-------------------|-------------|
| **Actor Entry Point** (`src/main.ts`) | Bootstrap actor, read input, select retailer adapter, launch crawler | Retailer Adapter, Crawlee Crawler | Phase 1 |
| **Retailer Adapter** (`src/retailers/{name}/`) | Site-specific selectors, URL patterns, cookie consent, page navigation | Router Handlers, Normalizer | Phase 1 (COS), Phase 4+ (others) |
| **Router Handlers** (`src/routes.ts` or per-retailer) | Label-based request routing: LISTING pages vs DETAIL pages | Crawler, Retailer Adapter | Phase 1 |
| **Cookie Handler** (`src/utils/cookie-consent.ts`) | Dismiss cookie/consent banners before extraction | Crawler (preNavigationHook) | Phase 1 |
| **Normalizer Pipeline** (`src/normalizers/`) | Transform raw scraped data into canonical schema: color mapping, price parsing, material extraction, variant explosion | Router Handlers (input), Dataset (output) | Phase 2 |
| **Canonical Schema** (`src/types/product.ts`) | TypeScript interfaces defining the normalized product shape | All components | Phase 1 |
| **Crawlee Dataset** (built-in) | Append-only storage for normalized product rows | Normalizer (input), Airtable Sync (output) | Phase 1 (automatic) |
| **Airtable Sync** (`src/integrations/airtable.ts`) | Batch upsert product rows to Airtable, handle rate limits (5 req/s) | Dataset (input), Airtable API | Phase 2 |
| **GPT-4o Scorer** (`src/integrations/scorer.ts`) | Read scoring config from Airtable, call OpenAI API, write scores back | Airtable (config + output), OpenAI API | Phase 3 |
| **Shared Utilities** (`src/utils/`) | Logging, retry helpers, rate limiter, error formatting | All components | Phase 1 |

### Data Flow

**Stage 1: Crawl** -- The Actor reads input (which retailer, what category URLs). The retailer adapter provides site-specific configuration to the Crawlee PlaywrightCrawler. The Router dispatches requests by label: `LISTING` pages get scraped for product URLs which are enqueued with label `DETAIL`. `DETAIL` pages get fully extracted.

**Stage 2: Normalize** -- Raw extracted data (retailer-specific field names, inconsistent color names, prices with currency symbols) passes through the normalizer pipeline. Each raw product is expanded into N rows (one per color variant) with canonical field names, normalized colors, and parsed prices.

**Stage 3: Store** -- Normalized rows are pushed to the Crawlee Dataset via `Dataset.pushData()`. This is append-only and stored as individual JSON files locally or in Apify cloud storage automatically.

**Stage 4: Sync** -- After crawling completes (or in batches during crawl), the Airtable sync module reads from the dataset and upserts records to Airtable. Upsert uses a composite key (retailer + product ID + color variant) for deduplication.

**Stage 5: Score** -- A separate Actor run (or a post-crawl hook) reads unscored products from Airtable, fetches the scoring config (criteria, weights) from a separate Airtable table, calls GPT-4o with structured output, and writes scores back.

## Recommended Project Structure

```
fashion-scraper/
  .actor/
    actor.json              # Apify actor definition
    input_schema.json       # Input schema for Actor
  src/
    main.ts                 # Actor entry point: init, select adapter, run crawler
    routes.ts               # Crawlee Router: default handler + labeled handlers
    types/
      product.ts            # Canonical product schema (TypeScript interfaces)
      input.ts              # Actor input types
      retailer.ts           # RetailerAdapter interface
    retailers/
      cos/
        adapter.ts          # COS-specific: base URLs, selectors, cookie handling
        extractors.ts       # COS-specific extraction logic (page -> raw data)
        config.ts           # COS URLs, category mappings
      ssense/               # Future: same structure
        adapter.ts
        extractors.ts
        config.ts
    normalizers/
      index.ts              # Pipeline orchestrator: runs all normalizers in sequence
      color.ts              # Color name -> canonical color mapping
      price.ts              # Price string -> { amount, currency } parsing
      materials.ts          # Material string extraction and categorization
      variants.ts           # Explode one product into N color-variant rows
    integrations/
      airtable.ts           # Airtable client: batch upsert, rate limiting, field mapping
      openai.ts             # OpenAI client: GPT-4o scoring with structured output
    utils/
      cookie-consent.ts     # Generic cookie banner dismissal
      logger.ts             # Crawlee log wrapper
      retry.ts              # Retry/backoff utilities
  storage/                  # Local Crawlee storage (gitignored)
  package.json
  tsconfig.json
  eslint.config.js
  .gitignore
```

**Confidence: HIGH** -- This structure follows the official Apify TypeScript Actor template pattern (src/main.ts + src/routes.ts) verified via Apify documentation, extended with domain-specific directories. The retailer adapter pattern is synthesized from multiple verified scraper architectures.

## Patterns to Follow

### Pattern 1: Retailer Adapter Interface

**What:** Define a common interface that all retailer-specific modules implement. The adapter encapsulates everything site-specific: base URLs, CSS/XPath selectors, cookie consent strategy, pagination logic, and raw data extraction.

**When:** Any time you add a new retailer. The adapter is the ONLY place site-specific logic lives.

**Why:** COS, SSENSE, and Farfetch have completely different DOM structures, URL patterns, and anti-bot measures. Without a clean boundary, site-specific logic leaks everywhere and adding a new retailer means touching dozens of files.

**Example:**
```typescript
// src/types/retailer.ts
import { PlaywrightCrawlingContext } from 'crawlee';

export interface RetailerConfig {
  name: string;                    // 'cos' | 'ssense' | 'farfetch'
  baseUrl: string;                 // 'https://www.cos.com'
  startUrls: string[];             // Category listing URLs to begin crawl
  maxRequestsPerCrawl?: number;    // Safety limit
}

export interface RetailerAdapter {
  config: RetailerConfig;

  // Cookie/consent banner dismissal for this site
  handleConsent(context: PlaywrightCrawlingContext): Promise<void>;

  // Given a listing page, extract product URLs
  extractProductUrls(context: PlaywrightCrawlingContext): Promise<string[]>;

  // Given a product detail page, extract raw product data
  extractProduct(context: PlaywrightCrawlingContext): Promise<RawProduct>;

  // Determine if a URL is a listing page or detail page
  classifyUrl(url: string): 'LISTING' | 'DETAIL' | 'UNKNOWN';

  // Optional: handle pagination on listing pages
  getNextPageUrl?(context: PlaywrightCrawlingContext): Promise<string | null>;
}

export interface RawProduct {
  retailer: string;
  productId: string;
  url: string;
  name: string;
  priceRaw: string;              // e.g., "GBP 89.00" -- not yet normalized
  category: string;
  materialsRaw: string;          // e.g., "100% organic cotton" -- not yet parsed
  fitDescription?: string;
  colorVariants: RawColorVariant[];
  imageUrls: string[];
  scrapedAt: string;             // ISO timestamp
}

export interface RawColorVariant {
  colorNameRaw: string;          // e.g., "DUSTY ROSE" -- not yet normalized
  colorSwatchUrl?: string;
  imageUrls: string[];
  available: boolean;
}
```

**Confidence: HIGH** -- This is a well-established adapter pattern. The interface shape is informed by COS's actual product page structure (H&M Group sites use __NEXT_DATA__ JSON, verified via multiple sources) and common fashion e-commerce data fields.

### Pattern 2: Crawlee Router with Labels

**What:** Use Crawlee's built-in Router class to dispatch requests to different handlers based on labels. Label requests as `LISTING` or `DETAIL` when enqueuing them.

**When:** Always. This is Crawlee's recommended way to handle multiple page types.

**Why:** Avoids monolithic if/else blocks in a single requestHandler. Each page type gets its own clean handler function. Crawlee's Router is specifically designed for this.

**Example:**
```typescript
// src/routes.ts
import { createPlaywrightRouter, Dataset } from 'crawlee';
import { RetailerAdapter } from './types/retailer.js';
import { normalizeProduct } from './normalizers/index.js';

export function createRouter(adapter: RetailerAdapter) {
  const router = createPlaywrightRouter();

  // Listing pages: extract product URLs and enqueue them as DETAIL
  router.addHandler('LISTING', async (context) => {
    const { page, enqueueLinks, log } = context;
    await adapter.handleConsent(context);

    const productUrls = await adapter.extractProductUrls(context);
    log.info(`Found ${productUrls.length} products on listing page`);

    await enqueueLinks({
      urls: productUrls,
      label: 'DETAIL',
    });

    // Handle pagination
    const nextPage = await adapter.getNextPageUrl?.(context);
    if (nextPage) {
      await enqueueLinks({ urls: [nextPage], label: 'LISTING' });
    }
  });

  // Detail pages: extract product data, normalize, push to dataset
  router.addHandler('DETAIL', async (context) => {
    const { log } = context;
    await adapter.handleConsent(context);

    const rawProduct = await adapter.extractProduct(context);
    const normalizedRows = normalizeProduct(rawProduct);

    log.info(`Extracted ${normalizedRows.length} variants for ${rawProduct.name}`);
    await Dataset.pushData(normalizedRows);
  });

  return router;
}
```

**Confidence: HIGH** -- Verified via official Crawlee documentation. The Router class, `addHandler` with labels, and `enqueueLinks` with labels are all documented patterns.

### Pattern 3: Normalizer Pipeline (Transform Chain)

**What:** A sequence of pure transformation functions that convert raw scraped data into the canonical schema. Each normalizer handles one concern (color, price, materials, variant explosion).

**When:** After raw extraction, before pushing to dataset.

**Why:** Keeps extraction logic (site-specific, fragile) separate from normalization logic (reusable, testable). Normalizers are shared across all retailers. You can unit test each normalizer independently.

**Example:**
```typescript
// src/normalizers/index.ts
import { RawProduct } from '../types/retailer.js';
import { NormalizedProductRow } from '../types/product.js';
import { normalizeColor } from './color.js';
import { parsePrice } from './price.js';
import { parseMaterials } from './materials.js';

export function normalizeProduct(raw: RawProduct): NormalizedProductRow[] {
  const price = parsePrice(raw.priceRaw);
  const materials = parseMaterials(raw.materialsRaw);

  // Explode into one row per color variant
  return raw.colorVariants.map((variant) => ({
    retailer: raw.retailer,
    productId: raw.productId,
    url: raw.url,
    name: raw.name,
    category: raw.category,
    priceAmount: price.amount,
    priceCurrency: price.currency,
    materials,
    fitDescription: raw.fitDescription ?? null,
    colorOriginal: variant.colorNameRaw,
    colorNormalized: normalizeColor(variant.colorNameRaw),
    imageUrls: variant.imageUrls,
    available: variant.available,
    scrapedAt: raw.scrapedAt,
    // Composite key for Airtable upsert
    variantKey: `${raw.retailer}-${raw.productId}-${normalizeColor(variant.colorNameRaw)}`,
  }));
}
```

**Confidence: HIGH** -- Pipeline/transform chain pattern is well-established. The variant explosion (one row per color) matches the stated requirement.

### Pattern 4: Airtable Batch Upsert with Rate Limiting

**What:** Batch writes to Airtable with built-in rate limiting (max 5 requests/second, max 10 records per batch create/update call) and retry logic.

**When:** After normalization, as the final sync step.

**Why:** Airtable API has hard rate limits (5 req/s per base). Without explicit rate limiting, the actor will get 429 errors. The official airtable.js library has built-in retry, but you still need to batch records (max 10 per call) and pace requests.

**Example:**
```typescript
// src/integrations/airtable.ts
import Airtable from 'airtable';

const BATCH_SIZE = 10;         // Airtable max records per create/update call
const DELAY_BETWEEN_BATCHES_MS = 250; // Stay well under 5 req/s limit

export async function upsertToAirtable(
  records: NormalizedProductRow[],
  config: { apiKey: string; baseId: string; tableName: string }
): Promise<void> {
  const base = new Airtable({ apiKey: config.apiKey }).base(config.baseId);
  const table = base(config.tableName);

  for (let i = 0; i < records.length; i += BATCH_SIZE) {
    const batch = records.slice(i, i + BATCH_SIZE);

    await table.create(
      batch.map((record) => ({ fields: mapToAirtableFields(record) })),
      { typecast: true }  // Let Airtable auto-convert field types
    );

    if (i + BATCH_SIZE < records.length) {
      await new Promise((resolve) => setTimeout(resolve, DELAY_BETWEEN_BATCHES_MS));
    }
  }
}
```

**Confidence: MEDIUM** -- Airtable rate limits (5 req/s, 10 records/batch) verified via official Airtable docs and multiple sources. The `typecast` option and batch create API are from the official airtable.js library. Upsert via the REST API requires the `performUpsert` option with a merge field -- needs validation during implementation.

### Pattern 5: GPT-4o Scoring as Separate Stage

**What:** Run GPT-4o scoring as a distinct post-crawl step, not inline with scraping. Read scoring criteria from an Airtable config table, process products in batches, write scores back.

**When:** After all products are synced to Airtable.

**Why:** Scoring is expensive ($2.50/1M input tokens for GPT-4o) and slow. Decoupling it from scraping means: (a) scraping failures don't affect scored products, (b) you can re-score without re-scraping, (c) scoring criteria changes don't require re-crawling, (d) you can use OpenAI's Batch API for 50% cost reduction on non-urgent scoring.

**Example:**
```typescript
// src/integrations/scorer.ts
import OpenAI from 'openai';

interface ScoringConfig {
  criteria: { name: string; weight: number; description: string }[];
  model: string;   // 'gpt-4o'
  maxTokens: number;
}

export async function scoreProduct(
  product: NormalizedProductRow,
  config: ScoringConfig,
  openai: OpenAI
): Promise<Record<string, number>> {
  const response = await openai.chat.completions.create({
    model: config.model,
    response_format: { type: 'json_object' },
    messages: [
      {
        role: 'system',
        content: `Score this fashion product on the following criteria.
Return JSON with a score (1-10) for each criterion.
Criteria: ${JSON.stringify(config.criteria)}`,
      },
      {
        role: 'user',
        content: `Product: ${product.name}
Category: ${product.category}
Materials: ${product.materials}
Price: ${product.priceAmount} ${product.priceCurrency}
Color: ${product.colorNormalized}
Fit: ${product.fitDescription ?? 'N/A'}`,
      },
    ],
    max_tokens: config.maxTokens,
  });

  return JSON.parse(response.choices[0].message.content ?? '{}');
}
```

**Confidence: MEDIUM** -- GPT-4o structured output via `response_format: { type: 'json_object' }` is verified via OpenAI docs. Exact pricing may have changed. The Batch API for cost reduction is a verified OpenAI feature but integration details need validation during implementation.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Request Handler

**What:** Putting all scraping logic (listing extraction, detail extraction, normalization, Airtable push) in a single `requestHandler` function.

**Why bad:** Becomes unmaintainable past 100 lines. Impossible to test individual concerns. Adding a new retailer means duplicating the entire handler. Error in normalization crashes the whole crawl.

**Instead:** Use the Router pattern with labeled handlers. Keep extraction, normalization, and sync as separate modules.

### Anti-Pattern 2: Inline Airtable Writes During Crawl

**What:** Calling the Airtable API inside each request handler as products are scraped.

**Why bad:** Airtable's 5 req/s rate limit will throttle your crawler. Network errors to Airtable will cause request retries in Crawlee, leading to duplicate scrape work. Crawling and syncing have different failure modes that should not be coupled.

**Instead:** Push to Crawlee Dataset during crawl (fast, local/cloud, no rate limits). Sync to Airtable as a batch operation after crawling completes or in periodic flushes.

### Anti-Pattern 3: Hardcoded Selectors in Router Handlers

**What:** Putting CSS selectors like `page.locator('.product-title')` directly in the route handler code.

**Why bad:** When COS redesigns their site (which happens), you hunt through handler logic to find selectors. When adding SSENSE, you cannot reuse the handler structure. Selectors and extraction logic are the most volatile part of a scraper.

**Instead:** All selectors live inside the RetailerAdapter. Router handlers call adapter methods. Changing selectors means editing one file per retailer.

### Anti-Pattern 4: No Canonical Schema (Direct Scrape-to-Airtable)

**What:** Extracting data in the shape Airtable expects and pushing it directly without an intermediate normalized representation.

**Why bad:** Airtable field names become hardcoded throughout scraper code. Adding a new retailer with different raw field names requires changing normalization AND Airtable mapping in the same place. Cannot unit test normalization without mocking Airtable.

**Instead:** Define a canonical TypeScript interface (`NormalizedProductRow`). Scrape -> Normalize to canonical -> Map canonical to Airtable fields. Three clean boundaries.

### Anti-Pattern 5: Single Actor for Everything

**What:** One Apify Actor that scrapes, normalizes, syncs to Airtable, AND scores with GPT-4o in a single run.

**Why bad:** GPT-4o scoring is slow and expensive. If scoring fails at product #47, you lose the work or have to re-scrape. Scoring criteria changes require re-running the entire pipeline. Memory and timeout constraints on Apify are tighter for long-running actors.

**Instead:** Two actors or two-phase execution: (1) Scrape + Normalize + Sync to Airtable, (2) Score from Airtable. Can be triggered sequentially via Apify webhooks or scheduling.

## Key Architecture Decisions

### Decision 1: Single Actor with Two Modes vs. Two Separate Actors

**Recommendation: Start with a single Actor, two execution modes.**

For the MVP, use one Actor with an input parameter `mode: 'scrape' | 'score'`. In `scrape` mode, it crawls and syncs to Airtable. In `score` mode, it reads from Airtable, scores, and writes back.

**Rationale:** Two actors means managing two deployments, two input schemas, and actor-to-actor communication. For a personal/small-team tool, this is unnecessary overhead. A single actor with mode switching keeps deployment simple while maintaining the architectural separation internally.

**When to split:** If scoring takes >10 minutes independently, or if you want to score on a different schedule than scraping, split into two actors.

### Decision 2: Apify Built-in Airtable Integration vs. Direct API

**Recommendation: Direct Airtable API via airtable.js library.**

The Apify platform has a built-in Airtable integration (CREATE/APPEND/OVERWRITE modes), but it only runs after the actor completes and has limited field mapping. For this project, we need:
- Upsert (not just create/append) to avoid duplicates
- Composite key deduplication (retailer + product ID + color)
- Bidirectional sync (read scoring config, write scores back)

The built-in integration cannot do upserts or read from Airtable, so direct API usage is required.

**Confidence: MEDIUM** -- The built-in integration limitations are based on the Apify Airtable docs which describe CREATE/APPEND/OVERWRITE modes without mentioning upsert. The airtable.js library's upsert capability needs verification during implementation.

### Decision 3: COS Data Extraction Strategy

**Recommendation: Target `__NEXT_DATA__` JSON first, fall back to DOM selectors.**

COS (part of H&M Group) uses a Next.js frontend. H&M Group sites are verified to embed product data in `<script id="__NEXT_DATA__">` tags as JSON. This is far more reliable than CSS selectors because:
- JSON structure is stable across redesigns (tied to data model, not visual layout)
- All product data (variants, prices, materials) is typically in one JSON blob
- No need to handle dynamic loading or lazy rendering

Fall back to Playwright DOM extraction only if `__NEXT_DATA__` is missing or restructured (newer Next.js App Router uses `self.__next_f.push()` instead).

**Confidence: MEDIUM** -- H&M Group's use of `__NEXT_DATA__` is verified by multiple scraping sources and the H&M Apify actor. COS specifically has not been verified -- it may use a newer Next.js version with RSC/Flight data format. This needs validation during Phase 1 implementation.

## Build Order (Dependencies)

The build order is determined by component dependencies. Each phase produces a working (if incomplete) system.

```
Phase 1: Foundation
  [Canonical Schema] --> no dependencies, define first
  [Actor Entry Point] --> depends on schema, adapter interface
  [COS Adapter (basic)] --> depends on adapter interface
  [Router + Handlers] --> depends on adapter
  [Cookie Handler] --> depends on Playwright context
  Result: Can scrape COS and output to local Crawlee Dataset (JSON files)

Phase 2: Data Pipeline
  [Normalizer Pipeline] --> depends on schema, raw product type
  [Color Mapping] --> standalone normalizer
  [Price Parser] --> standalone normalizer
  [Airtable Sync] --> depends on normalized schema, Airtable API
  Result: Scrape -> Normalize -> Push to Airtable. Complete data pipeline.

Phase 3: Intelligence
  [GPT-4o Scorer] --> depends on Airtable (reads config + products)
  [Scoring Config Table] --> Airtable setup, no code dependency
  Result: Full pipeline including AI scoring.

Phase 4: Multi-Retailer
  [SSENSE Adapter] --> depends on adapter interface (defined in Phase 1)
  [Farfetch Adapter] --> depends on adapter interface
  [Adapter Registry] --> simple map of retailer name -> adapter
  Result: Multi-retailer support with shared normalization + scoring.

Phase 5: Production Hardening
  [Apify Scheduling] --> platform configuration
  [Error Monitoring] --> logging, alerting
  [Proxy Configuration] --> Apify proxy settings
  [Data Validation] --> Zod schemas for runtime validation
  Result: Reliable, scheduled, monitored production system.
```

**Critical dependency chain:** Schema -> Adapter Interface -> COS Adapter -> Router -> Normalizers -> Airtable Sync -> Scorer. This must be built roughly in order. The adapter interface (Phase 1) is the most important design decision because it constrains all future retailer additions.

## Scalability Considerations

This is a personal/small-team tool, not a high-scale service. Scale considerations are modest.

| Concern | Current (COS only) | 3 Retailers | 10+ Retailers |
|---------|--------------------|-----------  |---------------|
| **Crawl volume** | ~200-500 products per run | ~1000-2000 products per run | Consider parallel actors per retailer |
| **Airtable records** | ~500-1500 rows (color variants) | ~3000-6000 rows | Approaching Airtable limits (50K rows/base on free plan). Consider database migration. |
| **GPT-4o cost** | ~$0.10-0.50/run | ~$0.50-2.00/run | Consider Batch API (50% discount) or cheaper model (GPT-4o-mini) |
| **Apify compute** | Minimal, ~1-2 min run | ~3-5 min run | May need larger Actor memory or parallel runs |
| **Airtable API rate** | 5 req/s is fine | 5 req/s is fine | May bottleneck. Batch upserts help. |

## Sources

- [Crawlee Official Docs - Router](https://crawlee.dev/js/api/core/class/Router) -- HIGH confidence
- [Crawlee Official Docs - PlaywrightCrawler](https://crawlee.dev/js/api/playwright-crawler) -- HIGH confidence
- [Crawlee Refactoring Guide](https://crawlee.dev/js/docs/introduction/refactoring) -- HIGH confidence (project structure, router pattern)
- [Crawlee Result Storage](https://crawlee.dev/js/docs/guides/result-storage) -- HIGH confidence (Dataset, KeyValueStore)
- [Crawlee Saving Data](https://crawlee.dev/js/docs/introduction/saving-data) -- HIGH confidence (pushData)
- [Crawlee Parallel Scraping](https://crawlee.dev/js/docs/guides/parallel-scraping) -- HIGH confidence
- [Apify Actor Development](https://docs.apify.com/platform/actors/development) -- HIGH confidence
- [Apify Actor Monorepo Example](https://github.com/apify/actor-monorepo-example) -- HIGH confidence (project organization)
- [Apify Airtable Integration](https://docs.apify.com/platform/integrations/airtable) -- MEDIUM confidence (limitation claims)
- [Apify SDK Result Storage](https://docs.apify.com/sdk/js/docs/guides/result-storage) -- HIGH confidence
- [Airtable.js Official Library](https://github.com/airtable/airtable.js/) -- HIGH confidence (API client)
- [Airtable API Docs](https://airtable.com/developers/web) -- HIGH confidence (rate limits, batch sizes)
- [OpenAI GPT-4o Docs](https://developers.openai.com/api/docs/models/gpt-4o) -- HIGH confidence
- [XBVR Scraper Architecture](https://deepwiki.com/xbapps/xbvr/4.1-scraper-architecture) -- MEDIUM confidence (adapter pattern reference)
- [Next.js Scraping in 2025](https://www.trickster.dev/post/scraping-nextjs-web-sites-in-2025/) -- MEDIUM confidence (__NEXT_DATA__ and RSC patterns)
- [H&M Scraper Actor](https://github.com/emastra/actor-hm-scraper) -- MEDIUM confidence (H&M Group site structure)
- [Playwright Cookie Consent Handling](https://scrapfly.io/blog/how-to-click-on-modal-alerts-like-cookie-pop-up-in-playwright/) -- MEDIUM confidence
- [Pipeline Pattern (DEV.to)](https://dev.to/wallacefreitas/the-pipeline-pattern-streamlining-data-processing-in-software-architecture-44hn) -- LOW confidence (general pattern description)
