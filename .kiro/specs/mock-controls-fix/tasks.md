# Implementation Plan

## Bug 1: Auto-seed on startup (mock apps)

- [ ] 1. Write bug condition exploration test for Bug 1
  - **Property 1: Bug Condition** - Empty Database Auto-Seed
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate empty databases return 404 for all UBID lookups
  - **Scoped PBT Approach**: Test with a fresh empty SQLite database (delete DB file before test)
  - Test that GET /api/businesses/KA-TEST-0001 returns 404 on mock_sws with empty DB
  - Test that GET /api/records/by-ubid/KA-TEST-0001 returns 404 on mock_dept_shop with empty DB
  - Test that GET /api/records/by-ubid/KA-TEST-0001 returns 404 on mock_dept_factories with empty DB
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Empty DB → all UBID lookups return 404 instead of auto-seeding")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [ ] 2. Write preservation property tests for Bug 1 (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Empty Database Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: start mock app with 5 existing records, verify records are served without modification
  - Write property-based test: for all non-empty databases (row count > 0), existing records must be preserved and served correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1_

- [-] 3. Implement auto-seed for all three mock apps

  - [x] 3.1 Add auto_seed() to mock_sws/app.py
    - Add SEED_BUSINESSES constant with all 20 businesses from seed_data.py
    - Add auto_seed() function that checks if businesses table is empty (COUNT(*) == 0)
    - If empty, insert all 20 businesses using INSERT OR REPLACE
    - Call auto_seed() immediately after init_db() at module level
    - Log seeding action for debugging
    - _Bug_Condition: isBugCondition_Bug1(dbState) where dbState.rowCount == 0_
    - _Expected_Behavior: All 20 UBID lookups succeed after auto-seed_
    - _Preservation: Non-empty DB skips auto-seed, existing records unchanged_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1_

  - [x] 3.2 Add auto_seed() to mock_dept_shop/app.py
    - Add SEED_SHOP_RECORDS constant with 18 Shop records (KA-TEST-0001 to KA-TEST-0018)
    - Add auto_seed() function that checks if records table is empty
    - If empty, insert all 18 records using INSERT OR REPLACE
    - Call auto_seed() immediately after init_db() at module level
    - _Bug_Condition: isBugCondition_Bug1(dbState) where dbState.rowCount == 0_
    - _Expected_Behavior: 18 UBID lookups succeed after auto-seed_
    - _Preservation: Non-empty DB skips auto-seed, existing records unchanged_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1_

  - [x] 3.3 Add auto_seed() to mock_dept_factories/app.py
    - Add SEED_FACTORY_RECORDS constant with 15 Factories records (KA-TEST-0001 to KA-TEST-0015)
    - Add auto_seed() function that checks if records table is empty
    - If empty, insert all 15 records using INSERT OR REPLACE
    - Call auto_seed() immediately after init_db() at module level
    - _Bug_Condition: isBugCondition_Bug1(dbState) where dbState.rowCount == 0_
    - _Expected_Behavior: 15 UBID lookups succeed after auto-seed_
    - _Preservation: Non-empty DB skips auto-seed, existing records unchanged_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1_

  - [ ] 3.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Empty Database Auto-Seed
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [ ] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Empty Database Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 4. Checkpoint - Ensure Bug 1 tests pass
  - Ensure all Bug 1 tests pass, ask the user if questions arise.

---

## Bug 2: Seed/reset endpoints in mock_proxy.py

- [ ] 5. Write bug condition exploration test for Bug 2
  - **Property 1: Bug Condition** - Missing Seed/Reset Endpoints
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate missing endpoints return 404
  - **Scoped PBT Approach**: Test POST requests to /api/mock/seed and /api/mock/reset
  - Test that POST /api/mock/seed returns 404 on unfixed mock_proxy.py
  - Test that POST /api/mock/reset returns 404 on unfixed mock_proxy.py
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "POST /api/mock/seed → 404 because endpoint doesn't exist")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1_

