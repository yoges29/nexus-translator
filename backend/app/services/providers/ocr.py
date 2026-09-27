import asyncio
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from app.core.config import get_settings
from app.core.errors import AppError, ProviderError

logger = logging.getLogger("nexus.translator.ocr")


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class OCRRegion:
    text: str
    bounding_box: BoundingBox
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
        }


@dataclass
class OCRResult:
    text: str
    language: str | None = None
    regions: list[OCRRegion] = field(default_factory=list)


class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    async def extract_regions(self, image_bytes: bytes) -> list[OCRRegion]:
        raise NotImplementedError

    @abstractmethod
    async def process_image(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError


def _load_image_safely(image_bytes: bytes) -> Image.Image:
    if not image_bytes:
        raise AppError("Image payload is empty.")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        # Decompression bomb check & reasonable dimensions check
        if image.width > 8000 or image.height > 8000:
            raise AppError("Image dimensions exceed the maximum allowed limit of 8000x8000 pixels.")
        return image
    except AppError:
        raise
    except Exception as exc:
        raise AppError("Invalid or corrupted image format.") from exc


class RapidOCRProvider(OCRProvider):
    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR

                self._engine = RapidOCR()
            except Exception as exc:
                logger.error("Failed to initialize RapidOCR: %s", exc)
                raise ProviderError("OCR engine failed to initialize.") from exc
        return self._engine

    def _sync_process(self, image_bytes: bytes) -> OCRResult:
        image = _load_image_safely(image_bytes)
        # Convert RGBA/Palette/Grayscale to RGB for OCR processing
        if image.mode != "RGB":
            image = image.convert("RGB")

        import numpy as np

        img_np = np.array(image)
        engine = self._get_engine()
        result, elapse_list = engine(img_np)

        if not result:
            return OCRResult(text="", language=None, regions=[])

        regions: list[OCRRegion] = []
        lines: list[str] = []

        for item in result:
            # item structure: [box_points, text, score]
            # box_points: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            box_points = item[0]
            text = str(item[1]).strip()
            score = float(item[2]) if len(item) > 2 and item[2] is not None else None

            if not text:
                continue

            lines.append(text)

            xs = [pt[0] for pt in box_points]
            ys = [pt[1] for pt in box_points]
            min_x, max_x = int(min(xs)), int(max(xs))
            min_y, max_y = int(min(ys)), int(max(ys))

            box = BoundingBox(
                x=max(0, min_x),
                y=max(0, min_y),
                width=max(1, max_x - min_x),
                height=max(1, max_y - min_y),
            )
            regions.append(
                OCRRegion(
                    text=text,
                    bounding_box=box,
                    confidence=round(score, 4) if score is not None else None,
                )
            )

        full_text = "\n".join(lines).strip()
        return OCRResult(text=full_text, language=None, regions=regions)

    async def extract_text(self, image_bytes: bytes) -> str:
        res = await self.process_image(image_bytes)
        return res.text

    async def extract_regions(self, image_bytes: bytes) -> list[OCRRegion]:
        res = await self.process_image(image_bytes)
        return res.regions

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return await asyncio.to_thread(self._sync_process, image_bytes)


class TesseractOCRProvider(OCRProvider):
    def __init__(self, tesseract_cmd: str = "") -> None:
        self.tesseract_cmd = tesseract_cmd
        if self.tesseract_cmd:
            try:
                import pytesseract

                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            except Exception as exc:
                logger.warning("Failed setting tesseract_cmd: %s", exc)

    def _sync_process(self, image_bytes: bytes) -> OCRResult:
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise ProviderError("pytesseract is not installed.") from exc

        image = _load_image_safely(image_bytes)
        if image.mode != "RGB":
            image = image.convert("RGB")

        try:
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
        except Exception as exc:
            logger.error("Tesseract execution failed: %s", exc)
            raise ProviderError("Tesseract OCR processing failed.") from exc

        regions: list[OCRRegion] = []
        lines: list[str] = []
        n_boxes = len(data.get("text", []))

        for i in range(n_boxes):
            word = str(data["text"][i]).strip()
            conf_val = data.get("conf", ["-1"])[i]
            try:
                conf = float(conf_val)
            except (ValueError, TypeError):
                conf = -1.0

            if word and conf > 0:
                lines.append(word)
                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])
                regions.append(
                    OCRRegion(
                        text=word,
                        bounding_box=BoundingBox(x=x, y=y, width=w, height=h),
                        confidence=round(conf / 100.0, 4),
                    )
                )

        full_text = "\n".join(lines).strip()
        return OCRResult(text=full_text, language=None, regions=regions)

    async def extract_text(self, image_bytes: bytes) -> str:
        res = await self.process_image(image_bytes)
        return res.text

    async def extract_regions(self, image_bytes: bytes) -> list[OCRRegion]:
        res = await self.process_image(image_bytes)
        return res.regions

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return await asyncio.to_thread(self._sync_process, image_bytes)


class CloudVisionOCRProvider(OCRProvider):
    """Google Cloud Vision API provider abstraction."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or get_settings().cloud_vision_api_key

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        if not self.api_key:
            # Fall back to RapidOCR if no cloud key configured
            logger.info("Cloud vision API key not set; using local RapidOCR fallback.")
            return await RapidOCRProvider().process_image(image_bytes)

        import base64
        import httpx

        _load_image_safely(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        payload = {
            "requests": [
                {
                    "image": {"content": b64},
                    "features": [{"type": "TEXT_DETECTION"}],
                }
            ]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise ProviderError(f"Cloud Vision error: {response.text}")
                data = response.json()
            except Exception as exc:
                raise ProviderError("Cloud Vision OCR request failed.") from exc

        responses = data.get("responses", [{}])[0]
        text_annotations = responses.get("textAnnotations", [])
        if not text_annotations:
            return OCRResult(text="", language=None, regions=[])

        full_text = text_annotations[0].get("description", "").strip()
        detected_lang = (
            text_annotations[0].get("locale")
            if "locale" in text_annotations[0]
            else None
        )

        regions: list[OCRRegion] = []
        for ann in text_annotations[1:]:
            desc = ann.get("description", "").strip()
            vertices = ann.get("boundingPoly", {}).get("vertices", [])
            if vertices and desc:
                xs = [v.get("x", 0) for v in vertices]
                ys = [v.get("y", 0) for v in vertices]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                regions.append(
                    OCRRegion(
                        text=desc,
                        bounding_box=BoundingBox(
                            x=min_x,
                            y=min_y,
                            width=max(1, max_x - min_x),
                            height=max(1, max_y - min_y),
                        ),
                        confidence=None,
                    )
                )

        return OCRResult(text=full_text, language=detected_lang, regions=regions)

    async def extract_text(self, image_bytes: bytes) -> str:
        res = await self.process_image(image_bytes)
        return res.text

    async def extract_regions(self, image_bytes: bytes) -> list[OCRRegion]:
        res = await self.process_image(image_bytes)
        return res.regions


class MockOCRProvider(OCRProvider):
    """Deterministic mock provider for unit tests."""

    def __init__(self, text: str = "Hello", language: str = "en") -> None:
        self._text = text
        self._language = language

    async def extract_text(self, image_bytes: bytes) -> str:
        return self._text

    async def extract_regions(self, image_bytes: bytes) -> list[OCRRegion]:
        return [
            OCRRegion(
                text=self._text,
                bounding_box=BoundingBox(x=10, y=10, width=100, height=30),
                confidence=0.99,
            )
        ]

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(
            text=self._text,
            language=self._language,
            regions=await self.extract_regions(image_bytes),
        )
