"""Συνθετικές εικόνες για τα tests της φωτογραφίας (δημιουργούνται στη RAM, ποτέ σε δίσκο)."""
import io

from PIL import Image


def jpeg(width=400, height=300, color=(180, 120, 60), quality=85) -> bytes:
    img = Image.new("RGB", (width, height), color)
    for x in range(0, width, 40):                 # λίγη υφή, όχι μονόχρωμο
        img.paste((60, 160, 60), (x, 0, min(x + 20, width), height // 2))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def dark_jpeg() -> bytes:
    """Σχεδόν μαύρη: το demo food gate (μέση φωτεινότητα < 10) την απορρίπτει."""
    return _solid((0, 0, 0))


def _solid(color, size=(320, 240)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="JPEG")
    return out.getvalue()


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (100, 100), (200, 100, 50)).save(out, format="PNG")
    return out.getvalue()


def bomb_jpeg() -> bytes:
    """Μικρό έγκυρο JPEG του οποίου η κεφαλίδα (SOF0) δηλώνει 60000 x 60000: decompression bomb."""
    data = bytearray(_solid((120, 120, 120), (16, 16)))
    sof = data.index(b"\xff\xc0")
    data[sof + 5:sof + 9] = (60000).to_bytes(2, "big") * 2
    return bytes(data)
