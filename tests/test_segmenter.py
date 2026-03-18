import json
import sys

sys.path.append("..")
import os
import unittest
from os import path

from wahi_korero import FormatError, Segmenter, default_segmenter
from wahi_korero.audiosegment import MyAudioSegment


def find_base_path():
    # find the base path of the project - in a docker or when running tests can vary
    if os.path.exists(os.path.join("..", "setup.py")):
        return ".."
    elif os.path.exists(os.path.join(".", "setup.py")):
        return "."
    elif os.path.exists(os.path.join("/", "setup.py")):
        return "/"
    else:
        raise ValueError("Could not find base path for setup.py")


output_dir = "tests/output"


class SegmenterIntegrationTests(unittest.TestCase):

    # spotcheck_path = os.path.join(find_base_path(), "test", "sounds/spotcheck_file.wav")
    silence_path = os.path.join(
        find_base_path(), "tests", "sounds/10-minutes-of-silence.mp3"
    )
    hello_wav_path = os.path.join(find_base_path(), "tests", "sounds/hello.wav")
    seg_too_large_path = os.path.join(
        find_base_path(), "tests", "sounds/seg_too_large.wav"
    )
    silence_with_audio = os.path.join(
        find_base_path(), "tests", "sounds/5_mins_silence.m4a"
    )

    kaituhi_config = {
        "frame_duration_ms": 30,
        "buffer_length_ms": 1200,
        "threshold_silence_ms": 30,
        "threshold_voice_ms": 120,
        "aggression": 2,
        "squash_rate": 4000,  # changed from 8000 to 4000
    }

    def setUp(self):
        os.makedirs(output_dir, exist_ok=True)
        self.segmenter = default_segmenter()
        self.segmenter.disable_captioning()

    def test_silence(self):
        """
        We should get 1 caption the entire duration of silence
        """
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
        )

        stream = segmenter.segment_stream(self.silence_path, output_audio=False)
        for seg, audio in stream:
            start, end, voiced = seg

        assert round(end) == 600  # one long silent caption

    def test_max_caption_of_silence(self):
        """
        We should get silence captions broken up into max cap len
        """
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=1000,
            max_caption_len_ms=100 * 1000,
        )

        stream = segmenter.segment_stream(self.silence_path, output_audio=False)
        for seg, audio in stream:
            start, end, voiced = seg
            print((start), (end), (end - start))
            assert round(end - start) <= 100

        assert round(end) == 600  # one long silent caption

    # Basic test whether the stream runs smoothly on a small file
    def test_the_way_kaituhi_uses_it(self):

        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
        )

        stream = segmenter.segment_stream(self.silence_path, output_audio=False)
        for seg, audio in stream:
            start, end, voiced = seg
            print(start, end)

        assert True

    def test_the_min_cap_length(self):

        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=500,
        )

        stream = segmenter.segment_stream(self.hello_wav_path, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, voiced = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(start, end)

        assert caps[0]["end"] == caps[1]["start"]
        assert caps[1]["end"] == 1.5150000000000001
        assert caps[2]["start"] == 1.5150000000000001

    def test_5_min_silence_max_min_captions(self):
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
            max_caption_len_ms=100 * 1000,
        )

        stream = segmenter.segment_stream(self.silence_with_audio, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, voiced = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(round(start), round(end), round(end - start))

        assert caps[0]["end"] == caps[1]["start"]
        assert round(caps[0]["end"]) == 100
        assert round(caps[2]["end"]) == 330
        assert round(caps[12]["end"]) == 745

    def test_max_caption(self):
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            max_caption_len_ms=14000,
        )
        stream = segmenter.segment_stream(self.silence_with_audio, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, voiced = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(round(start), round(end), round(end - start))

        assert caps[0]["end"] == caps[1]["start"]
        assert round(caps[0]["end"]) == 14

    def test_min_caption(self):
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
        )
        stream = segmenter.segment_stream(self.silence_with_audio, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, voiced = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(round(start), round(end), round(end - start))

        assert caps[0]["end"] == caps[1]["start"]
        assert round(caps[0]["end"]) == 330
        assert round(caps[8]["end"]) == 745

    # Checks whether captions are less then max
    def test_new_segments_less_than_limit(self):
        MAX = 100 * 1000
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
            max_caption_len_ms=MAX,
        )

        stream = segmenter.segment_stream(self.seg_too_large_path, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, _ = seg
            caps.append([end, start])

        assert all((cap[1] - cap[0]) <= MAX for cap in caps)

    # Fails if a non audio file in inputted into the stream
    def test_non_audio(self):
        try:
            self.segmenter.segment_audio(
                "tests/test_segmenter.py", output_dir, output_audio=False
            )
            self.fail(
                "Segmenter should have failed gracefully on unsupported file format."
            )
        except FormatError:
            pass  # desired behaviour
        except:
            self.fail(
                "Segmenter should have failed gracefully on unsupported file format."
            )

    # Olds tests?
    def test_segmenting(self):
        out = os.path.join(find_base_path(), output_dir, "segmenting")
        os.makedirs(out, exist_ok=True)
        self.segmenter.segment_audio(
            self.hello_wav_path,
            out,
            verbose=False,
            output_audio=True,
        )

    def test_json_output(self):
        outdir = os.path.join(find_base_path(), output_dir)
        self.segmenter.segment_audio(
            self.hello_wav_path,
            outdir,
            verbose=False,
            output_audio=False,
        )
        stream = self.segmenter.segment_stream(self.hello_wav_path)
        num_segs = sum(1 for _ in stream)

        try:
            with open(path.join(outdir, "segments.json"), "r") as f:
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
        self.segmenter.segment_audio(
            self.hello_wav_path,
            os.path.join(find_base_path(), output_dir),
            verbose=False,
            output_audio=False,
        )
        stream = self.segmenter.segment_stream(self.hello_wav_path, output_audio=False)

        try:
            with open(path.join(output_dir, "segments.json"), "r") as f:
                data = json.load(f)
        except Exception as e:
            self.fail("Unexpected error loading JSON: {}".format(e))

        for (_, audio), seg in zip(stream, data["segments"]):
            if audio:
                self.assertEqual(
                    round(seg["end"] - seg["start"], 3),
                    len(audio) / 1000,
                    "Segments in JSON file should correspond to length of audio track.",
                )

    def test_segment_against_stream(self):
        self.segmenter.segment_audio(
            self.hello_wav_path, output_dir, verbose=False, output_audio=False
        )
        stream = self.segmenter.segment_stream(self.hello_wav_path)

        try:
            with open(path.join(output_dir, "segments.json"), "r") as f:
                data = json.load(f)
        except Exception as e:
            self.fail("Unexpected error loading JSON: {}".format(e))

        for (seg1, _), seg2 in zip(stream, data["segments"]):
            self.assertEqual(
                round(seg1[0], 3),
                round(seg1[0], 3),
                "Segments should be same in stream as in json.",
            )
            self.assertEqual(
                round(seg1[1], 3),
                round(seg1[1], 3),
                "Segments should be same in stream as in json.",
            )

    def test_captioning(self):
        self.segmenter.enable_captioning(500)
        self.segmenter.segment_audio(
            self.hello_wav_path, output_dir, verbose=False, output_audio=False
        )

    def test_captioning_min_length(self):
        audio_seg = MyAudioSegment.from_file(self.hello_wav_path, format="wav")
        audio_len = len(audio_seg)
        self.segmenter.enable_captioning(audio_len, min_caption_len_ms=audio_len)
        caption_stream = self.segmenter.segment_stream(self.hello_wav_path)
        self.assertEqual(
            len(list(caption_stream)), 1, "Should have one caption"
        )  # one caption, the whole length


if __name__ == "__main__":
    unittest.main(verbosity=2)
