"""Current synthetic Chromium evidence; no substitution of unrelated old PRs."""
import base64
import html
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local-data/ui-checks'
artifact = os.environ.get('UI_BASELINE_ARTIFACT_ID', '')
expected_baseline_commit = os.environ.get('UI_BASELINE_COMMIT', '')
baseline = None
baseline_commit = None
if artifact:
    assert artifact.isdigit(), 'Baseline artifact ID must be numeric'
    assert re.fullmatch(r'[0-9a-f]{40}', expected_baseline_commit), 'An exact tested baseline commit is required'
    try:
        result = subprocess.run(['gh', 'api', f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{artifact}/zip"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        if result.returncode == 0:
            baseline = zipfile.ZipFile(BytesIO(result.stdout))
            proof = json.loads(baseline.read('browser-journeys/coverage.json'))
            assert proof['commit'] == expected_baseline_commit, 'Baseline artifact does not match the expected tested commit'
            assert proof['mode'] == 'observe', 'Expected a baseline observation run'
            baseline_commit = proof['commit']
    except (subprocess.TimeoutExpired, OSError, zipfile.BadZipFile):
        # A missing/unavailable archive is disclosed below. A provenance
        # mismatch deliberately fails rather than relabelling unrelated images.
        if baseline:
            baseline.close()
        baseline = None

def figure(name, label, before=False):
    try:
        data = baseline.read(name) if before and baseline else (OUTPUT / name).read_bytes() if not before else None
    except (KeyError, OSError):
        data = None
    caption = '<figcaption>' + html.escape(label) + '</figcaption>'
    if data is None:
        return '<figure>' + caption + '<p>צילום אינו זמין בריצה הזאת.</p></figure>'
    src = 'data:image/png;base64,' + base64.b64encode(data).decode()
    return '<figure>' + caption + '<img src="' + src + '" alt="' + html.escape(label) + '"></figure>'

pairs = [
    ('BUX-01 — מצב שמירה אחרי עריכה נוספת', 'browser-journeys/saved-then-edited-390.png'),
    ('BUX-02 — תיקון חריגה ממספר התמונות', 'browser-journeys/capacity-recovered-390.png'),
    ('BUX-03 — רשימת דיווחים ריקה בבדיקה', 'browser-journeys/empty-pending-390.png'),
    ('BUX-04 — עשר תמונות בטלפון', 'browser-journeys/ten-photos-390.png'),
    ('BUX-05 — עבודה קצרה ללא פרטים נוספים', 'browser-journeys/draft-390.png'),
    ('BUX-06 — בדיקת ההערות לפני שליחה', 'browser-journeys/review-notes-390.png'),
    ('BUX-07 — העבודות להיום', 'crm/today-agenda-390.png'),
]
sections = ''.join('<section><h2>' + title + '</h2><div class="pair">' +
                   figure(name, 'לפני — קוד המוצר זהה ל־main בתחילת הסבב', True) +
                   figure(name, 'אחרי — גרסת הענף בריצת הבדיקות הזאת') + '</div></section>' for title, name in pairs)
coverage = {}
for suite in ('crm', 'statement', 'browser-journeys'):
    path = OUTPUT / suite / 'coverage.json'
    coverage[suite] = json.loads(path.read_text()) if path.exists() else {'screens': []}
rows = ''.join('<tr><td>' + html.escape(suite + ' / ' + item['screen']) + '</td><td>' +
               str(item['width']) + 'px</td></tr>' for suite, value in coverage.items() for item in value['screens'])
journey = coverage['browser-journeys']
checks = ''.join('<tr><td>' + html.escape(item['id']) + '</td><td>' + html.escape(item['description']) +
                 '</td><td>' + ('עבר' if item['passed'] else 'דורש תיקון') + '</td></tr>' for item in journey.get('checks', []))
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
run_url = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
document = '''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRM — תהליכים לפני ואחרי</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:#183044;font:16px/1.65 Arial,sans-serif}main{max-width:1280px;margin:auto;padding:24px}header,section{background:white;border:1px solid #dce4e9;border-radius:12px;padding:24px;margin-bottom:24px}h1{font-size:28px}h2{font-size:22px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}figure{margin:0;min-width:0}figcaption{padding:12px;background:#edf6f6;margin-bottom:12px;font-weight:bold}img{display:block;max-width:100%;height:auto;border:1px solid #dce4e9}a{color:#086b74}table{width:100%;border-collapse:collapse}td,th{text-align:start;padding:10px;border-bottom:1px solid #dce4e9;overflow-wrap:anywhere}code{direction:ltr;unicode-bidi:isolate;overflow-wrap:anywhere}@media(max-width:800px){main{padding:12px}.pair{grid-template-columns:1fr}header,section{padding:16px}}
</style></head><body><main><header><h1>CRM — תהליכים לפני ואחרי</h1><p>Odoo Community 18 · עברית ו־RTL · נתונים מלאכותיים בלבד.</p><p>בדיקות אוטומטיות בדפדפן Chromium בסביבת CI מבודדת. הדפדפן החי נחסם במדיניות כתובות; זו אינה טענה לשימוש ידני באתר המשותף. צילומי ההשוואה הם מאותם תרחישים ורוחבים, אך זמני ההפקה ונתוני הבדיקה משתנים בין הריצות.</p>'''
document += '<p>גרסת הריצה: <code>' + sha + '</code> · <a href="' + run_url + '">לוגים ותוצרי בדיקות</a></p>'
document += '<p>בסיס: <code>' + (baseline_commit or expected_baseline_commit or 'לא הוגדר') + '</code> · ' + ('ארכיון הבסיס הושווה ל־commit שנבדק.' if baseline else 'ארכיון הבסיס אינו זמין; אין תחליף מצילום ישן.') + '</p></header>'
document += sections + '<section><h2>רגרסיות ממוקדות</h2><p>מצב: ' + html.escape(journey.get('mode', 'לא נבדק')) + '</p><table><thead><tr><th>מזהה</th><th>בדיקה</th><th>תוצאה</th></tr></thead><tbody>' + checks + '</tbody></table></section>'
document += '<section><h2>כיסוי מסכים מצולם</h2><p>צילום מוכיח מצב מסוים בלבד. פעולות והרשאות שבוצעו מתועדות בבדיקות וב־docs/browser-ux-review.md.</p><table><thead><tr><th>תרחיש</th><th>רוחב</th></tr></thead><tbody>' + rows + '</tbody></table></section>'
document += '<section><h2>מגבלות</h2><p>לא בוצעה בדיקה במכשיר פיזי, ב־Safari או עם קורא מסך. אין חיבור Morning חי או שליחת הודעות. מסכי הגדרות מקוריים מקבלים בדיקת כניסה בלבד. דוח ההתחשבנות וה־PDF כבר קיימים ונבדקים בסוויטה נפרדת. מוכנות אבטחת סביבת ההפעלה נבחנת בנפרד ממוכנות הממשק.</p></section></main></body></html>'
(OUTPUT / 'crm-browser-before-after.html').write_text(document)
if baseline:
    baseline.close()
print(json.dumps({'report': 'crm-browser-before-after.html', 'commit': sha, 'baseline_commit': baseline_commit, 'baseline_loaded': bool(baseline),
                  'captures': sum(len(value['screens']) for value in coverage.values())}))
