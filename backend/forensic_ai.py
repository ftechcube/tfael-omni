#!/usr/bin/env python3
"""
TFAEL-OMNI v2.0 — Mesin AI Forensik NYATA (Pilar 6): YARA, OCR, Whisper, YOLO.

Prinsip kejujuran: setiap mesin NYATA bila pustaka/model-nya terpasang, dan melaporkan
`available: false` + alasan bila tidak — TIDAK pernah memalsukan hasil. Pustaka berat
(Whisper, YOLO) dimuat malas (lazy) dan di-cache agar hanya diunduh/diinisialisasi sekali.
"""

import io
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List

_RULES_PATH = os.path.join(os.path.dirname(__file__), "yara_rules", "tfael.yar")

# ---- YARA (yara-python) ----
_yara_compiled = None
_yara_error = None
try:
    import yara as _yara  # type: ignore
    _yara_compiled = _yara.compile(filepath=_RULES_PATH)
except Exception as _e:  # pustaka tak ada / rules gagal kompilasi
    _yara_error = str(_e)


def scan_yara(raw_bytes: bytes) -> Dict[str, Any]:
    """Pindai byte artefak dengan mesin YARA sungguhan terhadap ruleset tfael.yar."""
    if _yara_compiled is None:
        return {"engine": "yara-python", "available": False,
                "reason": f"yara-python/rules tak tersedia: {_yara_error}", "matches": []}
    try:
        matches = []
        for m in _yara_compiled.match(data=raw_bytes, timeout=10):
            try:
                ids = sorted({s.identifier for s in m.strings})
            except Exception:
                ids = []
            matches.append({
                "rule": m.rule,
                "severity": (m.meta or {}).get("severity", "INFO"),
                "desc": (m.meta or {}).get("desc", ""),
                "matched_strings": ids[:6],
                "engine": "yara",
            })
        return {"engine": "yara-python", "available": True, "matches": matches}
    except Exception as e:
        return {"engine": "yara-python", "available": True, "error": str(e), "matches": []}


def yara_status() -> Dict[str, Any]:
    return {"available": _yara_compiled is not None, "reason": _yara_error, "rules_path": _RULES_PATH}


