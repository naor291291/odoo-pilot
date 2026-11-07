# Review tool provenance

Installed project-local instructions, not global personal skills. Upstream content is retained unchanged.

- Interface Design: `2f9be3206855bcb2d1d0af262c8bae25cba6658d`
- Vercel Web Design Guidelines: `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62`
- Microsoft Playwright CLI source: `4bc00fb7fa5b4329f2fb53ac4743a066c2c664e8`
- Installed CLI: `@playwright/cli 0.1.23`. CLI-created instructions are under `.agents/skills/playwright-cli`.
- CLI browser installation failed on downloaded archive validation; installed system Chromium also failed on a forbidden local socket. CI uses its supported Google Chrome binary.
- Playwright/axe browser audit versions and integrity hashes are pinned in `scripts/qa/package-lock.json`.
- Odoo testing: official 18.0 source `odoo/tests/common.py` and `odoo/tests/loader.py` inspected. TransactionCase and HttpCase used.
