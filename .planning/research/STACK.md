# Technology Stack

**Project:** Fashion Scraper Pipeline (COS Menswear)
**Researched:** 2026-03-02
**Overall confidence:** HIGH

---

## Recommended Stack

### Runtime & Language

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Node.js | 22.x LTS | Runtime | Apify's recommended LTS version; Docker base images ship with 22. Node 22 is the current active LTS line (through April 2027). | HIGH |
| TypeScript | 5.x (latest) | Language | Apify's official templates use TypeScript. Type safety for complex product schemas prevents runtime bugs. Crawlee is TypeScript-first with full type declarations. | HIGH |

### Scraping Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Crawlee | 3.16.x | Core scraping orchestration | The official Apify-endorsed crawling framework. Handles request queuing, retries, proxy rotation, session management, and anti-blocking out of the box. Latest stable: v3.16.0 (Feb 6, 2026). TypeScript-first. | HIGH |
| @crawlee/playwright | 3.16.x | Browser automation crawler | Part of the Crawlee monorepo. PlaywrightCrawler provides full browser automation with auto-waiting, configurable concurrency, pre/post navigation hooks (critical for cookie banners), and proxy integration. | HIGH |
| Playwright | 1.58.x | Browser engine | Playwright over Puppeteer because: (1) auto-waiting for elements reduces flaky selectors, (2) built-in multi-browser support (Chrome, Firefox, WebKit) for anti-detection fallbacks, (3) better documentation and more active development, (4) Apify's own recommendation: "Playwright is more modern, user-friendly and harder to block than Puppeteer." | HIGH |

### Apify Platform

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| apify (SDK) | 3.6.x | Actor lifecycle, storage, input/output | Official SDK for building Actors. Handles Actor.init(), Actor.getInput(), Actor.pushData(), key-value stores, and dataset management. Latest: 3.6.0 (Feb 2026). | HIGH |
| apify-client | 2.22.x | API client (for orchestration if needed) | Only needed if you build a separate scheduler or want to trigger runs programmatically. Not required for the actor itself. | MEDIUM |
| Apify Cloud | N/A | Hosting & scheduling | The specified deployment target. Provides scheduling via cron expressions, built-in proxy infrastructure, monitoring dashboard, and pay-per-usage pricing. Non-technical client can adjust schedules through the UI. | HIGH |

### Docker Base Image

| Technology | Tag | Purpose | Why | Confidence |
|------------|-----|---------|-----|------------|
| apify/actor-node-playwright-chrome | 22-1.52.0 (pin to current) | Container image | Chrome-only Playwright image is much smaller than the all-browser image. COS does not require Firefox or WebKit. Pin both Node.js version and Playwright version for reproducible builds. | HIGH |

**Important:** Pin the image tag. The Crawlee docs explicitly warn against using `latest` -- browser updates can break selectors silently. Verify the exact latest Playwright version bundled in the Docker image at build time and pin it (e.g., `22-1.58.0` when available, or the latest pinned tag on Docker Hub).

### AI / LLM Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| openai (SDK) | 6.25.x | GPT-4o API calls for scoring | Official OpenAI Node.js/TypeScript SDK. Latest: ~6.25.0 (Feb 2026). Includes `zodResponseFormat` helper for structured outputs, ensuring GPT-4o returns valid JSON matching your Zod schema every time. | HIGH |
| GPT-4o | latest snapshot | Scoring model | Specified in project requirements. Supports structured outputs natively. Use `gpt-4o` model string (auto-routes to latest snapshot). For cost control, consider `gpt-4o-mini` for scoring since it is a simple 1-10 number -- but start with `gpt-4o` as specified. | HIGH |
| zod | 4.3.x | Schema validation | Used with OpenAI's `zodResponseFormat()` to define and validate the scoring response schema. Also useful for validating scraped product data before Airtable push. Latest: 4.3.6 (Feb 2026). | HIGH |

