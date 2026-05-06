# Mock Controls Fix Bugfix Design

## Overview

The SyncKar mock controls system has five interconnected bugs that collectively make the demo environment non-functional on a fresh deploy. This design addresses all five bugs using a coordinated fix strategy:

1. **Bug 1 — Auto-seed on startup**: Each mock app checks if its database is empty on startup and seeds itself with the full 20-business dataset inline
2. **Bug 2 — Seed/reset endpoints**: Add `/api/mock/seed` and `/api/mock/reset` endpoints to `mock_proxy.py` that call batch-create on all three systems
3. **Bug 3 — Complete UBID dropdown with business names**: Replace the hardcoded 15-UBID array with a static 20-UBID list that includes business names
4. **Bug 4 — Conflict trigger error handling**: Check PUT response status and show an error toast if either call returns non-2xx
5. **Bug 5 — New action buttons**: Add "Seed Data", "Reset & Reseed", and three scenario buttons to the Mock Controls page

The fix strategy is minimal and targeted: embed seed data directly in each file (no new imports), use existing batch endpoints, and add error feedback to the UI. All fixes preserve existing behavior for non-empty databases and existing API routes.

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug — empty databases, missing endpoints, incomplete UBID list, silent 404 failures, missing UI buttons
- **Property (P)**: The desired behavior when the bug condition holds — auto-seed on empty DB, seed/reset endpoints available, full UBID list with names, error toast on 404, all action buttons present
- **Preservation**: Existing behavior that must remain unchanged — non-empty DB not overwritten, existing GET/PUT proxying, existing update flows, existing batch endpoints
- **auto_seed()**: Function called after `init_db()` in each mock app that checks if the table is empty and seeds it if so
- **SEED_BUSINESSES**: Module-level constant in `mock_proxy.py` containing all 20 businesses for seed/reset endpoints
- **UBID_LIST**: Static constant in `App.jsx` containing all 20 UBIDs with business names for the dropdown
- **handleConflict**: Function in `App.jsx` that triggers simultaneous SWS + Factories updates to demonstrate conflict resolution

## Bug Details

### Bug Condition

The bugs manifest in five distinct scenarios:

**Bug 1 — Mock systems start empty**

The bug manifests when a fresh container starts or the SQLite DB is new/empty. The `init_db()` function creates tables but does not populate them, so all UBID lookups return 404.

**Formal Specification:**
```
FUNCTION isBugCondition_Bug1(dbState)
  INPUT: dbState of type DatabaseState
  OUTPUT: boolean
  
  RETURN dbState.tableExists('businesses' OR 'records')
         AND dbState.rowCount('businesses' OR 'records') == 0
         AND NOT auto_seed_called()
END FUNCTION
```

**Bug 2 — No seed/reset endpoint in mock_proxy.py**

The bug manifests when the dashboard attempts to trigger seeding via the API. The `mock_proxy.py` router has no `/api/mock/seed` or `/api/mock/reset` endpoint, so requests return 404.

**Formal Specification:**
```
FUNCTION isBugCondition_Bug2(request)
  INPUT: request of type HTTPRequest
  OUTPUT: boolean
  
  RETURN request.path IN ['/api/mock/seed', '/api/mock/reset']
         AND NOT endpoint_exists(request.path)
END FUNCTION
```

**Bug 3 — UBID dropdown incomplete and shows no business names**

The bug manifests when the Mock Controls page loads. The `UBIDS` array is hardcoded as `Array.from({ length: 15 }, ...)` and contains only raw UBID strings, not business names.

**Formal Specification:**
```
FUNCTION isBugCondition_Bug3(ubidList)
  INPUT: ubidList of type Array<string | object>
  OUTPUT: boolean
  
  RETURN ubidList.length < 20
         OR NOT ubidList[0].hasOwnProperty('name')
END FUNCTION
```

**Bug 4 — Conflict trigger produces no conflicts**

The bug manifests when `handleConflict` is called and the mock databases are empty. Both PUT calls return 404, no change events are emitted to Kafka, and no conflict appears in the Conflicts tab. The user sees no feedback that the operation failed.

**Formal Specification:**
```
FUNCTION isBugCondition_Bug4(response1, response2)
  INPUT: response1, response2 of type HTTPResponse
  OUTPUT: boolean
  
  RETURN (response1.status NOT IN [200, 201, 204]
         OR response2.status NOT IN [200, 201, 204])
         AND NOT error_toast_shown()
END FUNCTION
```

