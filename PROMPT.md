# Tumblr media retriever — Engineer-ready prompt

## Summary
Build a CLI tool that, given a Tumblr blog URL, downloads **every image, animated GIF, and video** posted to that blog (including reblogs and external embeds). If a media file is missing on Tumblr, automatically query the Internet Archive and retrieve the best (highest-resolution) archived capture. The tool must be polite, resumable, and produce a machine-readable manifest.

---

## Requirements (high level)
- Input: `tumblr` blog URL (e.g., `https://example.tumblr.com`)
- Output: local directory per blog + `manifest.json` describing all media and provenance
- Media types: **images (jpg/png/webp), animated GIFs, videos** (Tumblr-hosted; capture external embeds as links and optionally download)
- Fallback: automatic Internet Archive lookup — prefer highest-resolution snapshot when available
- Include: reblogs and externally embedded media by default
- Access method: **Tumblr API (primary)** — use the official Tumblr v2 API to enumerate every post and retrieve media metadata. Support a read-only API key via `--tumblr-api-key` or `TUMBLR_API_KEY`; allow OAuth for authenticated access when required. The tool must page through all posts (use `total_posts`/pagination or the API's `offset`/`before` parameters) so *every post* is processed, including posts whose media have been removed.
  - Recovery for removed media: when a Tumblr-hosted media URL returns 4xx/placeholder, extract the API-provided original/media URLs (e.g., `photos.alt_sizes`, `video` sources) and query the Internet Archive (Wayback CDX/Availability APIs) for archived captures of the media or the post page; prefer highest-resolution archived captures and record provenance in the manifest.
- Resume: incremental runs that skip already-downloaded items
- Politeness: configurable rate limiting, concurrency limits, backoff & jitter; respect `robots.txt` where applicable

---

## Deliverables
- Production-ready CLI tool (recommended languages: Python / Go / Node.js)
- `manifest.json` (see schema below) stored in the blog output folder
- Unit tests + integration test against a public Tumblr blog
- README with installation, usage, instructions for obtaining/setting a Tumblr API key or OAuth credentials (`TUMBLR_API_KEY`), and explanation of the Wayback fallback and configuration flags
- Optional: Dockerfile for reproducible runs

---

## CLI (suggested)
- Usage example:
  - `tumblr-archiver --url https://example.tumblr.com --out ./archives/example --resume --concurrency 2 --rate 1`
- Flags:
  - `--url <blog-url>`
  - `--out <directory>`
  - `--resume` (default: on)
  - `--concurrency <n>`
  - `--rate <req/sec>`
  - `--include-reblogs` / `--exclude-reblogs`
  - `--download-embeds` (opt-in for external videos)
  - `--recover-removed-media` (default: on) — attempt Wayback/Internet Archive lookup when Tumblr-hosted media is missing
  - `--wayback` / `--no-wayback` — enable or disable Internet Archive fallback
  - `--wayback-max-snapshots <n>` (default: 5) — how many Wayback snapshots to consider per URL
  - `--tumblr-api-key <key>` or set env `TUMBLR_API_KEY` — read-only Tumblr API key for public blogs (preferred)
  - `--oauth-consumer-key` / `--oauth-token` (optional) — for authenticated access when needed
  - `--dry-run`, `--verbose`

---

## Rate-limit & politeness (required)
- Default safe settings (recommended): `--rate 1 req/sec`, `--concurrency 2`, `retries=3`, `base-backoff=1s`, `max-backoff=32s`, randomized jitter on retries.
- Behavior: exponential backoff for 429/5xx, respect Retry-After, allow user override via CLI/config.
- Logging: surface when rate limits/backoff occur and provide ETA estimates.

---

## Manifest schema (required fields)
Each media object in `manifest.json` should include:
- `post_id`, `post_url`, `timestamp`
- `media_type` (image|gif|video)
- `filename`, `byte_size`, `checksum` (SHA256)
- `original_url` (Tumblr or external)
- `api_media_urls` (optional array) — all media URLs reported by the Tumblr API (e.g., `alt_sizes`)
- `media_missing_on_tumblr` (boolean) — true when the Tumblr-hosted URL returns 4xx/placeholder
- `retrieved_from` (`tumblr` | `internet_archive` | `external`)
- `archive_snapshot_url` (if retrieved from archive)
- `archive_snapshot_timestamp` (ISO8601 or Wayback timestamp)
- `status` (`downloaded` | `archived` | `missing` | `error`)
- `notes` (optional)

---

## Behavior & edge-cases
- Enumerate every post using the Tumblr API and continue pagination until the API indicates all posts have been returned (use `total_posts`, `offset`/`before`).
- Include posts even when their media has been removed by Tumblr; record the API-provided media URLs in the manifest and set `media_missing_on_tumblr: true` when the media URL returns 4xx/placeholder.
- Recovery flow for removed media:
  - Try API-provided media URLs first (e.g., `photos.alt_sizes`, `video` sources).
  - Query the Internet Archive (Wayback CDX / Availability APIs) for exact-URL snapshots; prefer highest-resolution or most recent high-quality snapshot.
  - If no exact media snapshot is available, request snapshots of the post page and extract archived media URLs from the archived HTML.
  - If an archived media file is found, download it and set `retrieved_from: internet_archive` with `archive_snapshot_url` and `archive_snapshot_timestamp`.
  - If no archived capture exists, mark `status: missing`.
- Deduplicate identical files across posts and reblogs; list all referencing `post_id`s in the manifest.
- For external embeds (YouTube/Vimeo/etc.), store embed URL(s) in the manifest and download only when `--download-embeds` is set and permitted.
- Respect rate limits, implement exponential backoff with jitter for 429/5xx, and allow users to disable Wayback lookups for privacy or speed.

---

## Tests & acceptance criteria
- Acceptance: The tool enumerates every post returned by the Tumblr API (matches `total_posts`) and either:
  - downloads the media from Tumblr, or
  - recovers the media from the Internet Archive (when `media_missing_on_tumblr`), or
  - marks the item `status: missing` when no source is available.
  The `manifest.json` must accurately reflect provenance (`retrieved_from`) and any Wayback snapshot metadata.
- Unit tests: URL/post parsing, Tumblr API pagination, media extraction from API responses, Wayback/CDX lookup and parsing, deduplication, retry/backoff logic.
- Integration: end-to-end run against a public Tumblr blog with >50 posts demonstrating full pagination, resumability, and Wayback recovery for intentionally-removed media.

---

## Security & compliance
- Add clear user-facing notice about respecting site terms and copyright.
- Provide opt-out flags for copyrighted/reblog content.
- Avoid storing secrets; validate and sanitize input URLs.

---

## Implementation notes / suggestions
- Use Tumblr v2 API (`/blog/{blog-identifier}/posts`) as the primary data source. Page through posts using `offset`/`limit` or `before`; rely on `total_posts` to confirm completion.
- Inspect API fields for media:
  - `photos` -> `alt_sizes` for image URLs and resolutions (pick highest `width`/`height` available).
  - `video` objects / `player` sources for video URLs.
  - `trail` for reblog provenance and `post` metadata for canonical URLs.
- For posts where the API reports media but the media URL returns 4xx/placeholder, treat the API's URLs as canonical "original" targets for Wayback lookups.
- Use a concurrent worker pool with token-bucket throttling for rate control and to respect Tumblr API limits; implement exponential backoff + jitter for 429/5xx responses.
- For Internet Archive fallback, query the Wayback CDX or Availability APIs with the original media URL and, if necessary, the post page URL; prefer highest-resolution archived captures and construct replay URLs like `https://web.archive.org/web/{timestamp}/{original_url}`.
- Persist progress in the manifest (and optional sidecar DB) for resumability; store API metadata and any Wayback snapshot metadata to avoid repeated archive queries.
- Keep API keys/secrets out of logs; prefer env vars for credentials.

---

## Success criteria (must pass)
1. Tool completes a run without crashes and produces a populated `manifest.json`.
2. Any media missing from Tumblr is retrieved from Internet Archive (when available) and marked accordingly.
3. The tool resumes correctly and does not re-download existing files.
4. Rate-limit behavior prevents 429s under default settings and is configurable.

---

## Next steps
- Draft a compact JSON manifest schema and sample file, or
- Draft a minimal CLI implementation plan (language & package recommendations).

