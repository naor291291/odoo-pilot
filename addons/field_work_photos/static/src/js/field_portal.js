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
        let dirty = false;
        const errorSummary = form.querySelector('[data-report-errors]');
        const clearErrors = () => {
            if (errorSummary) { errorSummary.hidden = true; errorSummary.replaceChildren(); }
            for (const error of form.querySelectorAll('[data-inline-validation]')) error.remove();
            for (const input of form.querySelectorAll('[data-wizard-invalid]')) {
                input.removeAttribute('aria-invalid'); input.classList.remove('is-invalid');
                input.removeAttribute('data-wizard-invalid'); input.removeAttribute('aria-describedby');
            }
        };
        const showErrors = errors => {
            clearErrors();
            const title = document.createElement('strong');
            title.textContent = 'כדי להמשיך יש להשלים:';
            const list = document.createElement('ul');
            for (const {target, message} of errors) {
                const error = document.createElement('p');
                error.className = 'o_field_inline_error'; error.dataset.inlineValidation = '1';
                error.id = `${target.id}-validation`; error.textContent = message;
                target.parentElement.append(error);
                target.dataset.wizardInvalid = '1'; target.setAttribute('aria-invalid', 'true');
                target.setAttribute('aria-describedby', error.id); target.classList.add('is-invalid');
                const item = document.createElement('li'); const link = document.createElement('a');
                link.href = `#${target.id}`; link.textContent = message;
                link.addEventListener('click', event => { event.preventDefault(); target.focus(); });
                item.append(link); list.append(item);
            }
            errorSummary.append(title, list); errorSummary.hidden = false; errorSummary.focus();
        };
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
                    img.width = 320; img.height = 240;
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
            input.setAttribute('aria-hidden', 'true');
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
        const panels = [...form.querySelectorAll('[data-wizard-panel]')];
        const next = form.querySelector('[data-wizard-next]');
        const back = form.querySelector('[data-wizard-back]');
        const nav = form.querySelector('[data-wizard-nav]');
        let step = 1;
        const validation = target => {
            const errors = [];
            if (target > 1) {
                if (!result.value) errors.push({target: result, message: 'בחרו את תוצאת הביקור.'});
                if (result.value === 'completed' && !summary.value.trim()) errors.push({target: summary, message: 'כתבו מה בוצע בפועל כדי לשלוח עבודה שהושלמה.'});
                if (result.value && result.value !== 'completed' && !reason.value.trim()) errors.push({target: reason, message: 'פרטו מה מנע השלמה ומה נדרש להמשך.'});
            }
            if (!errors.length && target > 2 && result.value === 'completed') {
                for (const gallery of galleries) {
                    const button = gallery.root.querySelector('[data-select-photo]');
                    if (!count(gallery)) errors.push({target: button, message: `הוסיפו לפחות תמונה אחת ${gallery.root.dataset.kind === 'before' ? 'לפני ביצוע' : 'אחרי ביצוע'}.`});
                }
            }
            return errors;
        };
        const go = (target, focus = true) => {
            const errors = target > step ? validation(target) : [];
            if (errors.length) { showErrors(errors); return; }
            clearErrors(); step = target;
            panels.forEach(panel => { panel.hidden = Number(panel.dataset.wizardPanel) !== step; });
            for (const button of nav.querySelectorAll('[data-wizard-go]')) {
                if (Number(button.dataset.wizardGo) === step) button.setAttribute('aria-current', 'step');
                else button.removeAttribute('aria-current');
            }
            next.hidden = step === 3; back.hidden = step === 1; submit.hidden = step !== 3;
            next.textContent = step === 1 ? 'המשך לתמונות' : 'המשך לבדיקה ושליחה';
            form.querySelector('[data-report-step-note]').textContent = `שלב ${step} מתוך 3 — ${['דיווח הביקור','תמונות','בדיקה ושליחה'][step - 1]}`;
            if (step === 3) {
                form.querySelector('[data-review-result]').textContent = `תוצאת הביקור: ${result.selectedOptions[0].textContent}`;
                form.querySelector('[data-review-description]').textContent = result.value === 'completed' ? summary.value : reason.value;
                form.querySelector('[data-review-photos]').textContent = `${galleries.map(count)[0]} תמונות לפני · ${galleries.map(count)[1]} תמונות אחרי`;
            }
            history.replaceState(null, '', `${location.pathname}${location.search}#report-step-${step}`);
            if (focus) panels.find(panel => Number(panel.dataset.wizardPanel) === step).querySelector('[data-wizard-heading]').focus();
        };
        if (nav) {
            nav.hidden = false;
            for (const gallery of galleries) gallery.root.querySelector('[data-select-photo]').id = `photo-${gallery.root.dataset.kind}-select`;
            next.addEventListener('click', () => go(Math.min(step + 1, 3)));
            back.addEventListener('click', () => go(Math.max(step - 1, 1)));
            nav.querySelectorAll('[data-wizard-go]').forEach(button => button.addEventListener('click', () => go(Number(button.dataset.wizardGo))));
            go(1, false);
        }
        form.addEventListener('change', () => { dirty = true; });
        form.addEventListener('input', () => { dirty = true; });
        window.addEventListener('beforeunload', event => {
            if (dirty && form.dataset.submitting !== '1') { event.preventDefault(); event.returnValue = ''; }
        });
        form.addEventListener('submit', event => {
            if (form.dataset.submitting === '1') {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = '1';
            dirty = false;
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

