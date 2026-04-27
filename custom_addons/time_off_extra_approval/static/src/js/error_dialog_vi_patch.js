/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { odooExceptionTitleMap } from "@web/core/errors/error_dialogs";

// Force Vietnamese title for validation popup in this custom deployment.
odooExceptionTitleMap.set("odoo.exceptions.ValidationError", _t("Lỗi xác thực"));