- [ ] 6. Write preservation property tests for Bug 2 (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Proxy Routes Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: GET /api/mock/sws/record/KA-TEST-0001 returns record data
  - Write property-based test: for all existing GET/PUT proxy routes, requests must be forwarded correctly to mock systems
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.3, 3.4_

- [-] 7. Implement seed/reset endpoints in mock_proxy.py

  - [x] 7.1 Add SEED_BUSINESSES constant to mock_proxy.py
    - Copy the full 20-business list from seed_data.py
    - Use this constant to construct batch-create payloads for all three systems
    - _Bug_Condition: isBugCondition_Bug2(request) where request.path == '/api/mock/seed'_
    - _Expected_Behavior: Endpoint exists and returns summary of records created_
    - _Preservation: Existing GET/PUT proxy routes unchanged_
    - _Requirements: 2.1, 2.3, 2.4, 3.4_

  - [x] 7.2 Add POST /api/mock/seed endpoint
    - Transform SEED_BUSINESSES into SWS format (all 20)
    - Transform SEED_BUSINESSES into Shop format (first 18)
    - Transform SEED_BUSINESSES into Factories format (first 15)
    - Call POST {base_url}/api/businesses/batch for SWS
    - Call POST {base_url}/api/records/batch for Shop
    - Call POST {base_url}/api/records/batch for Factories
    - Return summary: {"sws": 20, "shop": 18, "factories": 15}
    - _Bug_Condition: isBugCondition_Bug2(request) where request.path == '/api/mock/seed'_
    - _Expected_Behavior: All three systems seeded with correct record counts_
    - _Preservation: Existing proxy routes unchanged_
    - _Requirements: 2.1, 2.3, 3.4_

  - [x] 7.3 Add POST /api/mock/reset endpoint
    - Call DELETE {base_url}/api/businesses/all for SWS
    - Call DELETE {base_url}/api/records/all for Shop
    - Call DELETE {base_url}/api/records/all for Factories
    - Then call the same batch-create logic as /api/mock/seed
    - Return summary: {"cleared": true, "seeded": {"sws": 20, "shop": 18, "factories": 15}}
    - _Bug_Condition: isBugCondition_Bug2(request) where request.path == '/api/mock/reset'_
    - _Expected_Behavior: All systems cleared and reseeded_
    - _Preservation: Existing proxy routes unchanged_
    - _Requirements: 2.1, 2.4, 3.4_

  - [ ] 7.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Seed/Reset Endpoints Available
    - **IMPORTANT**: Re-run the SAME test from task 5 - do NOT write a new test
    - The test from task 5 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 5
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.3, 2.4_

  - [ ] 7.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Proxy Routes Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 6 - do NOT write new tests
    - Run preservation property tests from step 6
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 8. Checkpoint - Ensure Bug 2 tests pass
  - Ensure all Bug 2 tests pass, ask the user if questions arise.

---

## Bug 3: Complete UBID dropdown with business names

- [ ] 9. Write bug condition exploration test for Bug 3
  - **Property 1: Bug Condition** - Incomplete UBID Dropdown
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate incomplete UBID list and missing business names
  - **Scoped PBT Approach**: Test the UBIDS constant in App.jsx
  - Test that UBIDS array has length < 20 on unfixed code
  - Test that UBIDS array contains only raw strings (no business names) on unfixed code
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "UBIDS.length == 15 instead of 20, no business names")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 3.1, 3.2_