### Data Storage (Airtable)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| airtable (official JS client) | 0.12.2 | Airtable CRUD operations | The official client. Last published ~3 years ago (2023), but still functional. Handles rate limiting (5 req/s per base) and retries automatically. Not actively maintained, but the Airtable REST API itself is stable and backwards-compatible. | MEDIUM |
| Native fetch (alternative) | Built-in | Direct REST API calls | If the official client causes issues (no ESM support, stale types), use Node.js 22's built-in `fetch()` against the Airtable REST API directly. The API is simple (JSON over HTTPS with Bearer token auth). This is a viable fallback. | MEDIUM |

**Recommendation:** Start with the official `airtable` package. It handles rate limit retries. Switch to direct `fetch()` only if you hit compatibility issues with ESM or TypeScript types. Wrap all Airtable calls behind a thin abstraction layer so swapping is trivial.

**Key Airtable API constraints:**
- Rate limit: 5 requests/second per base
- Batch size: Up to 10 records per create/update/upsert request
- Effective throughput: 50 records/second max (5 batched requests x 10 records each)
- Upsert via `performUpsert` parameter: find-or-create in a single call (reduces API calls)
- For ~100-300 color variants per scrape run, this is more than sufficient

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| zod | 4.3.x | Schema validation for all data | Validate scraped product data shape before processing; define OpenAI response schemas | HIGH |
| dotenv | 16.x | Environment variable management | Local development only; Apify Cloud provides env vars natively | HIGH |
| typescript | 5.x | TypeScript compiler | Dev dependency for compilation | HIGH |
| @apify/log | (bundled with apify) | Structured logging | Comes with the Apify SDK; use for all logging instead of console.log | HIGH |

### Dev Dependencies

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| eslint | 9.x | Linting | HIGH |
| typescript-eslint | 8.x | TypeScript ESLint rules | HIGH |
| @eslint/js | (latest) | ESLint recommended config | HIGH |
| @types/node | 22.x | Node.js type definitions | HIGH |
| apify-cli | 1.2.x | Local actor development, testing, deployment | HIGH |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Browser automation | Playwright (via Crawlee) | Puppeteer | Puppeteer is Chromium-only, less actively developed, missing auto-wait. Apify themselves recommend Playwright for new projects. |
| Browser automation | Playwright (via Crawlee) | Selenium | Much heavier, slower, no Node.js-first design. Overkill for this use case. |
| Scraping framework | Crawlee | Raw Playwright | Crawlee adds request queue management, automatic retries, proxy rotation, session pooling, anti-blocking headers, and dataset storage. Writing this from scratch would take weeks. |
| Scraping framework | Crawlee | Scrapy (Python) | Project is TypeScript. Scrapy lacks browser automation. Apify's Python Crawlee is less mature than JS version. |
| Anti-detection | Crawlee built-in + Apify proxies | Camoufox (Firefox fork) | COS likely uses moderate anti-bot. Start with Chrome + Apify datacenter proxies. Upgrade to Camoufox template only if blocked. Camoufox adds complexity. |
| LLM SDK | openai (official) | langchain / vercel ai sdk | For a single API call to GPT-4o with structured output, the official SDK is simpler and has zero unnecessary abstraction. LangChain adds massive dependency bloat for no benefit here. |
| LLM model | GPT-4o | GPT-4o-mini | Mini is 10-20x cheaper and likely sufficient for a simple 1-10 scoring task. Start with GPT-4o as specified; recommend switching to mini after validating quality. |
| Airtable client | airtable (official) | Direct fetch / pyairtable | Official client works. Community alternatives are even more stale. Direct fetch is viable but requires manual rate limiting. |
| Schema validation | Zod 4 | Joi / Yup / AJV | Zod is TypeScript-first with type inference, integrates with OpenAI structured outputs via zodResponseFormat, and is the standard in the modern TS ecosystem. |
| Hosting | Apify Cloud | AWS Lambda / Railway / Fly.io | Apify Cloud is specified. It provides built-in proxy, scheduling, monitoring, and a non-technical-friendly UI. Self-hosting would require building all of this. |

---

## Cookie Consent Handling Strategy

COS (and most H&M Group sites) uses cookie consent banners (likely OneTrust or similar).

**Recommended approach (in order of preference):**

