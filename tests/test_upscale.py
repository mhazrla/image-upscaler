import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from upscale import main, output_size


class UpscaleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "sample.png"
        Image.new("RGBA", (12, 8), (200, 50, 10, 100)).save(self.source)

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main([str(arg) for arg in args])

    def test_custom_scale_and_transparency(self):
        output = self.root / "result.png"
        self.assertEqual(self.run_cli(self.source, "-s", "2.5x", "-o", output), 0)
        with Image.open(output) as result:
            self.assertEqual(result.size, (30, 20))
            self.assertEqual(result.getpixel((10, 10))[3], 100)

    def test_jpeg_flattening(self):
        output = self.root / "result.jpg"
        self.assertEqual(self.run_cli(self.source, "-s", "4", "-o", output), 0)
        with Image.open(output) as result:
            self.assertEqual(result.size, (48, 32))
            self.assertEqual(result.mode, "RGB")
            self.assertGreater(result.getpixel((0, 0))[1], 150)

    def test_no_overwrite_and_explicit_overwrite(self):
        output = self.root / "result.png"
        output.write_bytes(b"existing content")
        self.assertEqual(self.run_cli(self.source, "-o", output), 1)
        self.assertEqual(output.read_bytes(), b"existing content")
        self.assertEqual(self.run_cli(self.source, "-o", output, "--overwrite"), 0)

    def test_protect_input(self):
        before = self.source.read_bytes()
        with self.assertRaises(SystemExit) as error:
            self.run_cli(self.source, "-o", self.source, "--overwrite")
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.source.read_bytes(), before)

    def test_batch_continues_after_corrupt_input(self):
        (self.root / "broken.jpg").write_bytes(b"not an image")
        self.assertEqual(self.run_cli(self.root), 1)
        self.assertTrue((self.root / "upscaled" / "sample_2x.png").is_file())

    def test_collision_rejected(self):
        Image.new("RGB", (3, 3)).save(self.root / "sample.jpg")
        with self.assertRaises(SystemExit):
            self.run_cli(self.root)
        self.assertFalse((self.root / "upscaled").exists())

    def test_invalid_scales(self):
        for scale in ["0", "-2", "nan", "inf", "hello"]:
            with self.subTest(scale=scale), self.assertRaises(SystemExit):
                self.run_cli(self.source, "--scale", scale)

    def test_pixel_limit(self):
        with self.assertRaises(ValueError):
            output_size(10000, 10000, 4)
        with self.assertRaises(ValueError):
            output_size(100, 100, 1e308)

    def test_exif_orientation(self):
        source = self.root / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (12, 8)).save(source, exif=exif)
        output = self.root / "rotated.png"
        self.assertEqual(self.run_cli(source, "-o", output), 0)
        with Image.open(output) as result:
            self.assertEqual(result.size, (16, 24))
            self.assertIsNone(result.getexif().get(274))

    def test_webp_sharpen(self):
        output = self.root / "result.webp"
        self.assertEqual(self.run_cli(self.source, "-o", output, "--sharpen", "0.6"), 0)
        with Image.open(output) as result:
            self.assertEqual(result.size, (24, 16))
            self.assertIn("A", result.getbands())


if __name__ == "__main__":
    unittest.main()
