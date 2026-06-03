/** @odoo-module **/

import { Discuss } from "@mail/core/public_web/discuss";
import { DiscussClientAction } from "@mail/core/public_web/discuss_client_action";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

import { onMounted, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/** App shortcuts before the "See more" slot (4 + 1 more = 5 items on the bar). */
const LARK_SHORTCUT_APPS_MAX = 4;

/** Priority order for pinned shortcuts. */
const SHORTCUT_MENU_XMLIDS = [
    "mail.menu_root_discuss",
    "calendar.mail_menu_calendar",
    "hr_holidays.menu_hr_holidays_root",
    "project_todo.menu_todo_todos",
];

const LARK_BODY_CLASS = "o-mail-lark-ui";

function isMobileUi(ui) {
    if (ui?.isSmall) {
        return true;
    }
    return typeof window !== "undefined" && window.matchMedia("(max-width: 767.98px)").matches;
}

function setLarkUiActive(active) {
    document.body.classList.toggle(LARK_BODY_CLASS, active);
}

function bindLarkUiOnAction(component) {
    const ui = component.env.services.ui;
    onMounted(() => {
        if (isMobileUi(ui)) {
            setLarkUiActive(true);
        }
    });
    onWillUnmount(() => {
        if (isMobileUi(ui)) {
            setLarkUiActive(false);
        }
    });
}

patch(DiscussClientAction.prototype, {
    setup() {
        super.setup();
        bindLarkUiOnAction(this);
    },
});

patch(Discuss.prototype, {
    setup() {
        super.setup();
        this.menuService = useService("menu");
        this.larkAppsMenu = useState({ open: false });
        bindLarkUiOnAction(this);
    },

    get larkShortcutApps() {
        const appsByXmlid = new Map(
            this.menuService.getApps().filter((app) => app.xmlid).map((app) => [app.xmlid, app])
        );
        return SHORTCUT_MENU_XMLIDS.map((xmlid) => appsByXmlid.get(xmlid))
            .filter(Boolean)
            .slice(0, LARK_SHORTCUT_APPS_MAX);
    },

    get larkAllApps() {
        return this.menuService.getApps();
    },

    get larkCurrentAppId() {
        return this.menuService.getCurrentApp()?.id;
    },

    get larkSeeMoreLabel() {
        return _t("Xem thêm");
    },

    get larkAllAppsTitle() {
        return _t("Tất cả ứng dụng");
    },

    larkAppIconStyle(app) {
        if (!app.webIcon) {
            return "";
        }
        const { backgroundColor, color } = app.webIcon;
        let style = "";
        if (backgroundColor) {
            style += `background-color:${backgroundColor};`;
        }
        if (color) {
            style += `color:${color};`;
        }
        return style;
    },

    onLarkMoreAppsClick() {
        this.larkAppsMenu.open = true;
    },

    onLarkAllAppsClose() {
        this.larkAppsMenu.open = false;
    },

    async onLarkAppClick(app) {
        await this.menuService.selectMenu(app);
    },

    async onLarkAllAppClick(app) {
        await this.menuService.selectMenu(app);
        this.larkAppsMenu.open = false;
    },
});

patch(MessagingMenu.prototype, {
    onLarkSearchClick() {
        document.querySelector(".o-mail-DiscussSearch-inputClickable")?.click();
    },

    onLarkComposeClick() {
        const meetingBtn = document.querySelector(".o-mail-DiscussSearch button[data-hotkey='m']");
        if (meetingBtn) {
            meetingBtn.click();
            return;
        }
        this.env.services.command?.openMainPalette({ searchValue: "@" });
    },
});
