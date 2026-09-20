"""Local image upscaling CLI using Pillow and Lanczos interpolation."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import sys
import tempfile

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
           ".webp": "WEBP", ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF"}
MAX_PIXELS = 80_000_000


def scale_value(value: str) -> float:
    try:
        scale = float(value.lower().removesuffix("x"))
    except ValueError:
        raise argparse.ArgumentTypeError("Scale must be a number, for example: 2, 4, or 2.5.") from None
    if not math.isfinite(scale) or scale < 1:
        raise argparse.ArgumentTypeError("Scale must be a finite number greater than or equal to 1.")
    return scale


def sharpness_value(value: str) -> float:
    try:
        amount = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Sharpen must be a number between 0 and 3.") from None
    if not math.isfinite(amount) or not 0 <= amount <= 3:
        raise argparse.ArgumentTypeError("Sharpen must be between 0 and 3.")
    return amount


def output_size(width: int, height: int, scale: float) -> tuple[int, int]:
    # Check before rounding to handle huge but finite scales.
    scaled_width, scaled_height = width * scale, height * scale
    if not math.isfinite(scaled_width * scaled_height) or scaled_width * scaled_height > MAX_PIXELS:
        raise ValueError("Output exceeds the 80-megapixel limit; use a smaller scale.")
    return max(1, round(scaled_width)), max(1, round(scaled_height))


def upscale(source: Path, target: Path, scale: float, sharpen: float,
            quality: int, overwrite: bool) -> tuple[tuple[int, int], tuple[int, int]]:
    if source.resolve() == target.resolve():
        raise ValueError("Output cannot be the same as the input file.")
    if target.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {target}. Use --overwrite to replace it.")
    if target.suffix.lower() not in FORMATS:
        raise ValueError("Output extension must be PNG, JPG, WebP, BMP, or TIFF.")

    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise ValueError("Animated and multi-frame images are not supported.")
        # EXIF orientation affects the visible dimensions.
        oriented = ImageOps.exif_transpose(original)
        before = oriented.size
        after = output_size(*before, scale)
        alpha = "A" in oriented.getbands() or "transparency" in oriented.info
        work = oriented.convert("RGBA" if alpha else "RGB")
        result = work.resize(after, Image.Resampling.LANCZOS)
        if sharpen:
            rgb = result.convert("RGB").filter(
                ImageFilter.UnsharpMask(radius=1.5, percent=round(sharpen * 100), threshold=3)
            )
            if alpha:
                rgb.putalpha(result.getchannel("A"))
            result = rgb

        fmt = FORMATS[target.suffix.lower()]
        if fmt in {"JPEG", "BMP"} and alpha:
            background = Image.new("RGB", result.size, "white")
            background.paste(result, mask=result.getchannel("A"))
            result = background
        save_options = {}
        if fmt in {"JPEG", "WEBP"}:
            save_options["quality"] = quality
        if fmt == "JPEG":
            save_options["subsampling"] = 0
        if fmt in {"PNG", "JPEG", "WEBP", "TIFF"} and original.info.get("icc_profile"):
            save_options["icc_profile"] = original.info["icc_profile"]
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
            result.save(temporary, format=fmt, **save_options)
            if overwrite:
                os.replace(temporary, target)
            else:
                # Publish atomically without replacing an existing output.
                os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return before, after


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Upscale images locally with Lanczos interpolation (not AI super-resolution).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cli.add_argument("input", type=Path, help="Image file or directory (non-recursive)")
    cli.add_argument("-s", "--scale", type=scale_value, default=2.0,
                     help="Scale factor, such as 2, 4, 2.5, or 8x")
    cli.add_argument("-o", "--output", type=Path,
                     help="Output file, or output directory in batch mode")
    cli.add_argument("--format", choices=["png", "jpg", "webp", "bmp", "tiff"], default=None,
                     help="Output format; must match the -o extension when -o is a file")
    cli.add_argument("--sharpen", type=sharpness_value, default=0.0,
                     help="Unsharp-mask strength from 0 to 3")
    cli.add_argument("--quality", type=int, default=95, help="JPG/WebP quality from 1 to 100")
    cli.add_argument("--overwrite", action="store_true", help="Replace existing output files")
    return cli


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if not 1 <= args.quality <= 100:
        cli.error("--quality must be between 1 and 100.")
    source = args.input
    if not source.exists():
        cli.error(f"Input not found: {source}")
    batch = source.is_dir()
    if batch:
        sources = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
        if not sources:
            cli.error("The directory does not contain any supported images.")
        directory = args.output or source / "upscaled"
        if directory.exists() and not directory.is_dir():
            cli.error("Batch output must be a directory.")
    else:
        if not source.is_file():
            cli.error("Input must be a file or directory.")
        sources = [source]
        directory = source.parent
    extension = args.format or "png"
    tag = format(args.scale, ".12g")
    jobs = []
    for item in sources:
        name = f"{item.stem}_{tag}x.{extension}"
        if batch:
            target = directory / name
        elif args.output:
            target = args.output / name if args.output.is_dir() else args.output
        else:
            target = directory / name
        if target.suffix.lower() not in FORMATS:
            cli.error(f"Unsupported output extension: {target}")
        if args.format and FORMATS[target.suffix.lower()] != FORMATS["." + args.format]:
            cli.error("--format does not match the output file extension.")
        jobs.append((item, target))

    targets = [str(target.resolve()).casefold() for _, target in jobs]
    if len(targets) != len(set(targets)):
        cli.error("Output names collide (for example, photo.jpg and photo.png). Rename an input first.")
    inputs = {str(item.resolve()).casefold() for item in sources}
    if any(target in inputs for target in targets):
        cli.error("Output cannot overwrite an input file, including another input in the batch.")

    failed = 0
    for index, (item, target) in enumerate(jobs, 1):
        try:
            before, after = upscale(item, target, args.scale, args.sharpen, args.quality, args.overwrite)
            print(f"[{index}/{len(jobs)}] OK {item.name}: {before[0]}x{before[1]} -> "
                  f"{after[0]}x{after[1]} | {target}", flush=True)
        except (OSError, ValueError, MemoryError, UnidentifiedImageError,
                Image.DecompressionBombError) as error:
            failed += 1
            print(f"[{index}/{len(jobs)}] FAILED {item.name}: {error}", file=sys.stderr, flush=True)
    print(f"Done: {len(jobs) - failed} succeeded, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
