from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont


class LogoDesignError(ValueError):
    """Raised when a logo design contains invalid dimensions or colours."""


@dataclass(frozen=True, slots=True)
class LogoDesign:
    text: str
    width: int = 1200
    height: int = 360
    font_size: int = 120
    foreground: str = "#0f172a"
    background: str = "#ffffff"
    transparent_background: bool = False
    border_width: int = 0
    border_color: str = "#0f172a"
    padding: int = 24


class LogoService:
    """Create a simple reusable raster logo without external font assets."""

    MAX_PIXELS = 50_000_000

    def render(self, design: LogoDesign) -> Image.Image:
        self._validate(design)
        foreground = ImageColor.getcolor(design.foreground, "RGBA")
        background = (
            (255, 255, 255, 0)
            if design.transparent_background
            else ImageColor.getcolor(design.background, "RGBA")
        )
        border = ImageColor.getcolor(design.border_color, "RGBA")
        image = Image.new("RGBA", (design.width, design.height), background)
        painter = ImageDraw.Draw(image)
        if design.border_width:
            inset = design.border_width // 2
            painter.rectangle(
                (inset, inset, design.width - 1 - inset, design.height - 1 - inset),
                outline=border,
                width=design.border_width,
            )

        font = self._font(design.font_size)
        text = design.text.strip()
        if text:
            box = painter.multiline_textbbox((0, 0), text, font=font, align="center", spacing=4)
            text_width = box[2] - box[0]
            text_height = box[3] - box[1]
            available_width = max(1, design.width - 2 * design.padding)
            available_height = max(1, design.height - 2 * design.padding)
            if text_width > available_width or text_height > available_height:
                font = self._fit_font(text, design, painter)
                box = painter.multiline_textbbox((0, 0), text, font=font, align="center", spacing=4)
                text_width = box[2] - box[0]
                text_height = box[3] - box[1]
            position = (
                (design.width - text_width) / 2 - box[0],
                (design.height - text_height) / 2 - box[1],
            )
            painter.multiline_text(
                position,
                text,
                fill=foreground,
                font=font,
                align="center",
                spacing=4,
            )
        return image

    def save(self, design: LogoDesign, target: Path) -> Path:
        destination = Path(target).resolve()
        if destination.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            destination = destination.with_suffix(".png")
        destination.parent.mkdir(parents=True, exist_ok=True)
        image = self.render(design)
        suffix = destination.suffix.casefold()
        image_format = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".bmp": "BMP",
            ".tif": "TIFF",
            ".tiff": "TIFF",
        }[suffix]
        output = image
        if image_format in {"JPEG", "BMP"}:
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            output = background
        try:
            output.save(destination, format=image_format, quality=95)
        except OSError as exc:
            raise LogoDesignError(f"Логотип не сохранён: {exc}") from exc
        return destination

    def _fit_font(self, text: str, design: LogoDesign, painter: ImageDraw.ImageDraw) -> ImageFont.ImageFont:
        available_width = max(1, design.width - 2 * design.padding)
        available_height = max(1, design.height - 2 * design.padding)
        low = 6
        high = design.font_size
        best = self._font(low)
        while low <= high:
            middle = (low + high) // 2
            candidate = self._font(middle)
            box = painter.multiline_textbbox(
                (0, 0), text, font=candidate, align="center", spacing=4
            )
            if box[2] - box[0] <= available_width and box[3] - box[1] <= available_height:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        return best

    @staticmethod
    def _font(size: int) -> ImageFont.ImageFont:
        candidates = (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
        for candidate in candidates:
            if candidate.is_file():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except OSError:
                    continue
        return ImageFont.load_default(size=size)

    def _validate(self, design: LogoDesign) -> None:
        if not 16 <= design.width <= 20_000 or not 16 <= design.height <= 20_000:
            raise LogoDesignError("Размер логотипа должен быть от 16 до 20000 пикселей")
        if design.width * design.height > self.MAX_PIXELS:
            raise LogoDesignError("Логотип содержит слишком много пикселей")
        if not 6 <= design.font_size <= 2_000:
            raise LogoDesignError("Размер шрифта должен быть от 6 до 2000")
        if not 0 <= design.border_width <= 200:
            raise LogoDesignError("Толщина рамки должна быть от 0 до 200")
        if not 0 <= design.padding <= min(design.width, design.height) // 2:
            raise LogoDesignError("Некорректный внутренний отступ")
        try:
            ImageColor.getcolor(design.foreground, "RGBA")
            ImageColor.getcolor(design.background, "RGBA")
            ImageColor.getcolor(design.border_color, "RGBA")
        except ValueError as exc:
            raise LogoDesignError("Некорректный цвет") from exc
