# Sudachi Analysis Improvement Walkthrough

## Goal
Fix the issue where `analyze_text_sudachi.py` failed to detect codes defined by multi-token phrases (e.g., `*MODAL_MUST` defined as "しなければならない").

## Changes Implemented
### Phrase-Aware Keyword Matching
- **Problem**: The original `check_keyword` function only checked for exact matches against single morphemes. "しなければならない" is tokenized into 5 morphemes, so it never matched.
- **Solution**: Implemented a new matching logic that:
    1. Finds the keyword in the raw text string.
    2. Verifies that the start and end of the matched string align with valid token boundaries.
    3. This allows matching phrases that span multiple tokens while avoiding partial matches (e.g., matching "must" inside "mustard").

### Code Modifications
- Modified `check_coding_rules` to pre-calculate token start/end positions.
- Updated `evaluate_rule`, `parse_and_evaluate`, and `check_keyword` to propagate and use these positions.

## Verification Results

### Accuracy Metrics
| Metric | Pre-Fix | Post-Fix |
| :--- | :--- | :--- |
| **Accuracy** | 62.63% | **63.92%** |
| **Perfect Matches** | 13,893 | **14,550** |

### Code Detection Improvements
#### `*MODAL_MUST` (Obligation)
- **Pre-Fix**: 3,613 Missing (Top 1 missing code).
- **Post-Fix**: **0 Missing**.
- **Note**: Now appears as "Extra" in 3,702 cases. This indicates that the script now detects `*MODAL_MUST` in many paragraphs where the DB does not explicitly label it (likely because the DB prioritizes thematic labels over modal ones, or the script is now more sensitive).

#### `*CLAUSE_EXPLANATION`
- **Status**: Still missing (2,040 cases).
- **Reason**: This rule relies heavily on the `near()` operator (e.g., `near(説明会-開催)`). The `near()` logic currently operates on single tokens and was not updated to support phrases. This requires a more complex fix in `check_distance_logic`.

## Phase 2: near() / seq() Logic Improvement & BOM Fix

### Changes
1.  **Interval-Based Distance Logic**:
    - Implemented `find_token_intervals` to map phrases (e.g., "地域住民") to token spans.
    - Updated `check_distance_logic` to calculate distance based on these spans, allowing `near()` and `seq()` to work with phrases.

2.  **BOM Fix**:
    - Discovered that `khcoder_coding_rules_PV_v4.txt` had a BOM (Byte Order Mark) at the beginning.
    - This caused the first rule (`*CLAUSE_EXPLANATION`) to be skipped during loading.
    - Updated `load_coding_rules` to use `encoding='utf-8-sig'` to correctly handle the BOM.

3.  **Dictionary Strategy**:
    - Found that using the user dictionary (even with adjusted costs) caused regressions in other rules.
    - **Decision**: Disabled user dictionary loading and relied entirely on the code-based phrase matching logic.

### Verification Results (Final)
- **Accuracy**: **64.26%** (Improved from initial 62.63%)
- **Key Improvements**:
    - `*MODAL_MUST`: **0 missing** (was 3613).
    - `*CLAUSE_EXPLANATION`: **0 missing** (was 2040). Now appears as "Extra" (1737), indicating it is being detected (possibly more aggressively than the DB).

### Remaining Issues
- `*CLAUSE_DOC_REQUIREMENTS` (796 missing) and `*CLAUSE_POSITIVE_PERMISSION_CONSENT` (718 missing) are the next top issues.
- The "Extra" detections for `*MODAL_MUST` and `*CLAUSE_EXPLANATION` suggest a need to refine the rules or validate the DB labels.

## Phase 3: Switch to SplitMode.A

### Changes
- Changed Sudachi tokenizer mode from `SplitMode.C` (Compound) to `SplitMode.A` (Short).
- **Reason**: To match MeCab's tokenization behavior, specifically for terms like "許可申請書" which Sudachi C treats as one token, breaking rules like `near(申請-書)`.

### Verification Results
- **Accuracy**: **63.95%** (Comparable to Phase 2's 64.26%)
- **Improvements**:
    - `*CLAUSE_DOC_REQUIREMENTS`: Missing count dropped from **796** to **364**. This confirms that splitting "申請書" into "申請" + "書" helped.
- **Regressions**:
    - `*PROCEDURE_NOTICE_OPERATOR`: Missing count increased from **512** to **1083**. The token splitting likely interfered with rules relying on longer compound nouns for this code.

## Conclusion
The switch to `SplitMode.A` successfully resolved a significant portion of the `*CLAUSE_DOC_REQUIREMENTS` missing cases, validating the hypothesis that tokenization granularity was the issue. However, it caused a regression in `*PROCEDURE_NOTICE_OPERATOR`. The overall accuracy remains stable at ~64%. Future work should balance these trade-offs, potentially by adjusting specific rules for `*PROCEDURE_NOTICE_OPERATOR` to accommodate the shorter tokens.
