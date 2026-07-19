from io import BytesIO

from PIL import Image, ImageDraw

from core.visual.models import VisualDiffResult


class VisualDiffError(Exception):
    """Raised when visual diff comparison fails."""
    pass


Region = tuple[int, int, int, int]


class VisualDiffEngine:
    """Compare two screenshots and produce a highlighted diff overlay.

    The comparison works in RGB color space. Two pixels are considered different
    when the sum of absolute channel differences exceeds `threshold` (max 765).
    Changed pixels are grouped into connected regions and drawn as rectangles on
    a copy of the new image.
    """

    def __init__(
        self,
        threshold: int = 30,
        min_region_size: int = 10,
        outline_color: str = "red",
        outline_width: int = 2,
    ):
        self.threshold = threshold
        self.min_region_size = min_region_size
        self.outline_color = outline_color
        self.outline_width = outline_width

    def compare(self, old_bytes: bytes, new_bytes: bytes) -> VisualDiffResult:
        try:
            old_image = Image.open(BytesIO(old_bytes)).convert("RGB")
            new_image = Image.open(BytesIO(new_bytes)).convert("RGB")
        except Exception as exc:
            raise VisualDiffError(f"Failed to open screenshot for diff: {exc}") from exc

        width = max(old_image.width, new_image.width)
        height = max(old_image.height, new_image.height)
        old_image = self._pad_to_size(old_image, width, height)
        new_image = self._pad_to_size(new_image, width, height)

        diff_pixels = 0
        total_pixels = width * height
        changed_mask = bytearray(width * height)

        old_pixels = old_image.load()
        new_pixels = new_image.load()

        for x in range(width):
            for y in range(height):
                old_pixel = old_pixels[x, y]
                new_pixel = new_pixels[x, y]
                distance = (
                    abs(old_pixel[0] - new_pixel[0])
                    + abs(old_pixel[1] - new_pixel[1])
                    + abs(old_pixel[2] - new_pixel[2])
                )
                if distance > self.threshold:
                    diff_pixels += 1
                    changed_mask[y * width + x] = 1

        if diff_pixels == 0:
            return VisualDiffResult(changed=False, diff_score=0.0, changed_regions=0, diff_bytes=None)

        regions = self._find_regions(changed_mask, width, height)
        if not regions:
            # Changed pixels existed but were all filtered out as noise.
            return VisualDiffResult(changed=False, diff_score=0.0, changed_regions=0, diff_bytes=None)

        overlay = new_image.copy()
        draw = ImageDraw.Draw(overlay)
        for region in regions:
            draw.rectangle(region, outline=self.outline_color, width=self.outline_width)

        buffer = BytesIO()
        overlay.save(buffer, format="PNG")

        return VisualDiffResult(
            changed=True,
            diff_score=round(diff_pixels / total_pixels, 6),
            changed_regions=len(regions),
            diff_bytes=buffer.getvalue(),
        )

    def _pad_to_size(self, image: Image.Image, width: int, height: int) -> Image.Image:
        """Pad an image with white to the target size without stretching."""
        if image.width == width and image.height == height:
            return image
        padded = Image.new("RGB", (width, height), (255, 255, 255))
        padded.paste(image, (0, 0))
        return padded

    def _find_regions(self, mask: bytearray, width: int, height: int) -> list[Region]:
        """Group changed pixels into axis-aligned bounding boxes."""
        visited = bytearray(width * height)
        regions: list[Region] = []

        for x in range(width):
            for y in range(height):
                idx = y * width + x
                if not mask[idx] or visited[idx]:
                    continue
                min_x, max_x = x, x
                min_y, max_y = y, y
                stack = [(x, y)]
                visited[idx] = 1
                while stack:
                    cx, cy = stack.pop()
                    min_x, max_x = min(min_x, cx), max(max_x, cx)
                    min_y, max_y = min(min_y, cy), max(max_y, cy)
                    for nx, ny in [(cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]:
                        if 0 <= nx < width and 0 <= ny < height:
                            nidx = ny * width + nx
                            if mask[nidx] and not visited[nidx]:
                                visited[nidx] = 1
                                stack.append((nx, ny))

                if max_x - min_x + 1 >= self.min_region_size or max_y - min_y + 1 >= self.min_region_size:
                    regions.append((min_x, min_y, max_x, max_y))

        return regions
