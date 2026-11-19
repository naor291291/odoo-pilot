"""Operator-only helpers for a separately authorized, reversible pilot role change.

Not RPC methods, no automatic execution or commits. Preflight is read-only.
"""
from odoo.exceptions import AccessError, ValidationError

FINANCE = 'field_work_photos.group_field_finance'
OPS = 'field_work_photos.group_field_dispatcher'


def preflight(env, login, expected_uid=None):
    if not (env.su or env.user.has_group('base.group_system')):
        raise AccessError('בדיקת חשבון הפיילוט דורשת מנהל מערכת.')
    users = env['res.users'].with_context(active_test=False).search([('login', '=', login)])
    if len(users) != 1 or (expected_uid is not None and users.id != expected_uid):
        raise ValidationError('זהות החשבון אינה תואמת; אין לשנות הרשאות.')
    user = users
    if not user.active or user.share or not user.has_group(OPS):
        raise ValidationError('נדרש חשבון פנימי פעיל בעל הרשאת תפעול קיימת.')
    if any(user.has_group(group) for group in ('base.group_system', 'base.group_erp_manager')):
        raise ValidationError('החשבון כבר מחזיק הרשאת ניהול מערכת או משתמשים; נדרשת בדיקה נפרדת.')
    if not user.company_ids or user.company_id not in user.company_ids:
        raise ValidationError('יש לאמת את שיוך החברות לפני שינוי הרשאות.')
    return {'uid': user.id, 'login': user.login, 'name': user.name,
            'company_ids': sorted(user.company_ids.ids), 'company_id': user.company_id.id,
            'finance': user.has_group(FINANCE)}


def enable(env, login, expected_uid):
    """Execute ONLY after separate approval; retain the returned receipt for rollback."""
    before = preflight(env, login, expected_uid)
    added = not before['finance']
    if added:
        env['res.users'].browse(expected_uid).write({'groups_id': [(4, env.ref(FINANCE).id)]})
    after = preflight(env, login, expected_uid)
    if after['company_ids'] != before['company_ids'] or not after['finance']:
        raise ValidationError('אימות הרשאות נכשל; יש לבטל את העסקה.')
    return {**before, 'added_finance': added}


def restore(env, receipt):
    """Remove only Finance added by enable; preserve prior Finance and other groups."""
    current = preflight(env, receipt['login'], receipt['uid'])
    if current['company_ids'] != receipt['company_ids'] or current['company_id'] != receipt['company_id']:
        raise ValidationError('שיוך החברות השתנה מאז ההרחבה; נדרשת בדיקה נפרדת.')
    if receipt['added_finance']:
        env['res.users'].browse(receipt['uid']).write({'groups_id': [(3, env.ref(FINANCE).id)]})
    result = preflight(env, receipt['login'], receipt['uid'])
    if result['finance'] != receipt['finance']:
        raise ValidationError('החזרת ההרשאות לא הושלמה; יש לבטל את העסקה.')
    return result