**Bug 5 — Mock Controls page missing action buttons**

The bug manifests when the Mock Controls page renders. Only one action button ("Trigger Simultaneous Conflict") is present, with no "Seed / Reset Data" button or Scenario A/B/C buttons.

**Formal Specification:**
```
FUNCTION isBugCondition_Bug5(buttonList)
  INPUT: buttonList of type Array<Button>
  OUTPUT: boolean
  
  RETURN NOT buttonList.includes('Seed Data')
         OR NOT buttonList.includes('Reset & Reseed')
         OR NOT buttonList.includes('Scenario A')
         OR NOT buttonList.includes('Scenario B')
         OR NOT buttonList.includes('Scenario C')
END FUNCTION
```

### Examples

**Bug 1 Examples:**
- Fresh deploy: `docker-compose up` → all UBID lookups return 404 → "Record not found" in dashboard
- Empty DB: `rm /tmp/mock_sws.db && restart` → SWS has zero records → auto-seed should run but doesn't
- Non-empty DB: DB has 5 records → auto-seed should skip → existing records preserved ✅

**Bug 2 Examples:**
- Dashboard calls `POST /api/mock/seed` → 404 because endpoint doesn't exist
- Dashboard calls `POST /api/mock/reset` → 404 because endpoint doesn't exist
- Existing proxy routes like `GET /api/mock/sws/record/KA-TEST-0001` → continue to work ✅

**Bug 3 Examples:**
- Dropdown shows 15 UBIDs (KA-TEST-0001 to KA-TEST-0015) → missing KA-TEST-0016 to KA-TEST-0020
- Dropdown shows "KA-TEST-0001" → no business name → user can't identify business at a glance
- Expected: "KA-TEST-0001 — Bengaluru Silk Weavers Pvt Ltd"

**Bug 4 Examples:**
- Empty DB + click "Trigger Simultaneous Conflict" → both PUTs return 404 → no error toast → user confused
- Non-empty DB + click "Trigger Simultaneous Conflict" → both PUTs return 200 → conflict appears in Conflicts tab ✅
- Expected: 404 → error toast "❌ Conflict trigger failed (404) — databases may be empty. Click 'Seed Data' first."

**Bug 5 Examples:**
- Mock Controls page renders → only "Trigger Simultaneous Conflict" button visible
- Expected: "Seed Data", "Reset & Reseed", "Scenario A", "Scenario B", "Scenario C" buttons also visible

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Non-empty databases must not be overwritten on startup (auto-seed checks row count first)
- Existing GET/PUT proxy routes must continue to work exactly as before
- Existing update flows (user clicks "Update [System]") must continue to send PUT requests and show success toasts
- Existing batch endpoints must continue to use `INSERT OR REPLACE` semantics (idempotent)
- Existing sub-app mounting in `combined_app.py` must continue to route requests correctly
- UBIDs KA-TEST-0016 to KA-TEST-0018 must continue to return 404 in Factories (by design)
- UBIDs KA-TEST-0019 to KA-TEST-0020 must continue to return 404 in Shop and Factories (by design)
- Dashboard tab navigation must continue to fetch and display data without regression

**Scope:**
All inputs that do NOT involve empty databases, missing endpoints, or the new action buttons should be completely unaffected by this fix. This includes:
- Existing UBID lookups on non-empty databases
- Existing update operations via the dashboard
- Existing polling and change detection flows
- Existing conflict resolution logic

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Missing auto-seed logic**: The `init_db()` function in each mock app creates tables but does not check if they are empty or seed them. The `seed_data.py` script exists but is a standalone script, not a module that can be imported.

2. **Missing proxy endpoints**: The `mock_proxy.py` router only has GET/PUT routes for individual records. No POST routes exist for batch seeding or resetting all systems at once.

3. **Hardcoded incomplete UBID list**: The `UBIDS` array in `App.jsx` is generated as `Array.from({ length: 15 }, ...)` and contains only raw UBID strings. The full 20-business list with names is only in `seed_data.py`, which is not imported by the dashboard.

4. **Missing error handling in handleConflict**: The `handleConflict` function calls `Promise.all([...])` but does not check the response status of either PUT call. If either returns 404, the function silently fails with no user feedback.

