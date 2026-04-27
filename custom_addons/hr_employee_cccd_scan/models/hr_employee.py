# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import date

from odoo import api, fields, models, _
from odoo.tools.misc import format_date


def _normalize_vn_cccd_qr_text(raw):
    """Strip BOM; accept fullwidth vertical bar (common OCR/scan quirk)."""
    if not raw:
        return ''
    t = raw.strip().lstrip('\ufeff')
    t = t.replace('｜', '|')  # U+FF5C fullwidth
    return t.strip()


def _cccd_focus_crops(image):
    """Regions where CCCD QR usually sits (back of card, upper-right)."""
    h, w = image.shape[:2]
    if h < 32 or w < 32:
        return [image]
    crops = [
        image,
        image[0 : int(h * 0.72), int(w * 0.30) : w],
        image[0 : int(h * 0.60), int(w * 0.45) : w],
        image[0 : int(h * 0.50), int(w * 0.52) : w],
        image[int(h * 0.05) : int(h * 0.75), int(w * 0.38) : w],
        image[int(h * 0.02) : int(h * 0.48), int(w * 0.55) : w],
    ]
    return [c for c in crops if c.size and min(c.shape[:2]) >= 16]


def _preprocess_for_qr(image_bgr):
    """Yield BGR / grayscale / enhanced copies for decoders (blur, low light)."""
    import cv2
    import numpy as np

    h, w = image_bgr.shape[:2]
    yield image_bgr
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    yield gray
    if min(h, w) < 16:
        return
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        yield clahe.apply(gray)
    except Exception:
        pass
    if min(h, w) >= 32:
        try:
            yield cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        except Exception:
            pass
    try:
        blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=1.2)
        yield cv2.addWeighted(gray, 1.6, blur, -0.6, 0)
    except Exception:
        pass
    try:
        kernel = np.array([[-1.0, -1.0, -1.0], [-1.0, 9.0, -1.0], [-1.0, -1.0, -1.0]])
        yield cv2.filter2D(gray, -1, kernel)
    except Exception:
        pass
    for block, c in ((31, 4), (21, 3), (41, 5)):
        if min(h, w) < block + 4:
            continue
        try:
            yield cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c
            )
        except Exception:
            pass
    try:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield otsu
    except Exception:
        pass


def _try_zxing_on_array(arr):
    """Decode QR with zxing-cpp; safe per-call (no broad swallow of whole pipeline)."""
    try:
        import zxingcpp
    except Exception:
        return None
    if arr is None or not getattr(arr, 'size', 0):
        return None
    sh = arr.shape[:2]
    if min(sh) < 12:
        return None
    try:
        for binarizer in (
            zxingcpp.Binarizer.LocalAverage,
            zxingcpp.Binarizer.GlobalHistogram,
        ):
            result = zxingcpp.read_barcode(
                arr,
                formats=zxingcpp.BarcodeFormat.QRCode,
                try_rotate=True,
                try_downscale=True,
                try_invert=True,
                binarizer=binarizer,
            )
            if result and result.text:
                return result.text
    except Exception:
        return None
    return None


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    id_card_front = fields.Binary(string='ID Card Front', groups='hr.group_hr_user', attachment=True)
    id_card_front_filename = fields.Char(string='ID Card Front Filename', groups='hr.group_hr_user')
    id_card_back = fields.Binary(string='ID Card Back', groups='hr.group_hr_user', attachment=True)
    id_card_back_filename = fields.Char(string='ID Card Back Filename', groups='hr.group_hr_user')

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

    def _action_preview_binary_image(self, field_name):
        employee = self[:1]
        if not employee or not employee.id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Save Required'),
                    'message': _('Please save the employee before previewing ID images.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        if not employee[field_name]:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/image?model=hr.employee&id=%s&field=%s' % (employee.id, field_name),
            'target': 'new',
        }

    def action_preview_id_card_front(self):
        return self._action_preview_binary_image('id_card_front')

    def action_preview_id_card_back(self):
        return self._action_preview_binary_image('id_card_back')

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
            focused_crops = _cccd_focus_crops(image)
            scales = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)

            def _resize_scale(var, sc):
                if var.ndim not in (2, 3) or sc <= 1.01:
                    return var
                h, w = var.shape[:2]
                nw = max(1, int(w * sc))
                nh = max(1, int(h * sc))
                if nw * nh > 14_000_000:
                    return var
                return cv2.resize(var, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

            # 1) zxing-cpp: crops × preprocess × upscale (blur / low light / small QR).
            for crop in focused_crops:
                for variant in _preprocess_for_qr(crop):
                    for sc in scales:
                        arr = variant if sc <= 1.01 else _resize_scale(variant, sc)
                        text = _try_zxing_on_array(arr)
                        if text:
                            return {'ok': True, 'text': text}

            # 2) OpenCV QRCodeDetector on the same candidate pool.
            detector = cv2.QRCodeDetector()
            candidates = []
            for crop in focused_crops:
                for variant in _preprocess_for_qr(crop):
                    candidates.append(variant)
                    for sc in (1.25, 1.5, 2.0, 2.5, 3.0):
                        if variant.ndim == 2 or variant.ndim == 3:
                            candidates.append(_resize_scale(variant, sc))

            for candidate in candidates:
                ch, cw = candidate.shape[:2]
                if min(ch, cw) < 12:
                    continue
                text, _, _ = detector.detectAndDecode(candidate)
                if text:
                    return {'ok': True, 'text': text}
                try:
                    ok, decoded_info, _pts, _straight = detector.detectAndDecodeMulti(candidate)
                    if ok and decoded_info:
                        for t in decoded_info:
                            if t:
                                return {'ok': True, 'text': t}
                except Exception:
                    pass

            return {'ok': False, 'error': self.env._('No QR code found in image.')}
        except Exception:
            return {'ok': False, 'error': self.env._('QR decoding failed on server.')}

    @api.model
    def parse_cccd_qr_payload(self, qr_text=None, **kwargs):
        """Map Vietnamese CCCD QR pipe-delimited text to hr.employee writable values (JSON-safe).

        Official payloads are often 6–8 pipe-separated fields (newer cards may omit a trailing field).
        """
        qr_text = _normalize_vn_cccd_qr_text(qr_text or kwargs.get('qr_text') or '')
        if not qr_text:
            return {'ok': False, 'error': _('Empty QR payload.')}
        low = qr_text.casefold()
        if low.startswith('http://') or low.startswith('https://'):
            return {
                'ok': False,
                'error': _('This QR is a web link, not raw CCCD data. Use the QR on the back of the card.'),
            }
        parts = [p.strip() for p in qr_text.split('|')]
        if len(parts) < 6 and '\t' in qr_text:
            parts = [p.strip() for p in qr_text.split('\t')]
        if len(parts) < 6 and ';' in qr_text:
            parts = [p.strip() for p in qr_text.split(';')]
        if len(parts) < 6:
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
