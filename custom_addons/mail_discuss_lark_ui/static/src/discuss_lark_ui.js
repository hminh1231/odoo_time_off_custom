/** @odoo-module **/

import { DiscussClientAction } from "@mail/core/public_web/discuss_client_action";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

import { browser } from "@web/core/browser/browser";
import { Component, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useBus, useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const LARK_SHORTCUT_APPS_MAX = 4;
const LARK_BAR_SLOT_COUNT = 4;
const LARK_DRAG_TOUCH_DELAY = 380;
const LARK_DRAG_MOVE_TOLERANCE = 8;

const SHORTCUT_MENU_XMLIDS = [
    "mail.menu_root_discuss",
    "calendar.mail_menu_calendar",
    "hr_holidays.menu_hr_holidays_root",
    "project_todo.menu_todo_todos",
];

const LARK_BODY_CLASS = "o-mail-lark-ui";
const LARK_MOBILE_SHELL_CLASS = "o-mail-lark-mobile-shell";
const LARK_ALLAPPS_OPEN_CLASS = "o-mail-lark-allapps-open";
const LARK_DRAGGING_CLASS = "o-mail-lark-dragging";

function larkShortcutsStorageKey() {
    return `mail_discuss_lark_ui.shortcuts.v1.${user.userId}`;
}

function normalizeShortcutSlots(xmlids) {
    const slots = [null, null, null, null];
    let index = 0;
    for (const xmlid of xmlids) {
        if (typeof xmlid !== "string" || !xmlid || slots.includes(xmlid) || index >= LARK_BAR_SLOT_COUNT) {
            continue;
        }
        slots[index++] = xmlid;
    }
    return slots;
}

function loadShortcutSlots() {
    try {
        const raw = browser.localStorage.getItem(larkShortcutsStorageKey());
        if (!raw) {
            return normalizeShortcutSlots(SHORTCUT_MENU_XMLIDS);
        }
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return normalizeShortcutSlots(SHORTCUT_MENU_XMLIDS);
        }
        const slots = [null, null, null, null];
        for (let i = 0; i < LARK_BAR_SLOT_COUNT; i++) {
            const value = parsed[i];
            slots[i] = typeof value === "string" && value ? value : null;
        }
        return normalizeShortcutSlots(slots.filter(Boolean));
    } catch {
        return normalizeShortcutSlots(SHORTCUT_MENU_XMLIDS);
    }
}

function saveShortcutSlots(slots) {
    try {
        browser.localStorage.setItem(
            larkShortcutsStorageKey(),
            JSON.stringify(slots.slice(0, LARK_BAR_SLOT_COUNT))
        );
    } catch {
        // ignore quota errors
    }
}

function isMobileUi(ui) {
    if (ui?.isSmall) {
        return true;
    }
    return typeof window !== "undefined" && window.matchMedia("(max-width: 767.98px)").matches;
}