5. **Incomplete UI implementation**: The Mock Controls page was designed with only the conflict trigger button. The seed/reset buttons and scenario buttons were never implemented, even though the corresponding backend scripts exist.

## Correctness Properties

Property 1: Bug Condition — Auto-seed on empty database

_For any_ mock app startup where the database table exists but has zero rows (isBugCondition_Bug1 returns true), the fixed app SHALL automatically seed the table with the full 20-business dataset (or 18 for Shop, 15 for Factories) before serving any requests, ensuring all UBID lookups succeed.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition — Seed/reset endpoints available

_For any_ POST request to `/api/mock/seed` or `/api/mock/reset` (isBugCondition_Bug2 returns true), the fixed mock_proxy.py SHALL handle the request by calling batch-create on all three mock systems and returning a summary of records created, ensuring the dashboard can trigger seeding without manual script execution.

**Validates: Requirements 2.3, 2.4**

Property 3: Bug Condition — Complete UBID dropdown with business names

_For any_ Mock Controls page load where the UBID dropdown is rendered (isBugCondition_Bug3 returns true), the fixed App.jsx SHALL display all 20 UBIDs in the format `KA-TEST-XXXX — Business Name`, ensuring users can identify businesses at a glance.

**Validates: Requirements 2.5, 2.6**

Property 4: Bug Condition — Conflict trigger error handling

_For any_ conflict trigger where either PUT call returns a non-2xx status (isBugCondition_Bug4 returns true), the fixed handleConflict function SHALL display an error toast indicating the conflict trigger failed and suggesting the user seed data first, ensuring users receive feedback when the operation fails.

**Validates: Requirements 2.7, 2.8**

Property 5: Bug Condition — Full set of action buttons

_For any_ Mock Controls page render (isBugCondition_Bug5 returns true), the fixed App.jsx SHALL display all five action buttons ("Seed Data", "Reset & Reseed", "Scenario A", "Scenario B", "Scenario C"), ensuring users can trigger all demo flows from the UI.

**Validates: Requirements 2.9, 2.10**

Property 6: Preservation — Non-empty database not overwritten

_For any_ mock app startup where the database table has one or more rows (isBugCondition_Bug1 returns false), the fixed app SHALL skip auto-seeding and serve existing records without modification, preserving all existing data.

**Validates: Requirements 3.1**

Property 7: Preservation — Existing update flows unchanged

_For any_ user action that selects a UBID and clicks "Update [System]" (non-bug condition), the fixed App.jsx SHALL continue to send a PUT request to the correct mock system and display a success toast on 2xx response, preserving the existing update flow.

**Validates: Requirements 3.2**

Property 8: Preservation — Dashboard navigation unchanged

_For any_ user navigation between dashboard tabs (Overview, Audit Trail, Conflicts, DLQ, BSA Verify), the fixed App.jsx SHALL continue to fetch and display data from the existing API endpoints without regression, preserving all existing dashboard functionality.

**Validates: Requirements 3.3**

Property 9: Preservation — Existing proxy routes unchanged

_For any_ GET/PUT request to `/api/mock/{system}/record/{ubid}` (non-bug condition), the fixed mock_proxy.py SHALL continue to proxy those requests to the correct mock system base URL, preserving the existing proxy behavior.

**Validates: Requirements 3.4**

Property 10: Preservation — Batch endpoints remain idempotent

_For any_ batch-create request to the three mock apps (non-bug condition), the fixed apps SHALL continue to use `INSERT OR REPLACE` semantics so re-seeding is idempotent, preserving the existing batch behavior.

**Validates: Requirements 3.5**

Property 11: Preservation — Sub-app mounting unchanged

_For any_ request to `/sws`, `/shop`, or `/factories` in combined_app.py (non-bug condition), the fixed combined_app.py SHALL continue to route requests to the correct sub-app without path conflicts, preserving the existing routing behavior.

**Validates: Requirements 3.6**

Property 12: Preservation — Designed 404s for partial coverage

_For any_ UBID lookup where the UBID is intentionally not present in a system (KA-TEST-0016 to KA-TEST-0018 in Factories, KA-TEST-0019 to KA-TEST-0020 in Shop and Factories), the fixed apps SHALL continue to return 404, preserving the designed partial coverage behavior.

