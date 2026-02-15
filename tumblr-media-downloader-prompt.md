# Tumblr v1 media retriever — Task prompt

## Objective
Build a cross-platform **Python CLI** that retrieves **all media** from a given public Tumblr blog using the **v1 (public HTTP) API** and saves the best-quality assets to disk.

## Primary deliverable
- `tumblr-media-downloader` — runnable Python CLI with an entry point.

## Success criteria
- Downloads every media asset from all public posts of the specified blog (photos, photosets, animated GIFs, videos, audio).
- For any image available in multiple resolutions within a single post, **download the highest-resolution variant only**.
- Files saved using `postID_filename` (flat layout).
- Produces `manifest.json` including post metadata and the filenames downloaded.
- Re-running the CLI skips files that already exist by filename (idempotent behavior).

## Functional requirements
- CLI args:
  - Required: `--blog` (blog name or URL), `--out` (output directory).
  - Recommended extras: `--concurrency`, `--max-posts`, `--dry-run`, `--verbose`.
- Media selection:
  - Download images, animated GIFs, videos, audio, and photosets.
  - When multiple resolutions exist for the same image in a single post, select **only the highest-resolution** variant.
    - Tie-breakers (in order): 1) largest width×height, 2) larger file size (bytes), 3) prefer `original`/largest-quality URL or native format.
    - For videos, prefer the highest-resolution / highest-bitrate variant available.
  - Do not store multiple size variants of the same asset for the same post.
- API:
  - Use Tumblr **v1 public endpoints** (no API key / no OAuth). Paginate until no more posts.
- Output & layout:
  - Flat filenames: `postID_originalFilenameOrSuffix`.
  - Write `manifest.json` at the `--out` root with per-post metadata and downloaded filenames.
- Behavior:
  - Skip files that already exist by filename.
  - Default concurrency: 5 parallel downloads with retry/backoff on transient errors (configurable).
  - Log progress and errors; continue on partial failures.

## Manifest (high level schema)
Per-post entries should include at least:
- `post_id`, `post_url`, `timestamp`, `tags`
- `media_sources` (array of all found source URLs for the asset)
- `chosen_url` (the URL actually downloaded)
- `downloaded_filename`, `width`, `height`, `bytes`

## Non-functional requirements
- Low memory footprint (suitable for very large blogs).
- Respectful rate-limiting and backoff on HTTP 429 or errors.
- Minimal dependencies; publishable as an installable console script.

## Acceptance tests (manual examples)
1. Run the CLI on a blog that exposes multiple image sizes (e.g., `_1280`, `_500`, `_250`) — confirm only the largest (`_1280`) is downloaded and recorded in `manifest.json`.
2. Verify video posts pick the highest-resolution/bandwidth variant.
3. Re-run the CLI and confirm previously-downloaded files are not re-fetched.

## Assumptions & constraints
- Only public content is in scope (no OAuth/private posts).
- User is responsible for lawful use and compliance with Tumblr's terms.

## Suggested optional items (ask to enable)
- `--concurrency`, `--max-posts`, `--verbose`, unit tests, CI, Dockerfile.

---

*Generated task prompt — ready to use for implementation or to give to an LLM/developer.*
