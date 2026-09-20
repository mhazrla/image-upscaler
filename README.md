# Image Upscaler CLI

A small, privacy-friendly command-line tool for enlarging images by 2x, 4x, or any custom scale factor. All processing happens locally with Pillow's high-quality Lanczos resampling—no uploads, API keys, or external services required.

> [!NOTE]
> This is a traditional image resizer, not an AI super-resolution model. It produces smooth, high-quality enlargements but does not reconstruct new details.

## Features

- Scale a single image or every supported image in a directory
- Use standard 2x and 4x scaling or any custom factor of 1 or greater
- Read and write PNG, JPEG, WebP, BMP, and TIFF
- Preserve transparency in PNG, WebP, and TIFF output
- Correct EXIF orientation and preserve ICC color profiles when possible
- Apply optional sharpening after resizing
- Protect input files and existing outputs by default
- Process images locally and offline

## Requirements

- Python 3.10 or newer
- Pillow 12.3 or newer

## Installation

Clone the repository and install it in a virtual environment:

```bash
git clone https://github.com/mhazrla/image-upscaler.git
cd image-upscaler
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS or Linux
source .venv/bin/activate
```

Install the command:

```bash
python -m pip install -e .
```

You can now run `image-upscaler` from the activated environment. Alternatively, install only the dependency with `python -m pip install -r requirements.txt` and use `python upscale.py` in the examples below.

## Usage

The default scale is 2x and the default output format is PNG:

```bash
image-upscaler photo.jpg
# Creates photo_2x.png
```

Choose a 4x scale and an explicit output path:

```bash
image-upscaler photo.jpg --scale 4 --output enlarged.png
```

Use a custom decimal scale. The optional `x` suffix is accepted:

```bash
image-upscaler photo.jpg --scale 2.5
image-upscaler photo.jpg --scale 8x --sharpen 0.6
```

Process every supported image directly inside a directory:

```bash
image-upscaler ./input --scale 4 --output ./output --format webp --quality 95
```

Without `--output`, batch results are written to an `upscaled` subdirectory. Directory processing is non-recursive.

Convert a transparent image to JPEG. Transparent areas are placed on a white background:

```bash
image-upscaler logo.png --scale 2 --output enlarged.jpg
```

See every option:

```bash
image-upscaler --help
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `input` | Image file or directory to process | Required |
| `-s`, `--scale` | Scale factor of 1 or greater; accepts values such as `2`, `2.5`, or `4x` | `2` |
| `-o`, `--output` | Output file for one image or output directory for a batch | Automatic |
| `--format` | Batch/default output format: `png`, `jpg`, `webp`, `bmp`, or `tiff` | `png` |
| `--sharpen` | Unsharp-mask strength from `0` to `3` | `0` |
| `--quality` | JPEG or WebP quality from `1` to `100` | `95` |
| `--overwrite` | Replace output files that already exist | Disabled |

## Output behavior

- Automatic names include the scale, such as `photo_2x.png` or `photo_2.5x.png`.
- Explicit output file extensions determine the output format. If `--format` is also supplied, it must match that extension.
- Output dimensions are rounded to the nearest pixel after EXIF orientation is applied.
- Output is 8-bit RGB or RGBA; HDR and 16-bit workflows are not supported.
- Animated and multi-frame images are rejected.
- Output is limited to 80 megapixels per image to reduce accidental memory exhaustion. Large images can still require substantial RAM.
- Existing output is rejected unless `--overwrite` is used. Input files are always protected.
- Exit code `0` means success, `1` means one or more images failed, and `2` means the arguments were invalid. Batch processing continues when one image fails.

## Development

Install the project, then run the test suite:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## License

Image Upscaler CLI is available under the [MIT License](LICENSE).
