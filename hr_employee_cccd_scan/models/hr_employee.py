# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import date

from odoo import api, models, _
from odoo.tools.misc import format_date


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_scan_id_card(self):
        """Open the device camera dialog (browser); OCR/autofill comes later.

        On an unsaved new employee form, the web client calls this with an empty
        id list (browse([])). Do not use ensure_one() or the RPC fails and the
        dialog never opens.
        """
        employee = self[:1]
        return {
            'type': 'ir.actions.client',
            'tag': 'hr_employee_open_id_camera',
            'params': {
                'employee_id': employee.id if employee else False,
            },
        }

    @api.model
    def action_decode_cccd_qr(self, image_base64=None, **kwargs):
        """Decode QR from a base64 image string using OpenCV on server."""
        image_base64 = image_base64 or kwargs.get('image_base64')
        if not image_base64:
            return {'ok': False, 'error': self.env._('Missing image payload.')}
        try:
            import cv2
            import numpy as np
        except Exception:
            return {
                'ok': False,
                'error': self.env._(
                    "Server QR decoder is unavailable. Install dependency: pip install opencv-python zxing-cpp"
                ),
            }
        try:
            image_bytes = base64.b64decode(image_base64)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if image is None:
                return {'ok': False, 'error': self.env._('Could not decode image bytes.')}
            h, w = image.shape[:2]

            # CCCD QR is usually on the upper-right area. Try focused crops first.
            focused_crops = [
                image,  # full frame first
                image[0 : int(h * 0.70), int(w * 0.35) : w],  # right-upper large
                image[0 : int(h * 0.55), int(w * 0.50) : w],  # right-upper tighter
                image[int(h * 0.10) : int(h * 0.80), int(w * 0.40) : w],  # right vertical band
            ]

            # 1) Prefer zxing-cpp (more robust for noisy / perspective QR).
            try:
                import zxingcpp

                for crop in focused_crops:
                    result = zxingcpp.read_barcode(crop)
                    if result and result.text:
                        return {'ok': True, 'text': result.text}
                    for scale in (1.5, 2.0, 2.5):
                        up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                        result = zxingcpp.read_barcode(up)
                        if result and result.text:
                            return {'ok': True, 'text': result.text}
            except Exception:
                # Fallback to OpenCV below
                pass

            # 2) OpenCV fallback pipeline.
            detector = cv2.QRCodeDetector()
            candidates = list(focused_crops)

            # Enhance low-light / blur cases: grayscale + denoise + adaptive threshold.
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (3, 3), 0)
            thresh = cv2.adaptiveThreshold(
                blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 3
            )
            candidates.extend([gray, blur, thresh])
            # Also preprocess likely QR area only.
            gray_crop = cv2.cvtColor(focused_crops[1], cv2.COLOR_BGR2GRAY)
            thresh_crop = cv2.adaptiveThreshold(
                gray_crop, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 3
            )
            candidates.extend([gray_crop, thresh_crop])

            # QR on CCCD may occupy a small area; try larger scales.
            for scale in (1.25, 1.5, 2.0):
                candidates.append(
                    cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                )
                candidates.append(
                    cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                )
                candidates.append(
                    cv2.resize(thresh, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                )

            for candidate in candidates:
                text, _, _ = detector.detectAndDecode(candidate)
                if text:
                    return {'ok': True, 'text': text}

            return {'ok': False, 'error': self.env._('No QR code found in image.')}
        except Exception:
            return {'ok': False, 'error': self.env._('QR decoding failed on server.')}

    @api.model
    def parse_cccd_qr_payload(self, qr_text=None, **kwargs):
        """Map Vietnamese CCCD QR pipe-delimited text to hr.employee writable values (JSON-safe)."""
        qr_text = (qr_text or kwargs.get('qr_text') or '').strip()
        if not qr_text:
            return {'ok': False, 'error': _('Empty QR payload.')}
        parts = [p.strip() for p in qr_text.split('|')]
        if len(parts) < 7:
            return {'ok': False, 'error': _('QR format not recognized (expected CCCD data).')}

        cccd = parts[0]
        old_id = parts[1]
        full_name = parts[2]
        dob_raw = parts[3]
        gender_raw = (parts[4] or '').strip()
        address = (parts[5] or '').strip()

        vals = {}
        if full_name:
            vals['name'] = full_name
        if cccd:
            vals['identification_id'] = cccd
        if old_id and old_id not in ('0', '000000000', ''):
            vals['ssnid'] = old_id

        if dob_raw and len(dob_raw) == 8 and dob_raw.isdigit():
            dd = int(dob_raw[0:2])
            mm = int(dob_raw[2:4])
            yyyy = int(dob_raw[4:8])
            try:
                vals['birthday'] = date(yyyy, mm, dd).isoformat()
            except ValueError:
                pass

        if gender_raw:
            gc = gender_raw.casefold().strip()
            if gc in ('nam', 'male'):
                vals['sex'] = 'male'
            elif gc in ('nữ', 'female') or gc == 'nu':
                vals['sex'] = 'female'
            else:
                vals['sex'] = 'other'

        if address:
            vals['private_street'] = address

        vn = self.env['res.country'].sudo().search([('code', '=', 'VN')], limit=1)
        if vn:
            vals['private_country_id'] = vn.id
            # CCCD is a Vietnamese national ID → set nationality (Nationality / country_id).
            vals['country_id'] = vn.id

        if not any(k in vals for k in ('name', 'identification_id', 'birthday', 'private_street')):
            return {'ok': False, 'error': _('No usable fields could be read from the QR code.')}

        preview_rows = []
        if full_name:
            preview_rows.append({'label': _('Full name'), 'value': full_name})
        if cccd:
            preview_rows.append({'label': _('Citizen ID (CCCD)'), 'value': cccd})
        if old_id and old_id not in ('0', '000000000', ''):
            preview_rows.append({'label': _('Former ID (CMND)'), 'value': old_id})
        if 'birthday' in vals:
            bd = date.fromisoformat(vals['birthday'])
            preview_rows.append({'label': _('Date of birth'), 'value': format_date(self.env, bd)})
        sex_display = {'male': _('Male'), 'female': _('Female'), 'other': _('Other')}
        if vals.get('sex'):
            preview_rows.append({
                'label': _('Gender'),
                'value': sex_display.get(vals['sex'], vals['sex']),
            })
        if address:
            preview_rows.append({'label': _('Private address'), 'value': address})
        if vals.get('country_id') and vn:
            preview_rows.append({'label': _('Nationality'), 'value': vn.name})
        if vn:
            preview_rows.append({'label': _('Private country'), 'value': vn.name})

        return {'ok': True, 'values': vals, 'preview_rows': preview_rows}
