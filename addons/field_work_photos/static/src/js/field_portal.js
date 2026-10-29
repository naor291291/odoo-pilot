/** @odoo-module **/

function setupFieldReports() {
    for (const form of document.querySelectorAll('[data-field-report]')) {
        if (form.dataset.initialized) continue;
        form.dataset.initialized = '1';
        const submit = form.querySelector('[data-report-submit]');
        const save = form.querySelector('[data-report-save]');
        const result = form.querySelector('[name="field_visit_result"]');
        const summary = form.querySelector('[name="field_visit_summary"]');
        const reason = form.querySelector('[name="field_visit_reason"]');
        const galleries = [...form.querySelectorAll('.o_field_gallery')].map(root => ({root, files: [], urls: []}));
        const count = gallery => gallery.root.querySelectorAll('[data-photo-key]').length
            - gallery.root.querySelectorAll('[name="remove_photo"]:checked').length + gallery.files.length;
        const update = () => {
            const [before, after] = galleries.map(count);
            const completed = result?.value === 'completed';
            if (summary) summary.required = completed;
            if (reason) reason.required = Boolean(result.value) && !completed;
            const reasonArea = form.querySelector('[data-visit-reason]');
            if (reasonArea && result) reasonArea.hidden = !result.value || completed;
            if (submit) submit.disabled = !result.value || (completed
                ? !before || !after || !summary.value.trim()
                : !reason.value.trim());
            form.querySelector('[data-report-summary]').textContent = `${before} תמונות לפני · ${after} תמונות אחרי` +
                (result && completed && (!before || !after) ? ' — להשלמת עבודה נדרשת תמונה אחת לפחות בכל אזור.' : '');
        };
        const dialog = form.parentElement.querySelector('[data-photo-dialog]');
        const zoom = src => {
            if (!dialog || !dialog.showModal) return false;
            dialog.querySelector('img').src = src;
            dialog.showModal();
            return true;
        };
        dialog?.querySelector('[data-close-photo]').addEventListener('click', () => dialog.close());
        for (const link of form.querySelectorAll('[data-zoom-photo]')) {
            link.addEventListener('click', event => { if (zoom(link.href)) event.preventDefault(); });
        }
        for (const gallery of galleries) {
            const {root} = gallery;
            const input = root.querySelector('input[type="file"]');
            if (!input) continue;
            const error = root.querySelector('[data-file-error]');
            const select = root.querySelector('[data-select-photo]');
            const syncFiles = () => {
                const transfer = new DataTransfer();
                for (const file of gallery.files) transfer.items.add(file);
                input.files = transfer.files;
            };
            const render = () => {
                for (const url of gallery.urls) URL.revokeObjectURL(url);
                gallery.urls = [];
                const container = root.querySelector('[data-new-photos]');
                container.replaceChildren();
                gallery.files.forEach((file, index) => {
                    const url = URL.createObjectURL(file);
                    gallery.urls.push(url);
                    const item = document.createElement('div');
                    item.className = 'o_field_gallery_item';
                    const enlarge = document.createElement('button');
                    enlarge.type = 'button';
                    enlarge.className = 'o_field_photo_zoom';
                    enlarge.setAttribute('aria-label', `הגדלת תמונה חדשה ${index + 1}`);
                    const img = document.createElement('img');
                    img.className = 'o_field_gallery_image';
                    img.src = url;
                    img.alt = `תמונה חדשה ${index + 1}`;
                    enlarge.append(img);
                    enlarge.addEventListener('click', () => zoom(url));
                    const label = document.createElement('p');
                    label.className = 'o_field_help';
                    label.textContent = 'תמונה חדשה — עדיין לא נשמרה';
                    const remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'btn btn-link';
                    remove.textContent = 'הסרת התמונה החדשה';
                    remove.addEventListener('click', () => {
                        gallery.files.splice(index, 1);
                        syncFiles();
                        render();
                        update();
                        select.focus();
                    });
                    item.append(enlarge, label, remove);
                    container.append(item);
                });
            };
            // Keep the ordinary multipart input available when JS is absent.
            input.classList.add('visually-hidden');
            input.tabIndex = -1;
            select.hidden = false;
            select.addEventListener('click', () => {
                // The retained File objects are restored after the next choice.
                input.value = '';
                input.click();
            });
            input.addEventListener('cancel', syncFiles);
            input.addEventListener('change', () => {
                const files = [...input.files];
                const invalid = files.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 12 * 1024 * 1024);
                const tooMany = count(gallery) + files.length > 5;
                error.hidden = !invalid && !tooMany;
                error.textContent = invalid ? 'יש לבחור JPG, PNG או WebP בגודל של עד 12MB לתמונה.'
                    : tooMany ? 'אפשר לשמור עד 5 תמונות באזור הזה. הסר תמונה לפני הוספה נוספת.' : '';
                input.setAttribute('aria-invalid', error.hidden ? 'false' : 'true');
                if (!invalid && !tooMany) gallery.files.push(...files);
                syncFiles();
                render();
                update();
            });
            for (const checkbox of root.querySelectorAll('[name="remove_photo"]')) {
                checkbox.addEventListener('change', () => {
                    if (count(gallery) > 5) {
                        checkbox.checked = true;
                        error.hidden = false;
                        error.textContent = 'יש להסיר תמונה חדשה לפני ביטול ההסרה: עד 5 תמונות באזור.';
                    }
                    checkbox.closest('[data-photo-key]').classList.toggle('o_field_photo_marked', checkbox.checked);
                    update();
                });
            }
        }
        for (const field of [result, summary, reason]) field?.addEventListener('input', update);
        form.addEventListener('submit', event => {
            if (form.dataset.submitting === '1') {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = '1';
            form.setAttribute('aria-busy', 'true');
            if (event.submitter) event.submitter.textContent = 'שומר את הדיווח…';
        });
        window.addEventListener('pageshow', () => {
            delete form.dataset.submitting;
            form.removeAttribute('aria-busy');
            if (submit) submit.textContent = 'שליחת דיווח לבדיקה';
            if (save) save.textContent = 'שמירה והמשך מאוחר יותר';
            update();
        });
        update();
    }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setupFieldReports);
else setupFieldReports();
