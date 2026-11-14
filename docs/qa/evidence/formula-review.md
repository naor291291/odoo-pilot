# Original contractor workbook formula review

Read-only export inspected 2026-11-07 from the user-provided Google Sheet (ID `1qcKzzlgUC8RGMx8kjF4pf2Mjlh2XSQ0q-z8UJE3_7u0`). Workbook SHA-256: `91296f727eefbac511e6434ec5ba67acc26adc29ef10f3d3e7f2b02f226fbee5`.

No customer rows, addresses, names or workbook copy are committed. Formula text was extracted directly from XLSX XML; the workbook was not edited or recalculated.

All six monthly worksheets have the same first-row J/K/L/M/N formula definitions:

- J: zero when D is zero/blank/question-mark or E/F question-mark, otherwise D − E − F.
- K: 0 for the no-commission choice; otherwise 70% at J <= 500, 65% at J <= 1250, else 50%.
- L: zero for the two special categories; for regular rows, J if K=0, zero if J=0, else J*K+E.
- M/N: only their respective category; J if K=0, else J*K+E. These special categories reimburse E even when J=0.

`models/field_entitlement.py:sheet_amounts` matches these numeric cases. `test_sheet_formula_boundaries_and_special_cases` (passed in the 205-test native suite) checks 500/500.01, 1250/1250.01, zero, negative, no-commission and special zero-profit reimbursement. The category totals/snapshot test checks approved immutable movements and cash offset.

Boundaries: Odoo requires complete numeric inputs rather than storing question-mark strings; it rounds the base to currency precision and the calculated share to four decimals. Workbook sums operate on monthly rows; Odoo uses approved dated movements and reversals, preserving audit history. This review verifies formula structure plus existing executable edge cases, not every populated workbook row or Excel/Sheets engine recalculation.