# ---- OCR (pytesseract + Pillow; butuh binary tesseract) ----
def run_ocr(raw_bytes: bytes) -> Dict[str, Any]:
    """OCR NYATA dari gambar. Butuh pytesseract+Pillow dan binary `tesseract`."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:
        return {"engine": "tesseract", "available": False, "reason": f"pytesseract/Pillow tak terpasang: {e}", "text": ""}
    if shutil.which("tesseract") is None:
        return {"engine": "tesseract", "available": False,
                "reason": "binary 'tesseract' tak terpasang (jalankan: brew install tesseract tesseract-lang)", "text": ""}
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        text = pytesseract.image_to_string(img, lang=os.environ.get("OMNI_OCR_LANG", "eng"))
        return {"engine": "tesseract", "available": True, "text": text.strip(),
                "char_count": len(text.strip())}
    except Exception as e:
        return {"engine": "tesseract", "available": True, "error": str(e), "text": ""}


# ---- Whisper (faster-whisper; lazy, model di-cache) ----
_whisper_model = None
_whisper_error = None


def _get_whisper():
    global _whisper_model, _whisper_error
    if _whisper_model is not None or _whisper_error is not None:
        return _whisper_model
    try:
        from faster_whisper import WhisperModel  # type: ignore
        size = os.environ.get("OMNI_WHISPER_MODEL", "tiny")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    except Exception as e:
        _whisper_error = str(e)
    return _whisper_model


def transcribe_audio(raw_bytes: bytes, file_name: str = "audio.bin") -> Dict[str, Any]:
    """Transkripsi NYATA audio (offline) via faster-whisper bila terpasang."""
    try:
        import faster_whisper  # noqa: F401  # type: ignore
    except Exception as e:
        return {"engine": "faster-whisper", "available": False,
                "reason": f"faster-whisper tak terpasang (pip install faster-whisper): {e}", "text": ""}
    model = _get_whisper()
    if model is None:
        return {"engine": "faster-whisper", "available": False,
                "reason": f"Model gagal dimuat: {_whisper_error}", "text": ""}
    tmp = None
    try:
        suffix = os.path.splitext(file_name)[1] or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(raw_bytes)
            tmp = f.name
        segments, info = model.transcribe(tmp, beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {"engine": "faster-whisper", "available": True, "text": text,
                "language": getattr(info, "language", ""), "model": os.environ.get("OMNI_WHISPER_MODEL", "tiny")}
    except Exception as e:
        return {"engine": "faster-whisper", "available": True, "error": str(e), "text": ""}
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ---- YOLO (ultralytics; lazy, model di-cache) ----
_yolo_model = None
_yolo_error = None


def _get_yolo():
    global _yolo_model, _yolo_error
    if _yolo_model is not None or _yolo_error is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO  # type: ignore
        weights = os.environ.get("OMNI_YOLO_WEIGHTS", "yolov8m.pt")
        _yolo_model = YOLO(weights)
    except Exception as e:
        _yolo_error = str(e)
    return _yolo_model


def detect_objects(image_bytes: bytes, conf: float = 0.35) -> Dict[str, Any]:
    """Deteksi objek NYATA via YOLOv8 (ultralytics) bila terpasang."""
    try:
        import ultralytics  # noqa: F401  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:
        return {"engine": "yolov8", "available": False,
                "reason": f"ultralytics/Pillow tak terpasang (pip install ultralytics): {e}", "detections": []}
    model = _get_yolo()
    if model is None:
        return {"engine": "yolov8", "available": False, "reason": f"Model gagal dimuat: {_yolo_error}", "detections": []}
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        res = model.predict(img, conf=conf, verbose=False)
        dets: List[Dict[str, Any]] = []
        for r in res:
            names = r.names
            for b in r.boxes:
                cls = int(b.cls[0])
                xyxy = [round(float(v), 1) for v in b.xyxy[0].tolist()]
                dets.append({"label": names.get(cls, str(cls)), "confidence": round(float(b.conf[0]), 3), "bbox": xyxy})
        return {"engine": "yolov8", "available": True, "detections": dets, "count": len(dets)}
    except Exception as e:
        return {"engine": "yolov8", "available": True, "error": str(e), "detections": []}


def ocr_plate_text(image_bytes: bytes) -> Dict[str, Any]:
    """
    Baca teks pelat dari potongan gambar (crop kendaraan) via Tesseract dengan
    preprocessing khusus pelat: grayscale, perbesar, kontras/threshold, whitelist A-Z0-9.
    """
    try:
        import pytesseract  # type: ignore
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:
        return {"available": False, "reason": f"pytesseract/opencv tak terpasang: {e}", "text": ""}
    if shutil.which("tesseract") is None:
        return {"available": False, "reason": "binary tesseract tak terpasang", "text": ""}
    try:
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return {"available": True, "text": ""}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # perbesar agar karakter kecil lebih terbaca
        h, w = gray.shape[:2]
        scale = max(1.0, 160.0 / max(1, h))
        if scale > 1.0:
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        cfg = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        text = pytesseract.image_to_string(th, config=cfg)
        return {"available": True, "text": re.sub(r"[^A-Z0-9 ]", "", text.upper()).strip()}
    except Exception as e:
        return {"available": True, "error": str(e), "text": ""}


def grab_stream_frame(url: str, max_read: int = 25, open_timeout_ms: int = 12000) -> Dict[str, Any]:
    """
    Ambil SATU frame terbaru dari stream video (HLS .m3u8 / RTSP / MP4) via OpenCV+ffmpeg.
    Dipakai untuk menjalankan YOLO pada CCTV publik (data pemerintah terbuka).
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"OpenCV tak terpasang: {e}"}
    # Timeout ffmpeg agar tak menggantung bila stream mati
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        f"rw_timeout;{open_timeout_ms * 1000}|timeout;{open_timeout_ms * 1000}",
    )
    cap = None
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return {"ok": False, "error": "Gagal membuka stream (URL kedaluwarsa / tak terjangkau)."}
        frame = None
        for _ in range(max_read):
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
        if frame is None:
            return {"ok": False, "error": "Stream terbuka tetapi tak ada frame terbaca."}
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return {"ok": False, "error": "Gagal meng-encode frame."}
        h, w = frame.shape[:2]
        return {"ok": True, "jpeg": buf.tobytes(), "width": w, "height": h}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if cap is not None:
            cap.release()


def engines_status() -> Dict[str, Any]:
    """Status ketersediaan semua mesin AI forensik (untuk dashboard capabilities)."""
    def _importable(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:
            return False
    return {
        "yara": _yara_compiled is not None,
        "ocr_tesseract": _importable("pytesseract") and shutil.which("tesseract") is not None,
        "whisper": _importable("faster_whisper"),
        "yolo": _importable("ultralytics"),
    }
