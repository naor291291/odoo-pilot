/** @odoo-module **/

import { registry } from '@web/core/registry';
import { calendarView } from '@web/views/calendar/calendar_view';
import { CalendarRenderer } from '@web/views/calendar/calendar_renderer';
import { CalendarCommonRenderer } from '@web/views/calendar/calendar_common/calendar_common_renderer';
import { CalendarCommonPopover } from '@web/views/calendar/calendar_common/calendar_common_popover';

// Scoped view registration: native calendars outside field work are untouched.
class FieldWorkPopover extends CalendarCommonPopover {
    static template = 'field_work_photos.CalendarPopover';
    static subTemplates = {
        ...CalendarCommonPopover.subTemplates,
        popover: 'field_work_photos.CalendarPopoverCard',
        body: 'field_work_photos.CalendarPopoverBody',
        footer: 'field_work_photos.CalendarPopoverFooter',
    };
    get isEventDeletable() { return false; }
}

class FieldWorkCommonRenderer extends CalendarCommonRenderer {
    static components = { ...CalendarCommonRenderer.components, Popover: FieldWorkPopover };
}

class FieldWorkCalendarRenderer extends CalendarRenderer {
    static components = {
        ...CalendarRenderer.components,
        day: FieldWorkCommonRenderer,
        week: FieldWorkCommonRenderer,
        month: FieldWorkCommonRenderer,
    };
}

registry.category('views').add('field_work_calendar', {
    ...calendarView, Renderer: FieldWorkCalendarRenderer,
});
