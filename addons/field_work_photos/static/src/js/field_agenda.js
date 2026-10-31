/** @odoo-module **/

import { registry } from '@web/core/registry';
import { useHotkey } from '@web/core/hotkeys/hotkey_hook';
import { KanbanRenderer } from '@web/views/kanban/kanban_renderer';
import { kanbanView } from '@web/views/kanban/kanban_view';
import { X2ManyField, x2ManyField } from '@web/views/fields/x2many/x2many_field';

// Odoo's card-level Enter hotkey also consumes Enter on nested buttons.
// Register after the native hook, only in our two readonly action-card surfaces.
class FieldWorkActionRenderer extends KanbanRenderer {
    setup() {
        super.setup();
        useHotkey('Enter', ({ target }) => {
            const action = target.closest('button[name="action_open_field_workspace"], button[name="action_open_field_work_card"]');
            if (action && this.rootRef.el.contains(action)) {
                action.click();
            } else if (target.classList.contains('o_kanban_record')) {
                target.querySelector('button[name="action_open_field_workspace"], button[name="action_open_field_work_card"]')?.click();
            }
        }, { area: () => this.rootRef.el });
    }
}

class FieldWorkAttention extends X2ManyField {
    static components = { ...X2ManyField.components, KanbanRenderer: FieldWorkActionRenderer };
}

registry.category('fields').add('field_work_attention', { ...x2ManyField, component: FieldWorkAttention });
registry.category('views').add('field_work_agenda', { ...kanbanView, Renderer: FieldWorkActionRenderer });
