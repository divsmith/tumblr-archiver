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
- Access method: **web scraping** (no Tumblr API keys required)
- Resume: incremental runs that skip already-downloaded items
- Politeness: configurable rate limiting, concurrency limits, backoff & jitter; respect `robots.txt` where applicable

---

## Deliverables
- Production-ready CLI tool (recommended languages: Python / Go / Node.js)
- `manifest.json` (see schema below) stored in the blog output folder
- Unit tests + integration test against a public Tumblr blog
- README with installation, usage, and tuning options for rate limits
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
- `retrieved_from` (`tumblr` | `internet_archive`)
- `archive_snapshot_url` (if retrieved from archive)
- `status` (`downloaded` | `archived` | `missing` | `error`)
- `notes` (optional)

---

## Behavior & edge-cases
- Deduplicate identical files (store one copy; list all post references in manifest).
- If Internet Archive has multiple snapshots, choose highest-resolution; if resolution cannot be determined automatically, prefer most recent high-quality capture.
- For embedded external services (YouTube/Vimeo), store embed URL in manifest and download only if `--download-embeds` is set and permitted.
- Mark items with `status: missing` when neither source yields a file.

---

## Tests & acceptance criteria
- Acceptance: All media referenced by the blog are present locally OR retrieved from Internet Archive; `manifest.json` correctly reflects provenance.
- Unit tests: URL/post parsing, media extraction, archive lookup, deduplication, retry/backoff logic.
- Integration: end-to-end run against a public blog with >50 posts demonstrating resumability and archive fallback.

---

## Security & compliance
- Add clear user-facing notice about respecting site terms and copyright.
- Provide opt-out flags for copyrighted/reblog content.
- Avoid storing secrets; validate and sanitize input URLs.

---

## Implementation notes / suggestions
- Use concurrent worker pool with token-bucket throttling for rate control.
- Use robust HTML parsing (not regex) and canonicalize media URLs before deduplication.
- Query Wayback CDX API / Wayback snapshots for Internet Archive fallback.
- Persist progress in the manifest (or a sidecar DB) to allow immediate resume after interruption.

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

_Pick one and I'll proceed._
