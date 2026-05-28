import io
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_GOTENBERG_URL = "http://gotenberg:3000"
_WORD_MIMETYPES = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
})


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model_create_multi
    def create(self, vals_list):
        for i, vals in enumerate(vals_list):
            if vals.get("res_model") == "hr.leave" and vals.get("mimetype") in _WORD_MIMETYPES:
                vals_list[i] = self._convert_docx_to_pdf(vals)
        return super().create(vals_list)

    def _convert_docx_to_pdf(self, vals):
        """Convert a .doc/.docx attachment to PDF via Gotenberg before storing."""
        try:
            from gotenberg_client import GotenbergClient

            raw_bytes = vals.get("raw")
            if raw_bytes is None:
                import base64
                datas = vals.get("datas")
                if not datas:
                    return vals
                raw_bytes = base64.b64decode(datas)

            original_name = vals.get("name", "document.docx")
            original_mimetype = vals.get("mimetype", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            pdf_name = original_name.rsplit(".", 1)[0] + ".pdf"

            with GotenbergClient(_GOTENBERG_URL) as client:
                with client.libre_office.to_pdf() as route:
                    response = (
                        route
                        .convert_in_memory_file(
                            io.BytesIO(raw_bytes),
                            name=original_name,
                            mime_type=original_mimetype,
                        )
                        .run()
                    )

            pdf_bytes = response.content
            vals = dict(vals)
            vals["name"] = pdf_name
            vals["mimetype"] = "application/pdf"
            vals["raw"] = pdf_bytes
            vals.pop("datas", None)
            _logger.info("time_off_extra_approval: converted %r to PDF (%d bytes)", original_name, len(pdf_bytes))
        except Exception:
            _logger.exception(
                "time_off_extra_approval: docx→pdf conversion failed for %r, keeping original",
                vals.get("name"),
            )
        return vals
