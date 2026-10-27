/** @odoo-module **/

function setupFieldReports() {
    for (const form of document.querySelectorAll('[data-field-report]')) {
        if (form.dataset.initialized) continue;
        form.dataset.initialized = '1';
        const slots = [...form.querySelectorAll('.o_field_photo_slot')];
        const submit = form.querySelector('[data-report-submit]');
        const save = form.querySelector('[data-report-save]');
        if (!submit || !save) continue;
        const previews = new Map();
        const update = () => {
            const ready = slots.filter(slot => slot.dataset.saved === '1' || slot.dataset.selected === '1').length;
            const invalid = slots.some(slot => slot.dataset.invalid === '1');
            const changed = slots.some(slot => slot.dataset.selected === '1');
            submit.disabled = ready !== 2 || invalid;
            save.disabled = !changed || invalid;
            form.querySelector('[data-report-summary]').textContent = ready === 2
                ? 'שתי התמונות מוכנות. אפשר לשמור ולהגיש לאישור.'
                : `${ready} מתוך 2 תמונות מוכנות. יש להשלים תמונה לפני ביצוע ותמונה אחרי ביצוע.`;
        };
        for (const slot of slots) {
            const input = slot.querySelector('input[type="file"]');
            const preview = slot.querySelector('img');
            const status = slot.querySelector('[data-file-status]');
            const error = slot.querySelector('[data-file-error]');
            const clear = slot.querySelector('[data-clear-photo]');
            if (!input) continue;
            input.addEventListener('change', () => {
                if (previews.has(slot)) URL.revokeObjectURL(previews.get(slot));
                previews.delete(slot);
                const file = input.files[0];
                const invalid = file && (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 12 * 1024 * 1024);
                slot.dataset.invalid = invalid ? '1' : '0';
                slot.dataset.selected = file && !invalid ? '1' : '0';
                input.setAttribute('aria-invalid', invalid ? 'true' : 'false');
                error.hidden = !invalid;
                error.textContent = invalid ? 'יש לבחור JPG, PNG או WebP בגודל של עד 12MB.' : '';
                clear.hidden = !file;
                if (file && !invalid) {
                    const url = URL.createObjectURL(file);
                    previews.set(slot, url);
                    preview.src = url;
                    preview.hidden = false;
                    status.textContent = 'נבחרה תמונה חדשה — עדיין לא נשמרה';
                } else {
                    preview.hidden = slot.dataset.saved !== '1';
                    if (slot.dataset.savedSrc) preview.src = slot.dataset.savedSrc;
                    else preview.removeAttribute('src');
                    status.textContent = slot.dataset.saved === '1' ? 'נשמרה במערכת' : 'בחר תמונה מהמצלמה או מהגלריה';
                }
                const placeholder = slot.querySelector('[data-photo-placeholder]');
                if (placeholder) placeholder.hidden = !preview.hidden;
                update();
            });
            clear.addEventListener('click', () => {
                input.value = '';
                input.dispatchEvent(new Event('change'));
                input.focus();
            });
        }
        form.addEventListener('submit', event => {
            if (form.dataset.submitting === '1') {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = '1';
            form.setAttribute('aria-busy', 'true');
            if (event.submitter) event.submitter.textContent = 'שומר את הדיווח…';
        });
        window.addEventListener('pagehide', () => {
            for (const url of previews.values()) URL.revokeObjectURL(url);
        });
        window.addEventListener('pageshow', () => {
            delete form.dataset.submitting;
            form.removeAttribute('aria-busy');
            submit.textContent = 'שמירת התמונות והגשה לאישור';
            save.textContent = 'שמירה והמשך מאוחר יותר';
            update();
        });
        update();
    }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setupFieldReports);
else setupFieldReports();