- [ ] 10. Write preservation property tests for Bug 3 (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Update Flows Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: select UBID → click "Update SWS" → PUT request sent and success toast shown
  - Write property-based test: for all UBID selections and update operations, existing flows must work correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.2_

- [-] 11. Implement complete UBID dropdown with business names in App.jsx

  - [x] 11.1 Replace UBIDS array with UBID_LIST constant
    - Define static constant with all 20 UBIDs and business names
    - Format: const UBID_LIST = [{ ubid: 'KA-TEST-0001', name: 'Bengaluru Silk Weavers Pvt Ltd' }, ...]
    - Include all 20 businesses from seed_data.py
    - Update dropdown to map over UBID_LIST and display `${u.ubid} — ${u.name}`
    - Update selectedUbid state to store just the UBID string (no change to state structure)
    - _Bug_Condition: isBugCondition_Bug3(ubidList) where ubidList.length < 20_
    - _Expected_Behavior: All 20 UBIDs displayed with business names_
    - _Preservation: Existing update flows unchanged_
    - _Requirements: 3.1, 3.2, 2.5, 2.6, 3.2_

  - [ ] 11.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Complete UBID Dropdown
    - **IMPORTANT**: Re-run the SAME test from task 9 - do NOT write a new test
    - The test from task 9 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 9
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.5, 2.6_

  - [ ] 11.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Update Flows Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 10 - do NOT write new tests
    - Run preservation property tests from step 10
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 12. Checkpoint - Ensure Bug 3 tests pass
  - Ensure all Bug 3 tests pass, ask the user if questions arise.

---

## Bug 4: Conflict trigger error handling

- [ ] 13. Write bug condition exploration test for Bug 4
  - **Property 1: Bug Condition** - Silent Conflict Trigger Failure
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate silent 404 failures with no user feedback
  - **Scoped PBT Approach**: Test handleConflict with empty databases (both PUTs return 404)
  - Test that handleConflict with empty DB shows no error toast on unfixed code
  - Test that both PUT calls return 404 but no error feedback is shown
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Empty DB + conflict trigger → both PUTs return 404 → no error toast")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 4.1, 4.2_

- [ ] 14. Write preservation property tests for Bug 4 (BEFORE implementing fix)
  - **Property 2: Preservation** - Successful Conflict Trigger Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: non-empty DB + conflict trigger → both PUTs return 200 → success toast shown
  - Write property-based test: for all successful conflict triggers (both PUTs return 2xx), existing success flow must work correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.2_

- [-] 15. Implement error handling for handleConflict in App.jsx

  - [x] 15.1 Add error handling to handleConflict
    - Await both PUT calls individually (not Promise.all) to check status
    - If either res.status is not in [200, 201, 204], show error toast
    - Error toast message: "❌ Conflict trigger failed (404) — databases may be empty. Click 'Seed Data' first."
    - If both succeed, show existing success toast
    - _Bug_Condition: isBugCondition_Bug4(response1, response2) where either status is not 2xx_
    - _Expected_Behavior: Error toast shown when either PUT fails_
    - _Preservation: Successful conflict trigger unchanged_
    - _Requirements: 4.1, 4.2, 2.7, 2.8, 3.2_

  - [ ] 15.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Conflict Trigger Error Handling
    - **IMPORTANT**: Re-run the SAME test from task 13 - do NOT write a new test
    - The test from task 13 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 13
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.7, 2.8_

  - [ ] 15.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Successful Conflict Trigger Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 14 - do NOT write new tests
    - Run preservation property tests from step 14
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 16. Checkpoint - Ensure Bug 4 tests pass
  - Ensure all Bug 4 tests pass, ask the user if questions arise.

---

## Bug 5: Add action buttons to Mock Controls page

- [ ] 17. Write bug condition exploration test for Bug 5
  - **Property 1: Bug Condition** - Missing Action Buttons
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate missing action buttons
  - **Scoped PBT Approach**: Test the Mock Controls page button list
  - Test that only 1 action button is visible on unfixed code (only "Trigger Simultaneous Conflict")
  - Test that "Seed Data", "Reset & Reseed", "Scenario A", "Scenario B", "Scenario C" buttons are missing
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Only 1 button visible instead of 6")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 5.1, 5.2_

- [ ] 18. Write preservation property tests for Bug 5 (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Button Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: click "Trigger Simultaneous Conflict" → handleConflict called
  - Write property-based test: for all existing button clicks, existing handlers must be called correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.2_

- [-] 19. Implement action buttons in App.jsx

  - [x] 19.1 Add handleSeed function
    - Call POST /api/mock/seed
    - On success, show toast: "✅ Data seeded — all 20 businesses loaded"
    - On error, show toast: "❌ Seed failed: {error message}"
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where 'Seed Data' not in buttonList_
    - _Expected_Behavior: Seed Data button visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.9, 3.2_

  - [x] 19.2 Add handleReset function
    - Call POST /api/mock/reset
    - On success, show toast: "✅ Data reset & reseeded — all systems cleared and reloaded"
    - On error, show toast: "❌ Reset failed: {error message}"
    - After success, refresh all three records by calling fetchRecord for each system
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where 'Reset & Reseed' not in buttonList_
    - _Expected_Behavior: Reset & Reseed button visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.9, 3.2_

  - [x] 19.3 Add handleScenarioA function
    - Update registered_address in SWS for selected UBID
    - Construct body: { registered_address: "${Date.now()} Scenario A Street, Bangalore 560001" }
    - Call PUT /api/mock/sws/record/${selectedUbid} with body
    - Show toast: "📤 Scenario A triggered — SWS address updated, propagating to departments..."
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where 'Scenario A' not in buttonList_
    - _Expected_Behavior: Scenario A button visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.10, 3.2_

  - [x] 19.4 Add handleScenarioB function
    - Update Buss_Addr_Line1 in Shop for selected UBID
    - Construct body: { Buss_Addr_Line1: "${Date.now()} Scenario B Road, Bangalore 560002" }
    - Call PUT /api/mock/shop/record/${selectedUbid} with body
    - Show toast: "📥 Scenario B triggered — Shop address updated, propagating to SWS..."
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where 'Scenario B' not in buttonList_
    - _Expected_Behavior: Scenario B button visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.10, 3.2_

  - [x] 19.5 Add handleScenarioC function
    - Reuse existing handleConflict logic (simultaneous SWS + Factories update)
    - Show toast: "⚔️ Scenario C triggered — simultaneous conflict, watch Conflicts tab..."
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where 'Scenario C' not in buttonList_
    - _Expected_Behavior: Scenario C button visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.10, 3.2_

  - [x] 19.6 Add five new buttons to mock-controls-right div
    - Add "🌱 Seed Data" button → calls handleSeed
    - Add "🔄 Reset & Reseed" button → calls handleReset
    - Add "📤 Scenario A: SWS→Dept" button → calls handleScenarioA
    - Add "📥 Scenario B: Dept→SWS" button → calls handleScenarioB
    - Add "⚔️ Scenario C: Conflict" button → calls handleScenarioC
    - Keep existing "Trigger Simultaneous Conflict" button for backward compatibility
    - _Bug_Condition: isBugCondition_Bug5(buttonList) where buttons are missing_
    - _Expected_Behavior: All 6 buttons visible and functional_
    - _Preservation: Existing button behavior unchanged_
    - _Requirements: 5.1, 5.2, 2.9, 2.10, 3.2_

  - [ ] 19.7 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - All Action Buttons Present
    - **IMPORTANT**: Re-run the SAME test from task 17 - do NOT write a new test
    - The test from task 17 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 17
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.9, 2.10_

  - [ ] 19.8 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Button Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 18 - do NOT write new tests
    - Run preservation property tests from step 18
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 20. Checkpoint - Ensure Bug 5 tests pass
  - Ensure all Bug 5 tests pass, ask the user if questions arise.

---

## Final Integration Testing

- [ ] 21. Integration test: Fresh deploy → auto-seed → UBID lookup succeeds
  - Test full flow from fresh container startup to successful UBID lookup
  - Verify all three mock systems auto-seed on empty DB
  - Verify all 20 UBIDs are accessible after auto-seed
  - _Requirements: 2.1, 2.2_

- [ ] 22. Integration test: Seed Data button → all systems seeded
  - Click "Seed Data" button in dashboard
  - Verify all three systems seeded with correct record counts
  - Verify success toast shown
  - _Requirements: 2.3, 2.9_

- [ ] 23. Integration test: Reset & Reseed button → all systems cleared and reseeded
  - Click "Reset & Reseed" button in dashboard
  - Verify all systems cleared and reseeded
  - Verify success toast shown and records refreshed
  - _Requirements: 2.4, 2.9_

- [ ] 24. Integration test: Scenario A → SWS updated → propagation to departments
  - Select UBID → click "Scenario A" button
  - Verify SWS address updated
  - Verify propagation to Shop and Factories
  - Verify success toast shown
  - _Requirements: 2.10_

- [ ] 25. Integration test: Scenario B → Shop updated → propagation to SWS
  - Select UBID → click "Scenario B" button
  - Verify Shop address updated
  - Verify propagation to SWS
  - Verify success toast shown
  - _Requirements: 2.10_

- [ ] 26. Integration test: Scenario C → conflict detected → appears in Conflicts tab
  - Select UBID → click "Scenario C" button
  - Verify conflict detected
  - Verify conflict appears in Conflicts tab
  - Verify success toast shown
  - _Requirements: 2.10_

- [ ] 27. Integration test: Empty DB + conflict trigger → error toast shown
  - Clear all databases
  - Click "Trigger Simultaneous Conflict" button
  - Verify error toast shown with helpful message
  - _Requirements: 2.8_

- [ ] 28. Final checkpoint - All tests pass
  - Ensure all tests pass across all 5 bugs
  - Verify no regressions in existing functionality
  - Ask the user if questions arise
