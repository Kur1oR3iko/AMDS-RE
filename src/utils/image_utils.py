"""Image encoding helpers for model requests and chat previews."""

import base64
import io
from pathlib import Path


MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def encode_image_data_url(image_path: str, max_side: int = 1280, jpeg_quality: int = 85) -> tuple[str, str]:
    """
    Encode an image as base64 data for OpenAI-compatible vision messages.
    Large images are downscaled when Pillow is available to reduce request size.
    """
    path = Path(image_path)
    mime_type = MIME_TYPES.get(path.suffix.lower(), "image/png")

    try:
        from PIL import Image

        with Image.open(path) as image:
            if getattr(image, "is_animated", False):
                return _encode_raw(path, mime_type)

            image.thumbnail((max_side, max_side))
            if image.mode == "P" and "transparency" in image.info:
                image = image.convert("RGBA")
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            output = io.BytesIO()
            if image.mode == "RGBA":
                image.save(output, format="PNG", optimize=True)
                mime_type = "image/png"
            else:
                image.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
                mime_type = "image/jpeg"

            encoded = base64.b64encode(output.getvalue()).decode()
            return encoded, mime_type
    except Exception as e:
        print(f"[图片] 压缩编码失败，使用原始图片: {e}")
        return _encode_raw(path, mime_type)


def to_data_url(image_path: str, max_side: int = 1280, jpeg_quality: int = 85) -> str:
    encoded, mime_type = encode_image_data_url(image_path, max_side, jpeg_quality)
    return f"data:{mime_type};base64,{encoded}"


def _encode_raw(path: Path, mime_type: str) -> tuple[str, str]:
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode()
    return encoded, mime_type
