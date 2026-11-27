def migrate(cr, version):
    # Preserve financial estimates on historical works. New works use the new
    # formula; open works are converted after the schema exists (post migration).
    cr.execute("ALTER TABLE crm_lead ADD COLUMN IF NOT EXISTS field_commission_formula varchar")
    cr.execute("UPDATE crm_lead SET field_commission_formula = 'gross' WHERE field_commission_formula IS NULL")
