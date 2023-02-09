from wahi_korero.segment import ConfigError, default_segmenter, FormatError
from wahi_korero.utils import SUPPORTED_FORMATS
from unittest import TestCase
from pydub import AudioSegment
from os import path
import os
import json
import sys
import subprocess
import pytest

output_dir = "out"


class TestSegmenterIntegrationTests(TestCase):

    def setUp(self):
        if not path.exists(output_dir):
            os.mkdir(output_dir)
        self.segmenter = default_segmenter()
        self.segmenter.disable_captioning()

    def test_segmenting(self):
        for fmt in SUPPORTED_FORMATS:
            out = os.path.join(output_dir, 'segmenting', fmt)
            os.makedirs(out, exist_ok=True)
            self.segmenter.segment_audio(
                f"test/sounds/hello.{fmt}", out, verbose=False)

    def test_json_output(self):
        self.segmenter.segment_audio(
            "test/sounds/hello.wav", output_dir, verbose=False)
        stream = self.segmenter.segment_stream("test/sounds/hello.wav")
        num_segs = sum(1 for _ in stream)

        try:
            with open(path.join(output_dir, "segments.json"), "r") as f:
                data = json.load(f)
            if "segments" not in data:
                self.fail("JSON output has no `segments` key.")
            if len(data["segments"]) != num_segs:
                self.fail("JSON output has no segments.")
        except TypeError:
            self.fail("Output of segment_audio was not valid JSON.")
        except Exception as e:
            self.fail("Unexpected error {}".format(e))

    def test_segment_against_track_len(self):
        for f in SUPPORTED_FORMATS:

            self.segmenter.segment_audio(
                f"test/sounds/hello.{f}", output_dir, verbose=False)
            stream = self.segmenter.segment_stream(
                f"test/sounds/hello.{f}", output_audio=True)

            try:
                with open(path.join(output_dir, "segments.json"), "r") as f:
                    data = json.load(f)
            except Exception as e:
                self.fail("Unexpected error loading JSON: {}".format(e))

            print(data)
            for (_, audio), seg in zip(stream, data["segments"]):
                print(data['segments'])
                self.assertEqual(
                    round(seg["end"] - seg["start"], 4),
                    round(len(audio) / 1000, 4),
                    "Segments in JSON file should correspond to length of audio track."
                )

    def test_segment_against_stream(self):
        for f in SUPPORTED_FORMATS:
            self.segmenter.segment_audio(
                f"test/sounds/hello.{f}", output_dir, verbose=False)
            stream = self.segmenter.segment_stream(f"test/sounds/hello.{f}")

            try:
                with open(path.join(output_dir, "segments.json"), "r") as f:
                    data = json.load(f)
            except Exception as e:
                self.fail("Unexpected error loading JSON: {}".format(e))

            for (seg1, _), seg2 in zip(stream, data["segments"]):
                self.assertEqual(round(seg1[0], 3), round(
                    seg1[0], 3), "Segments should be same in stream as in json.")
                self.assertEqual(round(seg1[1], 3), round(
                    seg1[1], 3), "Segments should be same in stream as in json.")

    def test_non_audio(self):
        try:
            self.segmenter.segment_audio("test/test_segmenter.py", "out")
            self.fail(
                "Segmenter should have failed gracefully on unsupported file format."
            )
        except FormatError:
            pass  # desired behavior

    def test_captioning(self):
        for fmt in SUPPORTED_FORMATS:
            print(f"testing captions for {fmt}")
            out = os.path.join(output_dir, 'captioning', fmt)
            os.makedirs(out, exist_ok=True)
            self.segmenter.enable_captioning(500)
            self.segmenter.segment_audio(
                f"test/sounds/hello.{fmt}", out, verbose=False)

            with open(path.join(out, "segments.json"), "r") as f:
                data = json.load(f)

            duration = 0
            file_duration = 0
            for i in range(data['num_segments']):
                duration += data['segments'][i]['end'] - \
                    data['segments'][i]['start']
                p = subprocess.Popen(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1',
                     path.join(out, data['segments'][i]['fname'])],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)

                output, errors = p.communicate()
                file_duration += float(output)

            self.assertEqual(
                round(duration, 2),
                round(data['track_duration'], 2),
                "json " + fmt
            )
            self.assertEqual(
                round(duration, 2),
                round(file_duration, 2),
                "files " + fmt
            )
            print(f"captions for {fmt} PASSED")

    def test_captioning_min_length(self):
        audio_seg = AudioSegment.from_file(
            "test/sounds/hello.wav", format="wav")
        audio_len = len(audio_seg)
        self.segmenter.enable_captioning(
            audio_len, min_caption_len_ms=audio_len)
        caption_stream = self.segmenter.segment_stream("test/sounds/hello.wav")
        # one caption, the whole length of the track
        self.assertEqual(len(list(caption_stream)),
                         1, "Should have one caption")


if __name__ == "__main__":
    unittest.main(verbosity=2)
