"""Build inspectable screenshot evidence after both Chrome suites succeed."""
import base64
import html
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / '.local-data' / 'ui-checks'
coverage = json.loads((output / 'crm' / 'coverage.json').read_text())
images = {}
current = {
    'after-work': 'mobile-quote.png',
    'after-portal': 'portal-step-error-mobile.png',
    'after-rates': 'crm/contractor-rate-form-mobile.png',
    'after-hub': 'crm/hub-owner-1440.png',
    'after-client': 'crm/client-form-mobile.png',
    'after-task': 'crm/today-agenda-390.png',
    'after-guide': 'crm/guide-mobile.png',
    'after-calendar': 'crm/appointment-popover-desktop.png',
}
for key, name in current.items():
    images[key] = (output / name).read_bytes()
baseline = False
try:
    repository = os.environ['GITHUB_REPOSITORY']
    result = subprocess.run(
        ['gh', 'api', f'repos/{repository}/actions/artifacts/13046347621/zip'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
    if result.returncode == 0:
        with zipfile.ZipFile(BytesIO(result.stdout)) as archive:
            images['before-work'] = archive.read('mobile-quote.png')
            images['before-portal'] = archive.read('portal-step-error-mobile.png')
            images['before-rates'] = archive.read('crm/contractor-rate-form-mobile.png')
            images['before-hub'] = archive.read('crm/hub-owner-1440.png')
        baseline = True
except (KeyError, ValueError, OSError, subprocess.TimeoutExpired, zipfile.BadZipFile):
    pass

def figure(key, title):
    if key not in images:
        return '<p>צילום הבסיס אינו זמין בארכיון הזה.</p>'
    data = images[key]
    width, height = struct.unpack('>II', data[16:24])
    url = 'data:image/png;base64,' + base64.b64encode(data).decode()
    marks = {'before-hub': [('F01', 3, .03, .27, .94, .33)],
             'before-work': [('F02', 3, .04, .25, .92, .62)],
             'before-portal': [('F02', 3, .03, .10, .94, .49), ('F05', 1, .03, .00, .94, .04)],
             'before-rates': [('F04', 2, .03, .23, .94, .63)]}.get(key, [])
    pins = ''.join(f'<span class="audit-mark s{sev}" style="left:{x*100}%;top:{y*100}%;width:{w*100}%;height:{h*100}%"><b>{label}</b></span>' for label, sev, x,y,w,h in marks)
    return f'<figure><figcaption>{html.escape(title)}</figcaption><div class="annotated"><a href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{html.escape(title)}" width="{width}" height="{height}"></a>{pins}</div></figure>'

sections = []
for title, first, second in [
    ('מרכז העבודה: מעבודות נסתרות לפעולה ישירה', 'before-hub', 'after-hub'),
    ('כרטיס העבודה והניווט', 'before-work', 'after-work'),
    ('פורטל קבלן: תקציר קצר ומעבר לדיווח', 'before-portal', 'after-portal'),
    ('מחירון קבלן: מדרגות קומפקטיות ודוגמת חישוב', 'before-rates', 'after-rates'),
]:
    sections.append('<section><h2>' + title + '</h2><div class="pair">' +
                    figure(first, 'לפני — PR #12, תואם מבנית ל־main בתחילת הסבב') + figure(second, 'אחרי — סבב הבהירות הנוכחי') + '</div></section>')
for key, title in [
    ('after-client', 'פרטי לקוח בטלפון'),
    ('after-task', 'העבודות להיום בטלפון — תצוגה חדשה'),
    ('after-guide', 'מדריך העבודה'),
    ('after-calendar', 'פרטי מועד ופתיחת משימה'),
]:
    sections.append('<section><h2>' + title + '</h2>' + figure(key, title) + '</section>')
rows = ''.join('<tr><td>' + html.escape(item['screen']) + '</td><td>' + str(item['width']) + 'px</td><td>עבר</td></tr>' for item in coverage['screens'])
run_url = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
document = '''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>סקירת ממשק CRM — לפני ואחרי</title><style>
.annotated{position:relative}.audit-mark{position:absolute;border:3px solid #b34e00;pointer-events:none}.audit-mark b{position:absolute;top:0;left:0;background:#b34e00;color:white;padding:2px 6px;font:14px Arial}.audit-mark.s1{border-color:#1976d2}.audit-mark.s1 b{background:#1976d2}.audit-mark.s2{border-color:#8b6000}.audit-mark.s2 b{background:#8b6000}*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:#183044;font:16px/1.65 Arial,sans-serif}main{max-width:1280px;margin:auto;padding:24px}header,section{background:white;border:1px solid #dce4e9;border-radius:12px;padding:24px;margin-bottom:24px}h1{font-size:30px}h2{font-size:23px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}figure{margin:0;min-width:0}figcaption{padding:12px;background:#edf6f6;border-radius:8px;margin-bottom:12px;font-weight:bold}img{display:block;max-width:100%;height:auto;border:1px solid #dce4e9}a{color:#086b74}table{width:100%;border-collapse:collapse}td,th{text-align:start;padding:10px;border-bottom:1px solid #dce4e9}td:first-child{direction:ltr;text-align:right;overflow-wrap:anywhere}@media(max-width:800px){main{padding:12px}.pair{grid-template-columns:1fr}header,section{padding:16px}}
</style></head><body><main><header><h1>סקירת ממשק CRM — לפני ואחרי</h1><p>Odoo Community 18 · עברית ו־RTL · מנהלי פרויקטים וקבלנים בטלפון.</p><p>152 בדיקות מערכת, בדיקת הפעלה מחדש ושני תסריטי Chrome. כל הצילומים מציגים נתוני בדיקה מלאכותיים; הסכומים, התאריכים והסטטוסים עשויים להשתנות בין הריצות. צילומי הבסיס מארכיון PR #12. נבדק שקוד הממשק שלו זהה לבסיס main בסבב זה פרט לרווחים; נתוני הבדיקה והזמנים עשויים להשתנות. תצוגת היום חדשה. הסימונים בצילומי ״לפני״ מתייחסים לממצאים F01/F02/F04/F05 בדוח הביקורת; האזורים מקורבים. לחצו על תמונה לפתיחה בגודל מלא.</p>'''
document += '<p><a href="' + run_url + '">ריצת הבדיקות</a> · <a href="https://github.com/naor291291/odoo-pilot/compare/main...feature/crm-clarity-pass">השינוי לסקירה</a></p></header>'
document += ''.join(sections)
document += '<section><h2>כיסוי בדיקות המסכים</h2><table><thead><tr><th>מסך / מצב</th><th>רוחב</th><th>תוצאה</th></tr></thead><tbody>' + rows + '</tbody></table></section>'
document += '<section><h2>מה עדיין לא נבדק או לא מומש</h2><p>לא בוצע חיבור API חי ל־Morning. שליחה אוטומטית, דוח התחשבנות חודשי ומדדי הכנסה/רווח/המרה אינם מוצגים כאן כיכולות שהושלמו. מסכי Odoo המקוריים נבדקו בכניסה לעיון; זו אינה טענה לעיצוב מחדש של כל מסך מנהל מערכת. מצלמה בטלפון אמיתי, קורא מסך ורשת סלולרית לא יציבה דורשים בדיקה נפרדת.</p></section></main></body></html>'
(output / 'crm-ui-before-after.html').write_text(document)
for key, data in images.items():
    if key != 'before-rates':
        print('UI_EVIDENCE_IMAGE ' + json.dumps({'name': key, 'image_url': 'data:image/png;base64,' + base64.b64encode(data).decode()}), flush=True)
print('UI_EVIDENCE_META ' + json.dumps({'captures': len(coverage['screens']), 'baseline_loaded': baseline, 'report': 'crm-ui-before-after.html'}), flush=True)
