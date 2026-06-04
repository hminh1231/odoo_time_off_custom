/** @odoo-module **/

import { DiscussClientAction } from "@mail/core/public_web/discuss_client_action";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

import { Component, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useBus, useService } from "@web/core/utils/hooks";

const LARK_SHORTCUT_APPS_MAX = 4;

const SHORTCUT_MENU_XMLIDS = [
    "mail.menu_root_discuss",
    "calendar.mail_menu_calendar",
    "hr_holidays.menu_hr_holidays_root",
    "project_todo.menu_todo_todos",
];

const LARK_BODY_CLASS = "o-mail-lark-ui";
const LARK_MOBILE_SHELL_CLASS = "o-mail-lark-mobile-shell";
const LARK_ALLAPPS_OPEN_CLASS = "o-mail-lark-allapps-open";

function isMobileUi(ui) {
    if (ui?.isSmall) {
        return true;
    }
    return typeof window !== "undefined" && window.matchMedia("(max-width: 767.98px)").matches;
}

function useLarkAppsBar(component) {
    component.menuService = useService("menu");
    component.ui = useService("ui");
    component.larkAppsMenu = useState({ open: false });
    component.shellState = useState({ fullscreen: false });
    component.larkMediaState = useState({ mobile: isMobileUi(component.ui) });

    useBus(component.env.bus, "ACTION_MANAGER:UI-UPDATED", ({ detail: mode }) => {
        component.shellState.fullscreen = mode === "fullscreen";
    });

    const syncMobile = () => {
        component.larkMediaState.mobile = isMobileUi(component.ui);
    };

    onMounted(() => {
        syncMobile();
        const mq = window.matchMedia("(max-width: 767.98px)");
        const onMqChange = () => syncMobile();
        mq.addEventListener("change", onMqChange);
        component._larkMqCleanup = () => mq.removeEventListener("change", onMqChange);
    });

    onWillUnmount(() => {
        component._larkMqCleanup?.();
        document.body.classList.remove(LARK_BODY_CLASS);
        document.body.classList.remove(LARK_MOBILE_SHELL_CLASS);
        document.body.classList.remove(LARK_ALLAPPS_OPEN_CLASS);
    });

    const syncShellClasses = () => {
        const active = component.larkShowAppsBar;
        document.body.classList.toggle(LARK_BODY_CLASS, active);
        document.body.classList.toggle(LARK_MOBILE_SHELL_CLASS, active);
        document.body.classList.toggle(
            LARK_ALLAPPS_OPEN_CLASS,
            active && component.larkAppsMenu.open
        );
    };

    useEffect(syncShellClasses, () => [
        component.larkMediaState.mobile,
        component.ui.isSmall,
        component.shellState.fullscreen,
        component.larkAppsMenu.open,
    ]);

    onMounted(syncShellClasses);
}

function larkAppsBarGetters(ComponentClass) {
    Object.defineProperties(ComponentClass.prototype, {
        larkShowAppsBar: {
            get() {
                const mobile = this.larkMediaState?.mobile ?? isMobileUi(this.ui);
                return mobile && !this.shellState?.fullscreen;
            },
            configurable: true,
        },
        larkShortcutApps: {
            get() {
                const appsByXmlid = new Map(
                    this.menuService
                        .getApps()
                        .filter((app) => app.xmlid)
                        .map((app) => [app.xmlid, app])
                );
                return SHORTCUT_MENU_XMLIDS.map((xmlid) => appsByXmlid.get(xmlid))
                    .filter(Boolean)
                    .slice(0, LARK_SHORTCUT_APPS_MAX);
            },
            configurable: true,
        },
        larkAllApps: {
            get() {
                return this.menuService.getApps();
            },
            configurable: true,
        },
        larkCurrentAppId: {
            get() {
                return this.menuService.getCurrentApp()?.id;
            },
            configurable: true,
        },
        larkSeeMoreLabel: {
            get() {
                return _t("Xem thêm");
            },
            configurable: true,
        },
        larkAllAppsTitle: {
            get() {
                return _t("Tất cả ứng dụng");
            },
            configurable: true,
        },
    });
}

function larkAppsBarMethods(ComponentClass) {
    Object.assign(ComponentClass.prototype, {
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
}

function bindDiscussLarkUi(component) {
    const ui = component.env.services.ui;
    onMounted(() => {
        if (isMobileUi(ui)) {
            document.body.classList.add("o-mail-lark-discuss");
        }
    });
    onWillUnmount(() => {
        document.body.classList.remove("o-mail-lark-discuss");
    });
}

patch(DiscussClientAction.prototype, {
    setup() {
        super.setup();
        bindDiscussLarkUi(this);
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

export class LarkMobileAppsBar extends Component {
    static template = "mail_discuss_lark_ui.LarkMobileAppsBar";
    static props = {};

    setup() {
        useLarkAppsBar(this);
    }
}

larkAppsBarGetters(LarkMobileAppsBar);
larkAppsBarMethods(LarkMobileAppsBar);

registry.category("main_components").add("LarkMobileAppsBar", {
    Component: LarkMobileAppsBar,
});