**Validates: Requirements 3.7, 3.8**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File 1**: `synckar/mock_systems/mock_sws/app.py`

**Function**: `auto_seed()` (new function)

**Specific Changes**:
1. **Add SEED_BUSINESSES constant**: Embed the full 20-business list from `seed_data.py` as a module-level constant (list of dicts with all SWS fields)
   - Copy the `BUSINESSES` list from `seed_data.py` and rename to `SEED_BUSINESSES`
   - Include all 20 businesses with all fields (ubid, business_name, registered_address, etc.)

2. **Add auto_seed() function**: Check if the `businesses` table is empty and seed it if so
   - Query `SELECT COUNT(*) FROM businesses`
   - If count == 0, insert all 20 businesses using the existing batch-create logic
   - Use `INSERT OR REPLACE` to ensure idempotency
   - Log the seeding action for debugging

3. **Call auto_seed() after init_db()**: Add `auto_seed()` call immediately after `init_db()` at module level
   - Ensures seeding happens before any requests are served
   - Only runs once per container startup

**File 2**: `synckar/mock_systems/mock_dept_shop/app.py`

**Function**: `auto_seed()` (new function)

**Specific Changes**:
1. **Add SEED_SHOP_RECORDS constant**: Embed the 18 Shop records from `seed_data.py` as a module-level constant
   - Copy the Shop record transformation logic from `seed_data.py` (first 18 businesses)
   - Include all Shop fields (shop_reg_no, ubid, business_name, Buss_Addr_Line1, etc.)

2. **Add auto_seed() function**: Check if the `records` table is empty and seed it if so
   - Query `SELECT COUNT(*) FROM records`
   - If count == 0, insert all 18 records using the existing batch-create logic
   - Use `INSERT OR REPLACE` to ensure idempotency

3. **Call auto_seed() after init_db()**: Add `auto_seed()` call immediately after `init_db()` at module level

**File 3**: `synckar/mock_systems/mock_dept_factories/app.py`

**Function**: `auto_seed()` (new function)

**Specific Changes**:
1. **Add SEED_FACTORY_RECORDS constant**: Embed the 15 Factories records from `seed_data.py` as a module-level constant
   - Copy the Factories record transformation logic from `seed_data.py` (first 15 businesses)
   - Include all Factories fields (factory_license_no, ubid, business_name, factory_address, etc.)

2. **Add auto_seed() function**: Check if the `records` table is empty and seed it if so
   - Query `SELECT COUNT(*) FROM records`
   - If count == 0, insert all 15 records using the existing batch-create logic
   - Use `INSERT OR REPLACE` to ensure idempotency

3. **Call auto_seed() after init_db()**: Add `auto_seed()` call immediately after `init_db()` at module level

**File 4**: `synckar/synckar/api/routes/mock_proxy.py`

**Function**: `seed_all()` and `reset_all()` (new endpoints)

**Specific Changes**:
1. **Add SEED_BUSINESSES constant**: Embed the full 20-business list as a module-level constant
   - Same list as in `mock_sws/app.py`
   - Used to construct batch-create payloads for all three systems

2. **Add POST /api/mock/seed endpoint**: Call batch-create on all three systems
   - Transform SEED_BUSINESSES into SWS format (all 20)
   - Transform SEED_BUSINESSES into Shop format (first 18)
   - Transform SEED_BUSINESSES into Factories format (first 15)
   - Call `POST {base_url}/api/businesses/batch` for SWS
   - Call `POST {base_url}/api/records/batch` for Shop
   - Call `POST {base_url}/api/records/batch` for Factories
   - Return summary: `{"sws": 20, "shop": 18, "factories": 15}`

3. **Add POST /api/mock/reset endpoint**: Clear all records, then call seed
   - Call `DELETE {base_url}/api/businesses/all` for SWS
   - Call `DELETE {base_url}/api/records/all` for Shop
   - Call `DELETE {base_url}/api/records/all` for Factories
   - Then call the same batch-create logic as `/api/mock/seed`
   - Return summary: `{"cleared": true, "seeded": {"sws": 20, "shop": 18, "factories": 15}}`

**File 5**: `synckar/dashboard/src/App.jsx`

**Function**: `MockSystemsPage` component