function useLarkAppsBarDrag(component) {
    component.larkDragState = useState({
        active: false,
        xmlid: null,
        source: null,
        barSlotIndex: null,
        hoverSlot: null,
        overGrid: false,
    });
    component._larkDragPending = null;
    component._larkDragGhost = null;
    component._larkDidDrag = false;

    const clearPending = () => {
        if (component._larkDragPending?.timer) {
            clearTimeout(component._larkDragPending.timer);
        }
        component._larkDragPending = null;
    };

    const clearGhost = () => {
        component._larkDragGhost?.remove();
        component._larkDragGhost = null;
    };

    const endDrag = () => {
        clearPending();
        clearGhost();
        component.larkDragState.active = false;
        component.larkDragState.xmlid = null;
        component.larkDragState.source = null;
        component.larkDragState.barSlotIndex = null;
        component.larkDragState.hoverSlot = null;
        component.larkDragState.overGrid = false;
        document.body.classList.remove(LARK_DRAGGING_CLASS);
    };

    const createGhost = (sourceEl) => {
        clearGhost();
        const rect = sourceEl.getBoundingClientRect();
        const ghost = sourceEl.cloneNode(true);
        ghost.classList.add("o-mail-LarkDragGhost");
        ghost.style.width = `${rect.width}px`;
        ghost.style.height = `${rect.height}px`;
        ghost.style.left = `${rect.left}px`;
        ghost.style.top = `${rect.top}px`;
        document.body.appendChild(ghost);
        component._larkDragGhost = ghost;
        return { ghost, offsetX: rect.width / 2, offsetY: rect.height / 2 };
    };

    const moveGhost = (clientX, clientY, offsetX, offsetY) => {
        if (!component._larkDragGhost) {
            return;
        }
        component._larkDragGhost.style.left = `${clientX - offsetX}px`;
        component._larkDragGhost.style.top = `${clientY - offsetY}px`;
    };

    const updateDropHighlight = (clientX, clientY) => {
        const el = document.elementFromPoint(clientX, clientY);
        const slotEl = el?.closest?.("[data-lark-bar-slot]");
        const gridEl = el?.closest?.("[data-lark-allapps-grid]");
        component.larkDragState.hoverSlot = slotEl
            ? Number.parseInt(slotEl.dataset.larkBarSlot, 10)
            : null;
        component.larkDragState.overGrid = Boolean(gridEl);
    };

    const startDrag = (pending, sourceEl) => {
        component._larkDidDrag = true;
        const { ghost, offsetX, offsetY } = createGhost(sourceEl);
        component.larkDragState.active = true;
        component.larkDragState.xmlid = pending.xmlid;
        component.larkDragState.source = pending.source;
        component.larkDragState.barSlotIndex = pending.barSlotIndex;
        document.body.classList.add(LARK_DRAGGING_CLASS);
        component._larkDragPending = { ...pending, offsetX, offsetY, ghost };
        moveGhost(pending.startX, pending.startY, offsetX, offsetY);
        updateDropHighlight(pending.startX, pending.startY);
    };

    const onDocumentPointerMove = (ev) => {
        const pending = component._larkDragPending;
        if (!pending) {
            return;
        }
        if (!component.larkDragState.active) {
            const dx = Math.abs(ev.clientX - pending.startX);
            const dy = Math.abs(ev.clientY - pending.startY);
            if (dx > LARK_DRAG_MOVE_TOLERANCE || dy > LARK_DRAG_MOVE_TOLERANCE) {
                clearPending();
            }
            return;
        }
        ev.preventDefault();
        moveGhost(ev.clientX, ev.clientY, pending.offsetX, pending.offsetY);
        updateDropHighlight(ev.clientX, ev.clientY);
    };

    const onDocumentPointerUp = (ev) => {
        const pending = component._larkDragPending;
        if (!pending) {
            return;
        }
        if (component.larkDragState.active) {
            component.larkDropAtPointer(ev.clientX, ev.clientY);
        }
        endDrag();
        window.setTimeout(() => {
            component._larkDidDrag = false;
        }, 0);
    };

    onMounted(() => {
        document.addEventListener("pointermove", onDocumentPointerMove, { passive: false });
        document.addEventListener("pointerup", onDocumentPointerUp);
        document.addEventListener("pointercancel", onDocumentPointerUp);
        component._larkDragDocCleanup = () => {
            document.removeEventListener("pointermove", onDocumentPointerMove);
            document.removeEventListener("pointerup", onDocumentPointerUp);
            document.removeEventListener("pointercancel", onDocumentPointerUp);
        };
    });

    onWillUnmount(() => {
        component._larkDragDocCleanup?.();
        endDrag();
    });

    Object.assign(component, {
        onLarkAppDragPointerDown(ev) {
            if (!component.larkAppsMenu.open) {
                return;
            }
            const handle = ev.currentTarget;
            const xmlid = handle.dataset.larkXmlid;
            if (!xmlid) {
                return;
            }
            const source = handle.dataset.larkDragSource;
            const barSlotIndex =
                source === "bar" ? Number.parseInt(handle.dataset.larkBarSlot, 10) : null;
            clearPending();
            const pending = {
                xmlid,
                source,
                barSlotIndex: Number.isNaN(barSlotIndex) ? null : barSlotIndex,
                startX: ev.clientX,
                startY: ev.clientY,
                pointerId: ev.pointerId,
            };
            pending.timer = window.setTimeout(() => {
                if (component._larkDragPending === pending) {
                    startDrag(pending, handle);
                }
            }, LARK_DRAG_TOUCH_DELAY);
            component._larkDragPending = pending;
            if (handle.setPointerCapture) {
                try {
                    handle.setPointerCapture(ev.pointerId);
                } catch {
                    // ignore
                }
            }
        },

        onLarkAppDragPointerUp(ev) {
            if (!component.larkDragState.active) {
                clearPending();
            }
            const handle = ev.currentTarget;
            if (handle.releasePointerCapture) {
                try {
                    handle.releasePointerCapture(ev.pointerId);
                } catch {
                    // ignore
                }
            }
        },
    });
}

