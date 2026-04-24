/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { Dialog } from "@web/core/dialog/dialog";
import { delay } from "@web/core/utils/concurrency";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useChildRef, useService } from "@web/core/utils/hooks";
import { Component, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";

/** Lazy-load Odoo's bundled ZXing (same as web barcode scanner fallback). */
let zxingLibraryPromise = null;
function ensureZXingLibraryLoaded() {
    if (window.ZXing) {
        return Promise.resolve();
    }
    if (!zxingLibraryPromise) {
        zxingLibraryPromise = loadJS("/web/static/lib/zxing-library/zxing-library.js");
    }
    return zxingLibraryPromise;
}

/**
 * @param {HTMLCanvasElement} canvas
 * @returns {string | null}
 */
function decodeQrFromCanvasWithZXing(canvas) {
    const ZXing = window.ZXing;
    if (!ZXing || !canvas?.width) {
        return null;
    }
    const hints = new Map([
        [ZXing.DecodeHintType.POSSIBLE_FORMATS, [ZXing.BarcodeFormat.QR_CODE]],
        [ZXing.DecodeHintType.TRY_HARDER, true],
    ]);
    const reader = new ZXing.MultiFormatReader();
    reader.setHints(hints);
    const luminanceSource = new ZXing.HTMLCanvasElementLuminanceSource(canvas);
    const binaryBitmap = new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(luminanceSource));
    try {
        return reader.decodeWithState(binaryBitmap).getText();
    } catch (err) {
        if (err.name === "NotFoundException") {
            return null;
        }
        throw err;
    }
}

/**
 * @param {HTMLCanvasElement} input
 * @param {number} scale
 * @returns {HTMLCanvasElement}
 */
function scaleCanvasUp(input, scale) {
    const out = document.createElement("canvas");
    out.width = Math.max(1, Math.floor(input.width * scale));
    out.height = Math.max(1, Math.floor(input.height * scale));
    const ctx = out.getContext("2d");
    if (!ctx) {
        return input;
    }
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(input, 0, 0, input.width, input.height, 0, 0, out.width, out.height);
    return out;
}

/**
 * Very large phone photos (12MP+) can freeze ZXing or the main thread; cap longest edge.
 * @param {HTMLCanvasElement} canvas
 * @param {number} maxSide
 * @returns {HTMLCanvasElement}
 */
function clampCanvasMaxSide(canvas, maxSide) {
    const w = canvas.width;
    const h = canvas.height;
    const longest = Math.max(w, h);
    if (!longest || longest <= maxSide) {
        return canvas;
    }
    const scale = maxSide / longest;
    const nw = Math.max(1, Math.floor(w * scale));
    const nh = Math.max(1, Math.floor(h * scale));
    const out = document.createElement("canvas");
    out.width = nw;
    out.height = nh;
    const ctx = out.getContext("2d");
    if (!ctx) {
        return canvas;
    }
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(canvas, 0, 0, w, h, 0, 0, nw, nh);
    return out;
}

/**
 * Try several getUserMedia constraints: laptops usually only have a "user" (front) webcam,
 * so "environment" (back camera) often fails and must fall back.
 *
 * @returns {Promise<MediaStream>}
 */
async function getBestCameraStream(isMobile) {
    const mobileAttempts = [
        {
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1920 },
                height: { ideal: 1080 },
            },
            audio: false,
        },
        {
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: false,
        },
        {
            video: { facingMode: { ideal: "environment" } },
            audio: false,
        },
        {
            video: { facingMode: { ideal: "user" } },
            audio: false,
        },
        { video: true, audio: false },
    ];
    const desktopAttempts = [
        {
            video: { facingMode: { ideal: "environment" } },
            audio: false,
        },
        {
            video: { facingMode: { ideal: "user" } },
            audio: false,
        },
        {
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: false,
        },
        { video: true, audio: false },
    ];
    const attempts = isMobile ? mobileAttempts : desktopAttempts;
    let lastError;
    for (const constraints of attempts) {
        try {
            return await navigator.mediaDevices.getUserMedia(constraints);
        } catch (e) {
            lastError = e;
        }
    }
    throw lastError;
}

function hasBarcodeDetector() {
    return typeof window.BarcodeDetector !== "undefined";
}