**Specific Changes**:
1. **Replace UBIDS array with UBID_LIST constant**: Define a static constant with all 20 UBIDs and business names
   - Format: `const UBID_LIST = [{ ubid: 'KA-TEST-0001', name: 'Bengaluru Silk Weavers Pvt Ltd' }, ...]`
   - Include all 20 businesses from `seed_data.py`
   - Update dropdown to map over `UBID_LIST` and display `${u.ubid} — ${u.name}`
   - Update `selectedUbid` state to store just the UBID string (no change to state structure)

2. **Add error handling to handleConflict**: Check response status of both PUT calls
   - Await both PUT calls individually (not `Promise.all`) to check status
   - If either `res.status` is not in [200, 201, 204], show error toast: "❌ Conflict trigger failed (404) — databases may be empty. Click 'Seed Data' first."
   - If both succeed, show existing success toast

3. **Add handleSeed function**: Call `POST /api/mock/seed` and show success/error toast
   - Fetch `${API_BASE}/api/mock/seed` with method POST
   - On success, show toast: "✅ Data seeded — all 20 businesses loaded"
   - On error, show toast: "❌ Seed failed: {error message}"

4. **Add handleReset function**: Call `POST /api/mock/reset` and show success/error toast
   - Fetch `${API_BASE}/api/mock/reset` with method POST
   - On success, show toast: "✅ Data reset & reseeded — all systems cleared and reloaded"
   - On error, show toast: "❌ Reset failed: {error message}"
   - After success, refresh all three records by calling `fetchRecord` for each system

5. **Add handleScenarioA function**: Update registered_address in SWS for selected UBID
   - Construct body: `{ registered_address: "${Date.now()} Scenario A Street, Bangalore 560001" }`
   - Call `PUT /api/mock/sws/record/${selectedUbid}` with body
   - Show toast: "📤 Scenario A triggered — SWS address updated, propagating to departments..."

6. **Add handleScenarioB function**: Update Buss_Addr_Line1 in Shop for selected UBID
   - Construct body: `{ Buss_Addr_Line1: "${Date.now()} Scenario B Road, Bangalore 560002" }`
   - Call `PUT /api/mock/shop/record/${selectedUbid}` with body
   - Show toast: "📥 Scenario B triggered — Shop address updated, propagating to SWS..."

7. **Add handleScenarioC function**: Same as existing handleConflict (simultaneous SWS + Factories update)
   - Reuse existing handleConflict logic
   - Show toast: "⚔️ Scenario C triggered — simultaneous conflict, watch Conflicts tab..."

8. **Add five new buttons to mock-controls-right div**:
   - "🌱 Seed Data" button → calls `handleSeed`
   - "🔄 Reset & Reseed" button → calls `handleReset`
   - "📤 Scenario A: SWS→Dept" button → calls `handleScenarioA`
   - "📥 Scenario B: Dept→SWS" button → calls `handleScenarioB`
   - "⚔️ Scenario C: Conflict" button → calls `handleScenarioC`
   - Keep existing "Trigger Simultaneous Conflict" button for backward compatibility

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate fresh container startup, empty databases, missing endpoints, incomplete UBID lists, and missing buttons. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Bug 1 — Empty DB Test**: Start a mock app with an empty SQLite DB, query for any UBID (will fail on unfixed code with 404)
2. **Bug 2 — Missing Endpoint Test**: Call `POST /api/mock/seed` (will fail on unfixed code with 404)
3. **Bug 3 — Incomplete UBID List Test**: Load Mock Controls page, count dropdown options (will fail on unfixed code with 15 instead of 20)
4. **Bug 4 — Silent 404 Test**: Trigger conflict with empty DB, observe no error toast (will fail on unfixed code with silent failure)
5. **Bug 5 — Missing Buttons Test**: Load Mock Controls page, count action buttons (will fail on unfixed code with 1 instead of 6)

**Expected Counterexamples**:
- Empty DB → all UBID lookups return 404
- POST /api/mock/seed → 404 because endpoint doesn't exist
- UBID dropdown → only 15 options, no business names
- Conflict trigger with empty DB → no error toast, no feedback
- Mock Controls page → only 1 action button visible

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition_Bug1(input) DO
  result := auto_seed(input)
  ASSERT result.rowCount > 0
  ASSERT result.ubidLookup('KA-TEST-0001').status == 200
END FOR

