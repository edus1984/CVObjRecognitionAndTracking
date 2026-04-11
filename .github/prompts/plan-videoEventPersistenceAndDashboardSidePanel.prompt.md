## Plan: Video/Event Persistence and Dashboard Side Panel

Build a normalized persistence flow from upload to vision processing to dashboard consumption, centered on two tables (videos and events with FK), strict filename validation/parsing, computed absolute event timestamps, and complete test coverage for parser, API flow, and persistence behavior.

**Steps**
1. Phase 1: Data model and DB bootstrap.
2. Add a first-run SQL bootstrap script in the db area that creates required extension(s), videos/events tables, FK constraints, and query indexes.
3. Extend ORM models in [db/models.py](db/models.py) to include a Video entity and Event-to-Video relationship aligned to the SQL schema.
4. Ensure first-run DB initialization path is explicit and safe via [db/database.py](db/database.py), while keeping the SQL bootstrap as the canonical initialization artifact.
5. Phase 2: Filename parsing and metadata extraction.
6. Add a focused parser utility (module placed within current structure) to parse [datetime]_[cameraID]_[location][sector].[ext].
7. Enforce strict validation: reject uploads when naming does not match expected pattern.
8. Extract and carry metadata: capture start datetime, camera ID, location name, sector number, filename, extension.
9. Add verbose logging for parsing success/failure paths.
10. Phase 3: Pipeline persistence integration.
11. Update [vision/pipeline.py](vision/pipeline.py) to track fps, frame index, relative event second, and persistence-ready payloads.
12. Update [vision/events.py](vision/events.py) contract minimally so emitted events include timing context needed for DB writes.
13. Compute absolute event timestamp as video capture start datetime + relative event second.
14. Persist workflow: create video row at upload start, store linked events during/after processing, finalize video status and summary fields.
15. Add robust logs across stages: video open, parsing, processing progress, event generation, DB write summary, completion/errors.
16. Phase 4: API and dashboard wiring.
17. Extend [api/main.py](api/main.py) upload flow to validate filename, create/update video records, and persist events from pipeline output.
18. Add API endpoint(s) to list uploaded videos (newest first) for dashboard consumption.
19. Update [dashboard/app.py](dashboard/app.py) to 80/20 layout:
20. Left 80% keeps current primary content.
21. Right 20% contains top video visualizer and below it uploaded videos list from DB/API, including empty-state and selection behavior.
22. Phase 5: Tests and quality gates.
23. Add/extend test setup under tests folder with pytest-based unit and integration coverage (mock-heavy, no real PostgreSQL required).
24. Unit tests: parser valid/invalid naming, timestamp derivation, event payload mapping.
25. Integration tests: upload validation, pipeline invocation, DB persistence calls/transactions, list-videos endpoint response.
26. Dashboard checks: right-column rendering logic, uploaded-list handling, empty-state behavior.
27. Phase 6: Documentation.
28. Append README end section in [README.md](README.md) documenting DB bootstrap usage, filename convention, timestamp logic, new API behavior, dashboard side panel, and test commands.

**Relevant files**
- [vision/pipeline.py](vision/pipeline.py) for timing capture, event payload enrichment, persistence hooks, and verbose logs.
- [vision/events.py](vision/events.py) for event output structure and timing context.
- [api/main.py](api/main.py) for upload validation/persistence orchestration and videos listing endpoint.
- [db/models.py](db/models.py) for Video/Event schema alignment and relationships.
- [db/database.py](db/database.py) for initialization/session integration points.
- [dashboard/app.py](dashboard/app.py) for 80/20 layout and right-side video/list panel.
- [config.py](config.py) for any small config additions required by parsing/logging defaults.
- [requirements.txt](requirements.txt) for test dependency additions.
- [README.md](README.md) for appended feature documentation.

**Verification**
1. Run SQL bootstrap on clean DB and confirm videos/events tables, FK, and indexes exist.
2. Upload valid filename and confirm: video row inserted, events linked by FK, absolute event timestamps computed correctly.
3. Upload invalid filename and confirm strict API rejection with clear validation error.
4. Validate logs show all key processing stages and DB write summaries.
5. Open dashboard and confirm right 20% column behavior: video player on top, uploaded list below, selection and empty states.
6. Run tests and confirm new unit/integration suite passes in mock-heavy mode.
7. Sanity-check existing upload/process flow to ensure no regressions.

**Decisions Applied**
- Event absolute timestamp = capture datetime from filename + relative event second in video.
- Filename mismatch = reject upload.
- Parse pattern for any extension (not only mp4).
- Integration tests are mock-heavy (no mandatory real PostgreSQL in first pass).

Plan is saved at /memories/session/plan.md. If you approve this, the next agent can execute it directly in implementation mode.
