# Bugfix Requirements Document

## Introduction

The SyncKar mock controls system has five interconnected bugs that collectively make the demo environment non-functional on a fresh deploy. The mock systems start empty (no auto-seed), the dashboard has no way to trigger seeding, the UBID dropdown is incomplete and shows no business names, the conflict trigger silently fails because the mock DBs are empty, and the Mock Controls page is missing several action buttons. These bugs must be fixed together because Bug 4 (conflict trigger failure) is a downstream consequence of Bug 1 (empty databases).

---

## Bug Analysis

### Current Behavior (Defect)

**Bug 1 — Mock systems start empty**

1.1 WHEN a fresh container starts (or the SQLite DB is new/empty) THEN the system returns "Record not found" for every UBID lookup because no auto-seed logic runs on startup

1.2 WHEN `seed_data.py` is not manually invoked THEN the system has zero records in all three mock databases (mock_sws, mock_dept_shop, mock_dept_factories)

**Bug 2 — No seed/reset endpoint in mock_proxy.py**

2.1 WHEN the dashboard attempts to trigger seeding via the API THEN the system returns 404 because no `/api/mock/seed` or `/api/mock/reset` endpoint exists in `mock_proxy.py`

2.2 WHEN `combined_app.py` receives a seed/reset request THEN the system has no handler to forward the request to the individual mock apps

**Bug 3 — UBID dropdown incomplete and shows no business names**

3.1 WHEN the Mock Controls page loads THEN the system shows only 15 UBIDs (KA-TEST-0001 to KA-TEST-0015) because the list is hardcoded as `Array.from({ length: 15 }, ...)`

3.2 WHEN a user views the UBID dropdown THEN the system displays only the raw UBID code (e.g. `KA-TEST-0001`) with no business name, making it difficult to identify the correct business during demos

**Bug 4 — Conflict trigger produces no conflicts in the Conflicts tab**

4.1 WHEN `handleConflict` is called and the mock databases are empty THEN the system silently fails — both PUT calls return 404, no change events are emitted to Kafka, and no conflict appears in the Conflicts tab

4.2 WHEN the mock databases are empty and a conflict is triggered THEN the system shows no feedback to the user that the operation failed (no error toast, no 404 indication)

**Bug 5 — Mock Controls page missing action buttons**

5.1 WHEN the Mock Controls page renders THEN the system shows only one action button ("Trigger Simultaneous Conflict"), with no "Seed / Reset Data" button

5.2 WHEN the Mock Controls page renders THEN the system shows no Scenario A, B, or C buttons, even though the corresponding scripts exist in `synckar/scripts/`

---

### Expected Behavior (Correct)

**Bug 1 — Auto-seed on startup**

2.1 WHEN a mock app starts and its SQLite database is empty (zero records) THEN the system SHALL automatically seed all 20 businesses using the dataset defined in `seed_data.py` before serving any requests

2.2 WHEN a mock app starts and its SQLite database already contains records THEN the system SHALL skip seeding and start normally without overwriting existing data

**Bug 2 — Seed/reset endpoints**

2.3 WHEN a POST request is made to `/api/mock/seed` THEN the system SHALL call the batch-create endpoints on all three mock apps and return a summary of records created

2.4 WHEN a POST request is made to `/api/mock/reset` THEN the system SHALL clear all records from all three mock apps and then re-seed them with the full 20-business dataset, returning a summary of the operation

**Bug 3 — Complete UBID dropdown with business names**

2.5 WHEN the Mock Controls page loads THEN the system SHALL display all 20 UBIDs (KA-TEST-0001 to KA-TEST-0020) in the dropdown

2.6 WHEN a user views the UBID dropdown THEN the system SHALL display each entry as `KA-TEST-XXXX — Business Name` so the business is identifiable at a glance

**Bug 4 — Conflict trigger produces visible conflicts**

2.7 WHEN `handleConflict` is called and the selected UBID exists in both SWS and Factories THEN the system SHALL emit two simultaneous change events that SyncKar detects as a conflict, which SHALL appear in the Conflicts tab within the normal propagation window

2.8 WHEN `handleConflict` is called and either PUT call returns a non-2xx status THEN the system SHALL display an error toast indicating the conflict trigger failed and suggesting the user seed data first

**Bug 5 — Full set of action buttons**

2.9 WHEN the Mock Controls page renders THEN the system SHALL display a "Seed / Reset Data" button that calls the `/api/mock/seed` endpoint and shows a success or error toast

2.10 WHEN the Mock Controls page renders THEN the system SHALL display three scenario buttons — "Scenario A: SWS → Dept", "Scenario B: Dept → SWS", and "Scenario C: Conflict" — that trigger the corresponding demo flows via the API

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a mock app starts and its database already has records THEN the system SHALL CONTINUE TO serve existing records without modification (no overwrite on non-empty DB)

3.2 WHEN a user selects a UBID and clicks "Update [System]" THEN the system SHALL CONTINUE TO send a PUT request to the correct mock system and display a success toast on 2xx response

3.3 WHEN a user navigates between dashboard tabs (Overview, Audit Trail, Conflicts, DLQ, BSA Verify) THEN the system SHALL CONTINUE TO fetch and display data from the existing API endpoints without regression

3.4 WHEN the mock proxy forwards GET/PUT requests to `/api/mock/{system}/record/{ubid}` THEN the system SHALL CONTINUE TO proxy those requests to the correct mock system base URL

3.5 WHEN the three mock apps (mock_sws, mock_dept_shop, mock_dept_factories) receive batch-create requests THEN the system SHALL CONTINUE TO use `INSERT OR REPLACE` semantics so re-seeding is idempotent

3.6 WHEN the combined_app.py mounts the three sub-apps under `/sws`, `/shop`, and `/factories` THEN the system SHALL CONTINUE TO route requests to the correct sub-app without path conflicts

3.7 WHEN UBIDs KA-TEST-0016 to KA-TEST-0018 are looked up in the Factories system THEN the system SHALL CONTINUE TO return 404 (these businesses are SWS + Shop only by design)

3.8 WHEN UBIDs KA-TEST-0019 to KA-TEST-0020 are looked up in Shop or Factories THEN the system SHALL CONTINUE TO return 404 (these businesses are SWS only by design)
