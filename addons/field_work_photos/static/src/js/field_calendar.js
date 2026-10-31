/** @odoo-module **/

import { useEffect } from '@odoo/owl';
import { CalendarController } from '@web/views/calendar/calendar_controller';
import { is24HourFormat } from '@web/core/l10n/dates';
import { getFormattedDateSpan } from '@web/views/calendar/utils';
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
    computeDateTimeAndDuration() {
        super.computeDateTimeAndDuration();
        const { start, isTimeHidden, isAllDay } = this.props.record;
        // Only a start appointment is stored. Do not present FullCalendar's
        // default one-hour block as an agreed end time or work duration.
        if (!isTimeHidden && !isAllDay) this.time = start.toFormat(is24HourFormat() ? 'HH:mm' : 'hh:mm a');
        this.timeDuration = null;
        if (this.date) this.date = getFormattedDateSpan(start, start);
    }
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

class FieldWorkCalendarController extends CalendarController {
    setup() {
        super.setup();
        // A desktop sidebar left open makes the native mobile controller hide
        // the calendar. Collapse it when entering phone layout; users can still
        // explicitly open the mobile filters afterwards.
        useEffect(() => {
            if (this.env.isSmall) this.state.showSideBar = false;
        }, () => [this.env.isSmall]);
    }
}

registry.category('views').add('field_work_calendar', {
    ...calendarView, Controller: FieldWorkCalendarController, Renderer: FieldWorkCalendarRenderer,
});