1. **Pre-set consent cookies via `preNavigationHooks`** (BEST)
   - Before navigating, inject the consent cookie (e.g., `OptanonAlertBoxClosed`, `OneTrustGroupsConsent`) into the browser context
   - Zero DOM interaction needed, fastest, most reliable
   - Requires one-time investigation of which cookie values COS expects

2. **Click the accept button**
   - Use `page.click()` with a resilient selector targeting the accept button
   - Wrap in try/catch with timeout -- banner may not appear on every page load

3. **Block the consent script via `page.route()`**
   - Intercept and abort requests to the cookie consent JS
   - Risk: some sites break without the consent script

**Do NOT use:** `idcac-playwright` package (IDCAC browser extension port). Crawlee mentions it but does not bundle it due to licensing issues, and it adds a fragile dependency.

---

## Project Structure (Apify Actor Convention)

```
fashion-scraper/
  .actor/
    actor.json            # Actor manifest (name, version, Docker config)
    input_schema.json     # Input UI schema for Apify Console
  src/
    main.ts               # Actor entry point (Actor.init/exit lifecycle)
    routes.ts             # PlaywrightCrawler route handlers
    config.ts             # Type-safe configuration from Actor input
    scraper/
      cos.ts              # COS-specific scraping logic
      selectors.ts        # CSS/XPath selectors (isolated for maintainability)
    processing/
      normalize.ts        # Color normalization, price parsing
      scoring.ts          # GPT-4o scoring integration
    storage/
      airtable.ts         # Airtable client wrapper with batching/retry
      schemas.ts          # Zod schemas for product data
    utils/
      cookies.ts          # Cookie consent handling
  storage/                # Local development storage (gitignored)
    datasets/
    key_value_stores/
    request_queues/
  Dockerfile              # Based on apify/actor-node-playwright-chrome
  package.json
  tsconfig.json
  eslint.config.js        # ESLint 9 flat config
  .gitignore
```

---

## Installation

```bash
# Initialize project from Apify template
npx apify-cli create fashion-scraper --template ts-crawlee-playwright-chrome

# Core dependencies
npm install crawlee @crawlee/playwright playwright apify openai airtable zod

# Dev dependencies
npm install -D typescript @types/node eslint typescript-eslint @eslint/js apify-cli
```

**Note:** The Apify template will install most of these automatically. The above lists what the final package.json should contain.

---

## Environment Variables / Actor Input

The actor should accept configuration via Apify Actor Input (defined in `input_schema.json`), NOT environment variables, so the non-technical client can adjust settings through the Apify Console UI.

**Actor Input fields:**
| Field | Type | Purpose |
|-------|------|---------|
| `startUrls` | array of strings | COS category page URLs to scrape |
| `maxProducts` | integer | Limit products per run (for testing) |
| `airtableApiKey` | string (secret) | Airtable personal access token |
| `airtableBaseId` | string | Target Airtable base ID |
| `airtableTableName` | string | Target table name |
| `openaiApiKey` | string (secret) | OpenAI API key |
| `scoringModel` | string (enum) | GPT model to use (default: gpt-4o) |
| `enableScoring` | boolean | Toggle AI scoring on/off |
| `proxyConfig` | object | Apify proxy configuration |

Secrets (API keys) should be stored in Apify's encrypted environment variables, not in the input schema directly. The input schema references them as defaults from env vars.

---

## Version Pinning Strategy

| Dependency | Pin Strategy | Rationale |
|------------|-------------|-----------|
| crawlee | `^3.16.0` | Minor updates safe; major version changes may break |
| playwright | Pinned via Docker image tag | Browser version must match Docker image exactly |
| openai | `^6.25.0` | Caret range; SDK is stable and backwards-compatible |
| airtable | `^0.12.2` | Unlikely to update; pin what works |
| zod | `^4.3.0` | Zod 4 is stable; minor updates safe |
| Node.js | Pin via Docker `FROM` tag | `22` in Dockerfile |

---

## Cost Considerations

