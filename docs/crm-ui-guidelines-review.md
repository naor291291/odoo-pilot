# Web Interface Guidelines implementation review

Rules fetched from Vercel's `web-interface-guidelines/command.md`, SHA `3eb3a212b7b89493922ea418489d4c6f67ae8bd5`. This is a code review plus the linked browser evidence, not a formal accessibility certification.

## `static/src/js/field_portal.js`

- `static/src/js/field_portal.js:22` — fixed: missing requirements now produce a focusable linked summary and inline `aria-describedby` errors.
- `static/src/js/field_portal.js:97` — fixed: generated image previews declare dimensions and descriptive alternatives; controls are native buttons.
- `static/src/js/field_portal.js:160` — fixed: forward navigation checks the current report/photo requirements, while Back retains values and file objects.
- `static/src/js/field_portal.js:175` — fixed: jumping directly to review exposes the panel containing the error; focus stays actionable.
- `static/src/js/field_portal.js:209` — fixed: leaving a dirty report warns before losing unsaved changes; submitted requests are exempt.
- `static/src/js/field_portal.js:222` — retained: busy text, `aria-busy`, duplicate-submit prevention and server-response success receipt.

## `static/src/scss/field_crm.scss`

- `static/src/scss/field_crm.scss:7` — visible focus with scroll margins; controls use touch manipulation and minimum touch sizes.
- `static/src/scss/field_crm.scss:60` — three-step navigation uses native buttons and textual `aria-current=step`, with full labels.
- `static/src/scss/field_crm.scss:64` — hidden wizard panels/actions remain non-interactive; no visually hidden active submit control.
- `static/src/scss/field_crm.scss:69` — report action area follows content and reserves device safe area; it does not cover form fields.
- `static/src/scss/field_crm.scss:71` — photo dialog contains overscroll; native Escape/focus behavior is preserved.
- ✓ no `outline:none`, `transition:all`, zoom suppression or new layout-measurement render loop.

## Views and shared design

- `views/field_portal_templates.xml` — labelled select/text/file controls, semantic step headings, error/status regions, sized lazy thumbnails, native localized datetime rendering, skip link and named photo dialog.
- `views/field_navigation_views.xml` — native Odoo controls for hub, client directory, task list/form/calendar and guide; descriptive queue/primary actions and empty-state help. Owner fields have explicit groups as well as ORM restrictions.
- `views/field_interface_views.xml` — inline missing-data guidance and textual stage indicator; existing Continue/Back and server validation retained.
- `views/field_workspace_views.xml` — three labelled percentage tiers, whole-amount/frozen-rate guidance and native open-form alternative to editing a dense table.
- `views/field_dispatch_views.xml`, `field_collection_views.xml`, `field_pricing_views.xml` — decorative Font Awesome icons hidden from assistive technology.
- `static/src/scss/field_interface.scss` — local Hebrew font with swap, semantic colors, readable readonly labels, tabular/LTR-isolated values and reduced-motion support retained.

## Scoped calendar extension

- `static/src/js/field_calendar.js` — registers a dedicated view via Odoo's view registry; inherits the native renderers/popover instead of patching core or globally altering calendars.
- `static/src/xml/field_calendar.xml` — native mobile Dialog, semantic close/open buttons, explicit Hebrew labels and wrapped event title. The action opens the readonly task form.
- `views/field_navigation_views.xml` — calendar creation, drag editing and deletion disabled; the workflow remains governed in the work card.

## Native platform boundaries and remaining checks

Odoo owns generic toolbar/search/dialog/list/calendar keyboard behavior, route state and widgets; these were reused rather than patched. Backend notebook selection is expressed through focused native actions, not a new custom URL/tab router. Hebrew has no Title Case; labels use normal Hebrew sentence forms. Native Odoo settings/users/project/CRM entries receive read-only smoke coverage, not a claim that every administrative setting and native widget was redesigned.

Automated browser checks cover visible client labels, queue touch targets, RTL direction, viewport overflow, keyboard activation, file/review errors, Escape/focus return, native required-name validation, rate bounds, draft persistence and role visibility. Physical-device camera/network interruption and real assistive technology remain manual verification items. Exact completed screens and CI results are recorded separately in `crm-ux-coverage.md` and the generated `coverage.json`.
