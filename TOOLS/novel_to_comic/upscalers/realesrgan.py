"""Real-ESRGAN upscaler (default model: RealESRGAN_x4plus_anime_6B).

Lazy imports: `realesrgan` + `basicsr` + torch are only required when this
provider is actually used. The model stays resident during a batch.

Install on the target Windows/GPU machine:

    pip install realesrgan
    # model weights are downloaded automatically on first use, or fetch
    # RealESRGAN_x4plus_anime_6B.pth manually into weights/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .base import BaseUpscaler, UpscaleResult, DEFAULT_MODEL


class RealEsrganUpscaler(BaseUpscaler):
    name = "realesrgan"

    def __init__(self, model: str = DEFAULT_MODEL, scale: int = 4, device: str | None = None, weights_dir: str = "weights", quality: int = 95, **_: object) -> None:
        self.model = model
        self.default_scale = scale
        self.device = device
        self.weights_dir = weights_dir
        self.quality = int(quality)
        self._upscaler: Any = None

    def warm(self) -> None:
        if self._upscaler is not None:
            return
        try:
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
            from realesrgan.archs.srvgg_arch import SRVGGNetCompact
        except ImportError as error:  # pragma: no cover - GPU machine only
            raise RuntimeError(
                "realesrgan provider needs the realesrgan package: pip install realesrgan"
            ) from error

        if self.model == "RealESRGAN_x4plus_anime_6B":
            architecture = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
        else:
            architecture = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type="prelu")

        weights_path = Path(self.weights_dir) / f"{self.model}.pth"
        if not weights_path.exists():
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            url_map = {
                "RealESRGAN_x4plus_anime_6B": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
                "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            }
            url = url_map.get(self.model)
            if url:
                import urllib.request
                urllib.request.urlretrieve(url, str(weights_path))

        self._upscaler = RealESRGANer(
            scale=4,
            model_path=str(weights_path),
            model=architecture,
            tile=512,
            tile_pad=16,
            pre_pad=0,
            half=True,
            device=self.device,
        )

    def release(self) -> None:
        self._upscaler = None

    def _upscale(self, src: Path, dst: Path, scale: int) -> UpscaleResult:
        self.warm()
        import cv2

        image = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
        output, _ = self._upscaler.enhance(image, outscale=scale)

        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        ext = dst.suffix.lower()
        if ext == ".webp":
            rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            Image.fromarray(rgb).save(dst, format="WEBP", quality=self.quality, method=6)
        elif ext == ".png":
            cv2.imwrite(str(dst), output, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        else:
            cv2.imwrite(str(dst), output)

        with Image.open(dst) as result:
            width, height = result.size
        return UpscaleResult(path=str(dst), width=width, height=height, scale=scale, provider=self.name, model=self.model)