const LIVE_ROI = {
    x: 0.56,
    y: 0.08,
    w: 0.38,
    h: 0.56,
};

const CCCD_IMPORT_BUS = "hr_employee_cccd_scan:import";

/**
 * Dialog to capture an ID card photo. Mobile: file input with capture=environment
 * opens the device camera. Desktop: optional live preview via getUserMedia.
 */
export class IdCardCameraDialog extends Component {
    static template = "hr_employee_cccd_scan.IdCardCameraDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        employeeId: { type: Number, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.modalRef = useChildRef();
        this.fileInputRef = useRef("fileInput");
        this.videoRef = useRef("video");
        /** @type {MediaStream | null} */
        this.stream = null;
        this.autoScanTimer = null;
        /** @type {number | null} requestVideoFrameCallback handle */
        this._videoFrameCallbackHandle = null;
        this._lastLiveDecodeWallMs = 0;
        this._lastSilentLiveServerMs = 0;
        this.scanInProgress = false;
        this.state = useState({
            mode: "choose",
            previewUrl: null,
            error: null,
            qrText: null,
            /** @type {{ previewRows: {label: string, value: string}[], values: Record<string, unknown> } | null} */
            parsedImport: null,
        });
        onPatched(() => {
            if (this.state.mode === "live" && this.videoRef.el && this.stream) {
                const video = this.videoRef.el;
                if (video.srcObject === this.stream) {
                    return;
                }
                video.setAttribute("playsinline", "true");
                video.playsInline = true;
                video.muted = true;
                video.srcObject = this.stream;
                video.play().catch(() => {});
                // Stream attaches after render; start frame-driven scan once the video element exists.
                this._startAutoScan();
            }
        });
        onWillUnmount(() => this._cleanup());
    }

    get dialogTitle() {
        return _t("Scan ID card");
    }

    get isMobileDevice() {
        return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
    }

    get labelTakePhoto() {
        return _t("Take photo of ID card");
    }

    get labelLiveScanContinuous() {
        return _t("Live QR scan (auto, like Camera app)");
    }

    get labelLiveCamera() {
        return _t("Live camera in browser");
    }

    get mobileChooseHint() {
        return _t(
            "Use “Live QR scan” and point at the card — the code is read automatically. Use “Take photo” only if live scan does not work."
        );
    }

    get liveModeAutoHint() {
        return _t("Keep the QR inside the dashed frame; it is scanned continuously while the camera is on.");
    }

    get labelDecodedFields() {
        return _t("Information read from the QR code");
    }

    get labelImportQuestion() {
        return _t("Do you want to import this information into the employee profile?");
    }

    get labelYesImport() {
        return _t("Yes, import");
    }

    get labelNoImport() {
        return _t("No");
    }

    get labelRetryParse() {
        return _t("Try to read fields again");
    }

    get labelRawQrToggle() {
        return _t("Show raw QR text");
    }

    /**
     * After a successful decode: load parsed fields in-dialog (no popup).
     * @param {string} rawText
     */
    async _onQrDecodeSuccess(rawText) {
        this.state.error = null;
        this.state.qrText = rawText;
        this.state.parsedImport = null;
        this._stopAutoScan();
        await this._prepareImportPreview(rawText);
    }

    async _prepareImportPreview(qrText) {
        const result = await this.orm.call("hr.employee", "parse_cccd_qr_payload", [], {
            qr_text: qrText,
        });
        if (!result || !result.ok) {
            const err = (result && result.error) || _t("Could not parse QR data.");
            this.state.error = err;
            this.notification.add(err, { type: "danger" });
            return;
        }
        this.state.error = null;
        this.state.parsedImport = {
            previewRows: result.preview_rows || [],
            values: result.values,
        };
    }

    onConfirmImport() {
        const imp = this.state.parsedImport;
        if (!imp?.values) {
            return;
        }
        this.env.bus.trigger(CCCD_IMPORT_BUS, { values: imp.values });
        this.notification.add(_t("Information has been filled in the employee form."), {
            type: "success",
        });
        this.props.close();
    }

    onDeclineImport() {
        this.state.parsedImport = null;
    }

    async onRetryParseFromPayload() {
        if (this.state.qrText) {
            await this._prepareImportPreview(this.state.qrText);
        }
    }

    get labelOpenWebcam() {
        return _t("Open webcam");
    }

    get labelChooseImage() {
        return _t("Choose image");
    }

    _cleanup() {
        this._stopAutoScan();
        if (this.stream) {
            for (const track of this.stream.getTracks()) {
                track.stop();
            }
            this.stream = null;
        }
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
            this.state.previewUrl = null;
        }
    }

    onPickFromCamera() {
        this.state.error = null;
        this.state.qrText = null;
        this.state.parsedImport = null;
        this.fileInputRef.el?.click();
    }

    onFileChange(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        this.state.parsedImport = null;
        if (this.stream) {
            for (const track of this.stream.getTracks()) {
                track.stop();
            }
            this.stream = null;
        }
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
        }
        this.state.previewUrl = URL.createObjectURL(file);
        this.state.mode = "preview";
        this.state.qrText = null;
        // Phones: decode can lag; retry a few times so QR scan works without extra taps.
        this._schedulePreviewScanRetries();
    }

    /**
     * Run QR detection on the preview a few times (mobile gallery/camera often needs a beat).
     */
    _schedulePreviewScanRetries() {
        void this._runPreviewScanRetries();
    }

    async _runPreviewScanRetries() {
        for (let i = 0; i < 3; i++) {
            if (this.state.mode !== "preview" || !this.state.previewUrl || this.state.qrText) {
                return;
            }
            await this.scanQrFromPreview({ silentOnFail: i < 2 });
            if (this.state.qrText) {
                return;
            }
            if (i < 2) {
                await delay(450);
            }
        }
    }

    async startLiveCamera() {
        this.state.error = null;
        this.state.parsedImport = null;
        if (!window.isSecureContext) {
            if (this.isMobileDevice) {
                const msg = _t(
                    "This phone connection is HTTP, so live webcam is blocked. Opening camera picker instead."
                );
                this.notification.add(msg, { type: "warning" });
                this.onPickFromCamera();
                return;
            }
            const msg = _t(
                "Camera needs a secure connection (HTTPS) or localhost. Open Odoo via HTTPS or use “Choose image”."
            );
            this.state.error = msg;
            this.notification.add(msg, { type: "warning" });
            return;
        }
        if (!navigator.mediaDevices?.getUserMedia) {
            const msg = _t(
                "Live camera is not available in this browser. Use “Choose image” to pick a file."
            );
            this.state.error = msg;
            this.notification.add(msg, { type: "warning" });
            if (this.isMobileDevice) {
                this.onPickFromCamera();
            }
            return;
        }
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
            this.state.previewUrl = null;
        }
        if (this.stream) {
            for (const track of this.stream.getTracks()) {
                track.stop();
            }
            this.stream = null;
        }
        try {
            this._lastSilentLiveServerMs = 0;
            this.stream = await getBestCameraStream(this.isMobileDevice);
            this.state.mode = "live";
        } catch (err) {
            const name = err && err.name;
            let msg;
            if (name === "NotAllowedError" || name === "PermissionDeniedError") {
                msg = _t(
                    "Camera access was blocked. Allow the camera in the browser address bar (site settings), then try again."
                );
            } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
                msg = _t("No camera was found. Connect a webcam or use “Choose image”.");
            } else if (name === "NotReadableError" || name === "TrackStartError") {
                msg = _t(
                    "The camera is already in use by another app. Close it or use “Choose image”."
                );
            } else {
                msg = _t(
                    "Could not start the camera. Check permissions, or use “Choose image” to upload a photo."
                );
            }
            this.state.error = msg;
            this.notification.add(msg, { type: "danger" });
        }
    }

    captureLiveFrame() {
        const video = this.videoRef.el;
        if (!video || video.readyState < 2) {
            return;
        }
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return;
        }
        ctx.drawImage(video, 0, 0);
        canvas.toBlob(
            (blob) => {
                if (!blob) {
                    return;
                }
                if (this.stream) {
                    for (const track of this.stream.getTracks()) {
                        track.stop();
                    }
                    this.stream = null;
                }
                if (this.state.previewUrl) {
                    URL.revokeObjectURL(this.state.previewUrl);
                }
                this.state.previewUrl = URL.createObjectURL(blob);
                this.state.mode = "preview";
                this.state.qrText = null;
                this.state.parsedImport = null;
                this._stopAutoScan();
                this.scanQrFromPreview({ silentOnFail: true });
            },
            "image/jpeg",
            0.92
        );
    }

    async _detectQrFromSource(
        source,
        {
            silentOnFail = false,
            allowServer = true,
            zxingQuick = false,
            liveContinuous = false,
            silentLiveServerThrottled = false,
        } = {}
    ) {
        // 1) Native BarcodeDetector (fast when it works; weak on small / noisy CCCD QR).
        if (hasBarcodeDetector()) {
            try {
                const detector = new window.BarcodeDetector({ formats: ["qr_code"] });
                const roiCanvas = this._makeRoiCanvas(source);
                const roiCodes = roiCanvas ? await detector.detect(roiCanvas) : [];
                const codes = roiCodes.length ? roiCodes : await detector.detect(source);
                const qr = (codes || []).find((c) => c.rawValue);
                if (qr) {
                    await this._onQrDecodeSuccess(qr.rawValue);
                    return;
                }
            } catch {
                // Fall through to ZXing-js then server.
            }
        }

        // 2) ZXing-js in-browser (same bundle as Odoo core; stronger decoder than BarcodeDetector alone).
        const zxingText = await this._tryZxingDecode(source, {
            quick: zxingQuick,
            liveContinuous,
        });
        if (zxingText) {
            await this._onQrDecodeSuccess(zxingText);
            return;
        }

        // 3) Server: full RPC when user explicitly scans; on mobile live auto use silent + throttle (no loading bar spam).
        if (allowServer) {
            await this._detectQrViaServer(source, { silentOnFail });
        } else if (silentLiveServerThrottled) {
            await this._detectQrViaServerSilentThrottled(source);
        }
    }

    _getSourceSize(source) {
        const width = source.videoWidth || source.naturalWidth || source.width;
        const height = source.videoHeight || source.naturalHeight || source.height;
        return { width, height };
    }

    _makeRoiCanvas(source) {
        const { width, height } = this._getSourceSize(source);
        if (!width || !height) {
            return null;
        }
        const sx = Math.max(0, Math.floor(width * LIVE_ROI.x));
        const sy = Math.max(0, Math.floor(height * LIVE_ROI.y));
        const sw = Math.max(1, Math.floor(width * LIVE_ROI.w));
        const sh = Math.max(1, Math.floor(height * LIVE_ROI.h));
        const canvas = document.createElement("canvas");
        canvas.width = sw;
        canvas.height = sh;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return null;
        }
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, sw, sh);
        return canvas;
    }

    /**
     * Full-frame canvas from a video or image element (for ZXing / server pipelines).
     * @returns {HTMLCanvasElement | null}
     */
    _sourceToFullCanvas(source) {
        const { width, height } = this._getSourceSize(source);
        if (!width || !height) {
            return null;
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return null;
        }
        ctx.drawImage(source, 0, 0, width, height);
        return canvas;
    }

    /**
     * Decode QR with ZXing-js on ROI then full frame, with upscales (CCCD QR is small).
     * @param {object} opts
     * @param {boolean} [opts.quick] Live webcam auto-scan: fewer passes so we finish before the next tick.
     * @param {boolean} [opts.liveContinuous] Phone live preview: a bit more resolution / scales for small QR.
     * @returns {Promise<string | null>}
     */
    async _tryZxingDecode(source, { quick = false, liveContinuous = false } = {}) {
        try {
            await ensureZXingLibraryLoaded();
        } catch {
            return null;
        }
        const canvases = [];
        const roi = this._makeRoiCanvas(source);
        const full = this._sourceToFullCanvas(source);
        if (quick) {
            const fullClamp = liveContinuous ? 1280 : 960;
            const scales = liveContinuous ? [1, 1.5, 2] : [1, 2];
            if (roi) {
                canvases.push(roi);
            }
            if (full) {
                canvases.push(clampCanvasMaxSide(full, fullClamp));
            }
            for (const base of canvases) {
                for (const scale of scales) {
                    const canvas = scale === 1 ? base : scaleCanvasUp(base, scale);
                    const capped = clampCanvasMaxSide(canvas, 2048);
                    const text = decodeQrFromCanvasWithZXing(capped);
                    if (text) {
                        return text;
                    }
                }
            }
            return null;
        }
        if (roi) {
            canvases.push(roi);
        }
        if (full) {
            canvases.push(full);
        }
        const scales = [1, 1.25, 1.5, 2];
        for (const base of canvases) {
            for (const scale of scales) {
                const canvas = scale === 1 ? base : scaleCanvasUp(base, scale);
                const capped = clampCanvasMaxSide(canvas, 2048);
                const text = decodeQrFromCanvasWithZXing(capped);
                if (text) {
                    return text;
                }
            }
        }
        return null;
    }

    async _toBase64Jpeg(source, { roiOnly = false } = {}) {
        const canvas = document.createElement("canvas");
        const { width, height } = this._getSourceSize(source);
        if (!width || !height) {
            return null;
        }
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return null;
        }
        if (roiOnly && this.state.mode === "live") {
            const sx = Math.max(0, Math.floor(width * LIVE_ROI.x));
            const sy = Math.max(0, Math.floor(height * LIVE_ROI.y));
            const sw = Math.max(1, Math.floor(width * LIVE_ROI.w));
            const sh = Math.max(1, Math.floor(height * LIVE_ROI.h));
            canvas.width = sw;
            canvas.height = sh;
            ctx.drawImage(source, sx, sy, sw, sh, 0, 0, sw, sh);
        } else {
            canvas.width = width;
            canvas.height = height;
            ctx.drawImage(source, 0, 0, width, height);
        }
        const exportCanvas = clampCanvasMaxSide(canvas, 2600);
        const dataUrl = exportCanvas.toDataURL("image/jpeg", 0.92);
        const parts = dataUrl.split(",");
        return parts.length > 1 ? parts[1] : null;
    }

    async _detectQrViaServer(source, { silentOnFail = false } = {}) {
        const roiFirst = await this._toBase64Jpeg(source, { roiOnly: true });
        const fullImage = await this._toBase64Jpeg(source, { roiOnly: false });
        if (!roiFirst && !fullImage) {
            const msg = _t("Could not prepare image for server QR decoding.");
            if (!silentOnFail) {
                this.state.error = msg;
            }
            if (!silentOnFail) {
                this.notification.add(msg, { type: "danger" });
            }
            return;
        }
        try {
            let result = null;
            if (roiFirst) {
                result = await this.orm.call("hr.employee", "action_decode_cccd_qr", [], {
                    image_base64: roiFirst,
                });
            }
            if ((!result || !result.ok) && fullImage) {
                result = await this.orm.call("hr.employee", "action_decode_cccd_qr", [], {
                    image_base64: fullImage,
                });
            }
            if (result && result.ok && result.text) {
                await this._onQrDecodeSuccess(result.text);
                return;
            }
            const msg = (result && result.error) || _t("No QR code found.");
            if (!silentOnFail) {
                this.state.error = msg;
            }
            this.state.qrText = null;
            if (!silentOnFail) {
                this.notification.add(msg, { type: "warning" });
            }
        } catch {
            const msg = _t("Server QR decoding failed.");
            this.state.error = msg;
            this.state.qrText = null;
            if (!silentOnFail) {
                this.notification.add(msg, { type: "danger" });
            }
        }
    }

    /**
     * Mobile live preview: occasional server decode without global loading (orm.silent), throttled.
     */
    async _detectQrViaServerSilentThrottled(source) {
        const now = Date.now();
        if (now - this._lastSilentLiveServerMs < 2800) {
            return;
        }
        this._lastSilentLiveServerMs = now;
        const roiFirst = await this._toBase64Jpeg(source, { roiOnly: true });
        const fullImage = await this._toBase64Jpeg(source, { roiOnly: false });
        if (!roiFirst && !fullImage) {
            return;
        }
        try {
            let result = null;
            if (roiFirst) {
                result = await this.orm.silent.call("hr.employee", "action_decode_cccd_qr", [], {
                    image_base64: roiFirst,
                });
            }
            if ((!result || !result.ok) && fullImage) {
                result = await this.orm.silent.call("hr.employee", "action_decode_cccd_qr", [], {
                    image_base64: fullImage,
                });
            }
            if (result && result.ok && result.text) {
                await this._onQrDecodeSuccess(result.text);
            }
        } catch {
            // ignore — next throttle window may succeed
        }
    }

    async scanQrFromLive({ silentOnFail = false } = {}) {
        const video = this.videoRef.el;
        if (!video || video.readyState < 2 || this.scanInProgress) {
            return;
        }
        this.scanInProgress = true;
        try {
            const allowServer = !silentOnFail;
            const zxingQuick = silentOnFail;
            const liveContinuous = silentOnFail && this.isMobileDevice;
            const silentLiveServerThrottled = silentOnFail && this.isMobileDevice;
            await this._detectQrFromSource(video, {
                silentOnFail,
                allowServer,
                zxingQuick,
                liveContinuous,
                silentLiveServerThrottled,
            });
        } finally {
            this.scanInProgress = false;
        }
    }

    async scanQrFromPreview({ silentOnFail = false } = {}) {
        if (!this.state.previewUrl || this.scanInProgress) {
            return;
        }
        this.scanInProgress = true;
        const img = new Image();
        img.src = this.state.previewUrl;
        try {
            await new Promise((resolve) => {
                img.onload = resolve;
                img.onerror = resolve;
            });
            if (img.decode) {
                try {
                    await img.decode();
                } catch {
                    // ignore; continue with natural dimensions
                }
            }
            if (!img.naturalWidth || !img.naturalHeight) {
                const msg = _t("Could not load the preview image for QR detection.");
                this.state.error = msg;
                if (!silentOnFail) {
                    this.notification.add(msg, { type: "danger" });
                }
                return;
            }
            await this._detectQrFromSource(img, { silentOnFail });
        } finally {
            this.scanInProgress = false;
        }
    }

    _startAutoScan() {
        this._stopAutoScan();
        this._lastLiveDecodeWallMs = 0;
        const video = this.videoRef.el;
        if (
            video &&
            typeof video.requestVideoFrameCallback === "function" &&
            typeof video.cancelVideoFrameCallback === "function"
        ) {
            this._scheduleNextVideoFrameScan();
            return;
        }
        const intervalMs = this.isMobileDevice ? 320 : 720;
        this.autoScanTimer = setInterval(() => {
            if (this.state.mode !== "live" || this.state.qrText) {
                return;
            }
            this.scanQrFromLive({ silentOnFail: true });
        }, intervalMs);
    }

    _scheduleNextVideoFrameScan() {
        const video = this.videoRef.el;
        if (!video || this.state.mode !== "live" || this.state.qrText) {
            return;
        }
        if (typeof video.requestVideoFrameCallback !== "function") {
            return;
        }
        this._videoFrameCallbackHandle = video.requestVideoFrameCallback(() => {
            this._videoFrameCallbackHandle = null;
            if (this.state.mode !== "live" || this.state.qrText) {
                return;
            }
            const wall = performance.now();
            const minGap = this.isMobileDevice ? 160 : 280;
            if (wall - this._lastLiveDecodeWallMs < minGap || this.scanInProgress) {
                this._scheduleNextVideoFrameScan();
                return;
            }
            this._lastLiveDecodeWallMs = wall;
            void this.scanQrFromLive({ silentOnFail: true }).finally(() => {
                if (this.state.mode === "live" && !this.state.qrText) {
                    this._scheduleNextVideoFrameScan();
                }
            });
        });
    }

    _stopAutoScan() {
        if (this.autoScanTimer) {
            clearInterval(this.autoScanTimer);
            this.autoScanTimer = null;
        }
        const video = this.videoRef.el;
        if (
            video &&
            this._videoFrameCallbackHandle != null &&
            typeof video.cancelVideoFrameCallback === "function"
        ) {
            video.cancelVideoFrameCallback(this._videoFrameCallbackHandle);
        }
        this._videoFrameCallbackHandle = null;
    }

    retake() {
        if (this.state.previewUrl) {
            URL.revokeObjectURL(this.state.previewUrl);
            this.state.previewUrl = null;
        }
        this.state.mode = "choose";
        this.state.error = null;
        this.state.qrText = null;
        this.state.parsedImport = null;
        this._stopAutoScan();
    }

    onClose() {
        this._cleanup();
        this.props.close();
    }

}

function openIdCardCameraAction(env, action) {
    const params = action.params || {};
    env.services.dialog.add(IdCardCameraDialog, {
        employeeId: params.employee_id,
    });
}

registry.category("actions").add("hr_employee_open_id_camera", openIdCardCameraAction);