| Service | Cost Model | Estimate per Run (~200 products) |
|---------|-----------|----------------------------------|
| Apify Cloud | $0.25-0.50/actor-compute-unit (CU) | ~0.1-0.3 CU per run = ~$0.03-$0.08 |
| Apify Proxies | $0.10-$8.00/1000 requests (datacenter vs residential) | Datacenter: ~$0.02; Residential: ~$1.60 |
| OpenAI GPT-4o | ~$2.50/1M input + $10/1M output tokens | ~200 scoring calls x ~500 tokens each = ~$0.02-0.05 |
| Airtable | Free tier: 1000 records, 1000 API calls/month | Likely within free tier for weekly runs |

**Total estimated cost per daily run:** $0.10-$2.00 depending on proxy type.

**Cost optimization:** Use datacenter proxies first (much cheaper). Switch to residential only if COS blocks datacenter IPs. Use GPT-4o-mini for scoring to cut LLM costs by ~10x.

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| Puppeteer | Inferior to Playwright in every dimension for new projects. Apify recommends Playwright. |
| Selenium | Too heavy, not Node.js native, no Crawlee integration. |
| LangChain | Massive dependency for a single GPT-4o call. Use the OpenAI SDK directly. |
| Cheerio / CheerioCrawler | COS is a React SPA that requires full browser rendering. Cheerio only parses static HTML. |
| Python Crawlee | Less mature than JS/TS version. The project is TypeScript. |
| Scrapy | Python, no browser automation, wrong ecosystem. |
| Bright Data / ScrapingBee | External proxy services are unnecessary -- Apify Cloud includes proxy infrastructure. |
| MongoDB / PostgreSQL | Overkill. Airtable IS the database per requirements. Crawlee datasets handle intermediate storage. |
| Express / Fastify | This is a batch job (Apify Actor), not a web server. No HTTP endpoints needed. |
| cron / node-schedule | Apify Cloud has built-in scheduling with a UI. Do not build your own scheduler. |

---

## Sources

### Verified (HIGH confidence)
- [Crawlee GitHub - releases (v3.16.0, Feb 2026)](https://github.com/apify/crawlee/releases)
- [Crawlee Docker images documentation](https://crawlee.dev/js/docs/guides/docker-images)
- [PlaywrightCrawler API options](https://crawlee.dev/js/api/playwright-crawler/interface/PlaywrightCrawlerOptions)
- [Apify Actor templates (official)](https://github.com/apify/actor-templates)
- [Apify input schema specification](https://docs.apify.com/platform/actors/development/actor-definition/input-schema/specification/v1)
- [Apify base Docker images (Node 20/22/24)](https://docs.apify.com/platform/actors/development/actor-definition/dockerfile)
- [OpenAI structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs/)
- [OpenAI Node.js SDK changelog (v6.x)](https://github.com/openai/openai-node/blob/master/CHANGELOG.md)
- [Airtable rate limits (5 req/s, 10 records/batch)](https://support.airtable.com/docs/managing-api-call-limits-in-airtable)
- [Airtable.js on npm (v0.12.2)](https://www.npmjs.com/package/airtable)

### Community Verified (MEDIUM confidence)
- [Playwright vs Puppeteer comparison (Apify blog)](https://blog.apify.com/playwright-vs-puppeteer/)
- [Cookie consent handling via preNavigationHooks (Crawlee community)](https://github.com/apify/crawlee/discussions/2299)
- [Apify anti-scraping academy](https://docs.apify.com/academy/anti-scraping)
- [Apify proxy documentation](https://apify.com/proxy)
- [OpenAI Responses API migration guide](https://platform.openai.com/docs/guides/migrate-to-responses)
- [Zod + zodResponseFormat tutorial](https://hooshmand.net/zod-zodresponseformat-structured-outputs-openai/)

### Unverified (LOW confidence)
- COS website technology stack (could not confirm SPA framework; 403 on direct fetch; assumed React/Next.js based on H&M Group patterns -- needs manual browser inspection)
- COS cookie consent provider (likely OneTrust based on H&M Group usage patterns -- needs manual verification)
- Exact Playwright version bundled in latest Docker image tag (verify at build time)
