"""El volumen de la mezcla: que se lea lo que mide ffmpeg y que todo quede al mismo nivel."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.domain.errors import EngineError
from app.infrastructure.loudness import TARGET_LUFS, ffmpeg_exe, measure_loudness, normalize_loudness, parse_loudnorm


class LoudnessParseTests(unittest.TestCase):
    STDERR = """[Parsed_loudnorm_0 @ 0x1] \n{\n\t"input_i" : "-23.50",\n\t"input_tp" : "-4.10",\n\t"input_lra" : "3.20",
\t"input_thresh" : "-33.70",\n\t"output_i" : "-14.10",\n\t"target_offset" : "0.10"\n}\n"""

    def test_the_measurement_is_read_from_ffmpeg_output(self):
        heard = parse_loudnorm(self.STDERR)
        self.assertEqual((heard.integrated, heard.true_peak, heard.range, heard.threshold, heard.offset),
                         (-23.5, -4.1, 3.2, -33.7, 0.1))

    def test_garbage_is_an_engine_error(self):
        with self.assertRaises(EngineError):
            parse_loudnorm("nada")


@unittest.skipUnless(shutil.which(ffmpeg_exe()) or Path(ffmpeg_exe()).is_file(), "sin ffmpeg")
class FfmpegTests(unittest.TestCase):
    """Con ffmpeg de verdad: un audio flojo y otro fuerte, normalizados."""

    def _tone(self, folder: Path, name: str, expression: str, seconds: float) -> Path:
        out = folder / name
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", expression, "-t", str(seconds),
             "-ar", "44100", "-ac", "2", str(out)],
            check=True,
        )
        return out

    def test_normalizing_brings_a_quiet_and_a_loud_audio_to_the_same_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            quiet = self._tone(folder, "q.wav", "sine=frequency=300:beep_factor=1,volume=0.05", 6.0)
            loud = self._tone(folder, "l.wav", "sine=frequency=300,volume=0.8", 6.0)
            levels = []
            for name, src in (("q", quiet), ("l", loud)):
                out = folder / f"{name}.norm.wav"
                normalize_loudness(src, out)
                levels.append(measure_loudness(out).integrated)
            for level in levels:
                self.assertAlmostEqual(level, TARGET_LUFS, delta=1.5)
            self.assertAlmostEqual(levels[0], levels[1], delta=1.0)


if __name__ == "__main__":
    unittest.main()
