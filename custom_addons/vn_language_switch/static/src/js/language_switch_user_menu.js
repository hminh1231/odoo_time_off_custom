/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { session } from "@web/session";

function isVietnameseLangCode(langCode) {
    return (langCode || "").toLowerCase().startsWith("vi");
}

function languageSwitchItem(env) {
    const currentLang = session.user_context?.lang || user.context?.lang || "en_US";
    const isVietnamese = isVietnameseLangCode(currentLang);
    return {
        type: "item",
        id: "vn_language_switch",
        description:
            isVietnamese
                ? _t("Ngon ngu: Tieng Viet (Switch to English)")
                : _t("Language: English (Chuyen sang Tieng Viet)"),
        show: () => Boolean(session.enable_user_language_switch),
        callback: async () => {
            const latestLang = session.user_context?.lang || user.context?.lang || "en_US";
            const nextLang = isVietnameseLangCode(latestLang) ? "en_US" : "vi_VN";
            await env.services.orm.write("res.users", [user.userId], { lang: nextLang });
            window.location.reload();
        },
        sequence: 55,
    };
}

registry.category("user_menuitems").add("vn_language_switch", languageSwitchItem);