function useLarkAppsBar(component) {
    component.menuService = useService("menu");
    component.ui = useService("ui");
    component.larkAppsMenu = useState({ open: false });
    component.shellState = useState({ fullscreen: false });
    component.larkMediaState = useState({ mobile: isMobileUi(component.ui) });
    component.larkShortcutSlots = useState(loadShortcutSlots());

    useLarkAppsBarDrag(component);

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

function larkAppsByXmlid(menuService) {
    return new Map(
        menuService
            .getApps()
            .filter((app) => app.xmlid)
            .map((app) => [app.xmlid, app])
    );
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
        larkAppsByXmlid: {
            get() {
                return larkAppsByXmlid(this.menuService);
            },
            configurable: true,
        },
        larkBarSlots: {
            get() {
                const appsByXmlid = this.larkAppsByXmlid;
                return this.larkShortcutSlots.map((xmlid, index) => ({
                    index,
                    xmlid,
                    app: xmlid ? appsByXmlid.get(xmlid) : null,
                }));
            },
            configurable: true,
        },
        larkShortcutApps: {
            get() {
                return this.larkBarSlots
                    .map((slot) => slot.app)
                    .filter(Boolean)
                    .slice(0, LARK_SHORTCUT_APPS_MAX);
            },
            configurable: true,
        },
        larkBarFilledCount: {
            get() {
                return this.larkShortcutSlots.filter(Boolean).length;
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
        larkCustomizeHint: {
            get() {
                return _t("Giữ và kéo ứng dụng xuống thanh dưới (tối đa 4)");
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

        larkIsAppInBar(xmlid) {
            return Boolean(xmlid && this.larkShortcutSlots.includes(xmlid));
        },

        larkPersistShortcutSlots(slots) {
            const next = slots.slice(0, LARK_BAR_SLOT_COUNT);
            while (next.length < LARK_BAR_SLOT_COUNT) {
                next.push(null);
            }
            const seen = new Set();
            for (let i = 0; i < LARK_BAR_SLOT_COUNT; i++) {
                const xmlid = next[i];
                if (!xmlid) {
                    next[i] = null;
                    continue;
                }
                if (!this.larkAppsByXmlid.has(xmlid) || seen.has(xmlid)) {
                    next[i] = null;
                } else {
                    seen.add(xmlid);
                }
            }
            this.larkShortcutSlots.splice(0, this.larkShortcutSlots.length, ...next);
            saveShortcutSlots(next);
        },

        larkDropAtPointer(clientX, clientY) {
            const xmlid = this.larkDragState.xmlid;
            const source = this.larkDragState.source;
            if (!xmlid) {
                return;
            }
            const el = document.elementFromPoint(clientX, clientY);
            const gridEl = el?.closest?.("[data-lark-allapps-grid]");
            const slotEl = el?.closest?.("[data-lark-bar-slot]");

            if (gridEl && source === "bar") {
                this.larkRemoveShortcutFromBar(this.larkDragState.barSlotIndex);
                return;
            }
            if (!slotEl) {
                return;
            }
            const slotIndex = Number.parseInt(slotEl.dataset.larkBarSlot, 10);
            if (Number.isNaN(slotIndex)) {
                return;
            }
            this.larkAssignShortcutToSlot(slotIndex, xmlid, source, this.larkDragState.barSlotIndex);
        },

        larkRemoveShortcutFromBar(slotIndex) {
            if (slotIndex == null || slotIndex < 0 || slotIndex >= LARK_BAR_SLOT_COUNT) {
                return;
            }
            const slots = [...this.larkShortcutSlots];
            slots[slotIndex] = null;
            this.larkPersistShortcutSlots(slots);
        },

        larkAssignShortcutToSlot(slotIndex, xmlid, source, fromBarSlotIndex) {
            if (!xmlid || slotIndex < 0 || slotIndex >= LARK_BAR_SLOT_COUNT) {
                return;
            }
            const appsByXmlid = this.larkAppsByXmlid;
            if (!appsByXmlid.has(xmlid)) {
                return;
            }

            const slots = [...this.larkShortcutSlots];
            const targetOccupied = Boolean(slots[slotIndex]);

            if (source === "grid") {
                const fromSlot = slots.indexOf(xmlid);
                if (fromSlot >= 0) {
                    slots[fromSlot] = null;
                }
                const filledAfterRemove = slots.filter(Boolean).length;
                if (!targetOccupied && filledAfterRemove >= LARK_SHORTCUT_APPS_MAX) {
                    return;
                }
                slots[slotIndex] = xmlid;
            } else if (source === "bar") {
                if (fromBarSlotIndex == null || fromBarSlotIndex < 0) {
                    return;
                }
                if (fromBarSlotIndex === slotIndex) {
                    return;
                }
                const moving = slots[fromBarSlotIndex];
                slots[fromBarSlotIndex] = slots[slotIndex];
                slots[slotIndex] = moving;
            }

            for (let i = 0; i < LARK_BAR_SLOT_COUNT; i++) {
                if (i !== slotIndex && slots[i] === xmlid) {
                    slots[i] = null;
                }
            }

            this.larkPersistShortcutSlots(slots);
        },

        onLarkMoreAppsClick() {
            this.larkAppsMenu.open = true;
        },

        onLarkAllAppsClose() {
            this.larkAppsMenu.open = false;
        },

        async onLarkAppClick(app, ev) {
            if (this._larkDidDrag || this.larkDragState.active) {
                ev?.preventDefault?.();
                ev?.stopPropagation?.();
                return;
            }
            await this.menuService.selectMenu(app);
        },

        async onLarkAllAppClick(app, ev) {
            if (this._larkDidDrag || this.larkDragState.active) {
                ev?.preventDefault?.();
                ev?.stopPropagation?.();
                return;
            }
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
