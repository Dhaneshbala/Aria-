# ARIA File Organizer — API Reference

Base URL: `http://127.0.0.1:8000/api/files`

All endpoints return JSON. AI analysis uses local Ollama models
(`qwen3:8b` for reasoning, `qwen2.5vl:3b` for vision) unless overridden
in Settings. File records include: `id, title, name, path, extension,
category, size, sha256, folder, subject, topic, doc_type, tags,
keywords, content_preview, ai_folder, ai_title, confidence, explanation`.

---

## Files

| Method | Path | Description |
|---|---|---|
| GET | `/api/files` | All files + folders + stats |
| GET | `/api/files/stats` | Totals, categories, top tags, AI stats |
| GET | `/api/files/folder-tree` | Nested folder tree with counts |
| GET | `/api/files/{id}` | One file record |
| DELETE | `/api/files/{id}` | Delete (soft; history recorded) |
| PUT | `/api/files/{id}/rename` | `{title}` — renames on disk too |
| PUT | `/api/files/{id}/move` | `{folder, physically?, path?}` |
| POST | `/api/files/bulk-move` | `{file_ids, folder}` |
| POST | `/api/files/bulk-delete` | `{file_ids}` |
| POST | `/api/files/bulk-rename` | `[{file_id, title}]` |

## Scan / Upload

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/scanned-folders` | Previously scanned folders |
| POST | `/api/files/scan-folder` | `{path, recursive?, max_depth?}` — index a folder |
| POST | `/api/files/organize-in-place` | `{path, dry_run?}` — scan + organize into `ARIA Organized/` |
| POST | `/api/files/preview-organization` | `{file_ids? / path?}` — DRY-RUN plan, moves nothing |
| POST | `/api/files/upload` | multipart file upload |
| POST | `/api/files/upload-multiple` | multipart multiple files |
| POST | `/api/files/upload-folder` | multipart with folder paths |

## AI

| Method | Path | Description |
|---|---|---|
| POST | `/api/files/ai-organize` | **SSE** 4-phase organize: vision scan → read/analyze → design folders → place (rules first, then AI). `{path?, dry_run?}` |
| POST | `/api/files/deep/propose` | **SSE** Deep rename+organize proposals (Riffo-style): reads full content + OCR, proposes new name AND folder per file. `{file_ids?, path?}` — no limits. Uses `think=False` + `format=json` for reliable structured output; a keyword-evidence guard overrides clearly wrong subject calls. Images scanned last (OCR via `qwen2.5vl:3b`, non-image files never hit vision) |
| GET | `/api/files/deep/proposals` | Pending/applied proposals `?status=pending\|applied\|error` |
| GET | `/api/files/deep/proposal/{file_id}` | Single proposal |
| POST | `/api/files/deep/apply` | Apply proposals `{proposal_ids?}` — renames + moves with backups, every change undoable via History |
| DELETE | `/api/files/deep/proposals` | Clear proposals `?status=` |
| POST | `/api/files/ai-analyze-all` | Batch AI analysis of every indexed file |
| POST | `/api/files/{id}/ai-rename` | AI title suggestion |
| POST | `/api/files/{id}/ai-folder` | AI folder decision `{folder, reason, confidence, source}` |
| POST | `/api/files/ai-rename-all` | AI title suggestions for unrenamed files (not applied) |

SSE events: `start`, `phase`, `scanning`, `scanned`, `scan_error`,
`reading`, `folders`, `analyzing`, `moved`, `error`, `done`.

## Rules (custom automation)

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/rules` | List rules (desc priority) |
| POST | `/api/files/rules` | Create `{name, conditions[], actions[], priority?}` |
| PUT | `/api/files/rules/{id}` | Update |
| DELETE | `/api/files/rules/{id}` | Delete |
| GET | `/api/files/rules/example` | Built-in starter rules |

Conditions: `field` ∈ `extension, name, title, category, subject, topic,
doc_type, folder, size, path, tag, project`; `op` ∈ `eq, contains, in,
regex, gt, lt`. Actions: `move_to_folder`, `set_folder`, `rename_to`.
Higher `priority` wins. See `backend/data/example_rules.json`.

## Profiles

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/profiles` | List reusable profiles |
| POST | `/api/files/profiles` | Create `{name, rules?}` |
| DELETE | `/api/files/profiles/{id}` | Delete |
| POST | `/api/files/profiles/{id}/apply` | Load profile's rules into the rules table |

## History / Undo / Rollback

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/history` | `{limit?, file_id?}` — every action |
| POST | `/api/files/undo/{history_id}` | Reverse one move/rename/delete |
| POST | `/api/files/rollback` | `{op?}` — undo all operations of a type (move/rename/delete/organize) |

Every move is backed up to `backend/storage/backups/` and verified by
size after moving. **Files are never deleted automatically.**

## Duplicates / Cleanup

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/duplicates` | Exact duplicates by SHA-256 |
| GET | `/api/files/near-duplicates` | `{threshold?}` — similar by content overlap |
| GET | `/api/files/cleanup-suggestions` | Broken paths, stale entries, dupes, huge files |

## Search

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/search` | `q?` + `category, subject, folder, doc_type, min_size, max_size, after, before, tags` filters. Scored: title 100 / name 90 / tags 60 / keywords 50 / folder 40 / subject+type 30 / content 20 |
| GET | `/api/files/{id}/similar` | Similar files |
| GET | `/api/files/saved-searches` | List saved searches |
| POST | `/api/files/saved-searches` | `{name, query}` |
| DELETE | `/api/files/saved-searches/{id}` | Delete |

## Preview / Media

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/{id}/preview` | Content preview, OCR text, vision, AI explanation |
| GET | `/api/files/{id}/image` | Raw image bytes |

## Folder Watching

| Method | Path | Description |
|---|---|---|
| GET | `/api/files/watch/status` | Watched folders + last scan |
| POST | `/api/files/watch/{path}` | Watch a folder (auto-index new files) |
| DELETE | `/api/files/watch/{path}` | Stop watching |
| POST | `/api/files/watch/start` `/watch/stop` | Restart / stop all watches |
| GET | `/api/files/events` | Event log (organize runs, errors, etc.) |
