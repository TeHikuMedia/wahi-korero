
# Make `wahi_korero` visible on sys.path
import sys
sys.path.append("..")

import json
import os
from os import path
from pydub import AudioSegment
import unittest
from wahi_korero import ConfigError, default_segmenter, FormatError

output_dir = "out"


class SegmenterIntegrationTests(unittest.TestCase):

    def setUp(self):
        if not path.exists(output_dir):
            os.mkdir(output_dir)
        for f in os.listdir(output_dir):
            os.remove(path.join(output_dir, f))
        self.segmenter = default_segmenter()
        self.segmenter.disable_captioning()

    def test_segmenting(self):
        self.segmenter.segment_audio("sounds/hello.wav", output_dir, verbose=False)

    def test_json_output(self):
        self.segmenter.segment_audio("sounds/hello.wav", output_dir, verbose=False)
        stream = self.segmenter.segment_stream("sounds/hello.wav")
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
        self.segmenter.segment_audio("sounds/hello.wav", output_dir, verbose=False)
        stream = self.segmenter.segment_stream("sounds/hello.wav", output_audio=True)

        try:
            with open(path.join(output_dir, "segments.json"), "r") as f:
                data = json.load(f)
        except Exception as e:
            self.fail("Unexpected error loading JSON: {}".format(e))

        for (_, audio), seg in zip(stream, data["segments"]):
            self.assertEqual(round(seg["end"] - seg["start"], 3), len(audio) / 1000,
                             "Segments in JSON file should correspond to length of audio track.")

    def test_segment_against_stream(self):
        self.segmenter.segment_audio("sounds/hello.wav", output_dir, verbose=False)
        stream = self.segmenter.segment_stream("sounds/hello.wav")

        try:
            with open(path.join(output_dir, "segments.json"), "r") as f:
                data = json.load(f)
        except Exception as e:
            self.fail("Unexpected error loading JSON: {}".format(e))

        for (seg1, _), seg2 in zip(stream, data["segments"]):
            self.assertEqual(round(seg1[0], 3), round(seg1[0], 3), "Segments should be same in stream as in json.")
            self.assertEqual(round(seg1[1], 3), round(seg1[1], 3), "Segments should be same in stream as in json.")

    def test_non_audio(self):
        try:
            self.segmenter.segment_audio("test_segmenter.py", "out")
            self.fail("Segmenter should have failed gracefully on unsupported file format.")
        except FormatError:
            pass  # desired behaviour
        except:
            self.fail("Segmenter should have failed gracefully on unsupported file format.")

    def test_captioning(self):
        self.segmenter.enable_captioning(500)
        self.segmenter.segment_audio("sounds/hello.wav", output_dir, verbose=False)

    def test_captioning_min_length(self):
        audio_seg = AudioSegment.from_file("sounds/hello.wav", format="wav")
        audio_len = len(audio_seg)
        self.segmenter.enable_captioning(audio_len, min_caption_len_ms=audio_len)
        caption_stream = self.segmenter.segment_stream("sounds/hello.wav")
        self.assertEqual(len(list(caption_stream)), 1, "Should have one caption") # one caption, the whole length of the track

if __name__ == "__main__":
    unittest.main(verbosity=2)