FOR ALL input WHERE isBugCondition_Bug2(input) DO
  result := seed_all() OR reset_all()
  ASSERT result.status == 200
  ASSERT result.summary.sws == 20
  ASSERT result.summary.shop == 18
  ASSERT result.summary.factories == 15
END FOR

FOR ALL input WHERE isBugCondition_Bug3(input) DO
  result := UBID_LIST
  ASSERT result.length == 20
  ASSERT result[0].hasOwnProperty('name')
END FOR

FOR ALL input WHERE isBugCondition_Bug4(input) DO
  result := handleConflict_fixed(input)
  ASSERT result.errorToastShown == true
  ASSERT result.errorMessage.includes('404')
END FOR

FOR ALL input WHERE isBugCondition_Bug5(input) DO
  result := MockSystemsPage_fixed()
  ASSERT result.buttons.includes('Seed Data')
  ASSERT result.buttons.includes('Reset & Reseed')
  ASSERT result.buttons.includes('Scenario A')
  ASSERT result.buttons.includes('Scenario B')
  ASSERT result.buttons.includes('Scenario C')
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition_Bug1(input) DO
  ASSERT auto_seed_skipped(input) == true
  ASSERT existingRecords(input) == existingRecords_original(input)
END FOR

FOR ALL input WHERE NOT isBugCondition_Bug2(input) DO
  ASSERT proxy_route(input) == proxy_route_original(input)
END FOR

FOR ALL input WHERE NOT isBugCondition_Bug3(input) DO
  ASSERT selectedUbid_state(input) == selectedUbid_state_original(input)
END FOR

FOR ALL input WHERE NOT isBugCondition_Bug4(input) DO
  ASSERT handleConflict_success(input) == handleConflict_success_original(input)
END FOR

FOR ALL input WHERE NOT isBugCondition_Bug5(input) DO
  ASSERT existing_button_behavior(input) == existing_button_behavior_original(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-empty databases, existing proxy routes, and existing update flows, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Non-empty DB Preservation**: Start mock app with 5 existing records, verify auto-seed skips and records unchanged
2. **Existing Proxy Route Preservation**: Call `GET /api/mock/sws/record/KA-TEST-0001` on non-empty DB, verify response unchanged
3. **Existing Update Flow Preservation**: Click "Update SWS" with valid data, verify PUT request sent and success toast shown
4. **Existing Batch Endpoint Preservation**: Call batch-create twice with same data, verify idempotency (INSERT OR REPLACE)
5. **Existing Sub-app Mounting Preservation**: Call `/sws/health`, `/shop/health`, `/factories/health`, verify routing unchanged
6. **Designed 404 Preservation**: Query KA-TEST-0019 in Shop, verify 404 returned (by design)

### Unit Tests

- Test `auto_seed()` function in each mock app with empty DB (should seed) and non-empty DB (should skip)
- Test `POST /api/mock/seed` endpoint with all three systems reachable (should return summary)
- Test `POST /api/mock/reset` endpoint with all three systems reachable (should clear and reseed)
- Test UBID_LIST constant has 20 entries and each has `ubid` and `name` properties
- Test `handleConflict` with 404 response (should show error toast) and 200 response (should show success toast)
- Test each new button click handler (handleSeed, handleReset, handleScenarioA, handleScenarioB, handleScenarioC)

### Property-Based Tests

- Generate random database states (empty, non-empty, partially filled) and verify auto-seed behavior is correct
- Generate random UBID selections and verify dropdown displays correct business name
- Generate random conflict trigger scenarios (empty DB, non-empty DB, partial coverage) and verify error handling
- Generate random button click sequences and verify all handlers are called correctly

### Integration Tests

- Test full flow: fresh deploy → auto-seed → UBID lookup succeeds
- Test full flow: click "Seed Data" → all three systems seeded → UBID lookup succeeds
- Test full flow: click "Reset & Reseed" → all systems cleared and reseeded → UBID lookup succeeds
- Test full flow: select UBID → click "Scenario A" → SWS updated → propagation to departments
- Test full flow: select UBID → click "Scenario B" → Shop updated → propagation to SWS
- Test full flow: select UBID → click "Scenario C" → conflict detected → appears in Conflicts tab
- Test full flow: empty DB → click "Trigger Simultaneous Conflict" → error toast shown
