import json
import sys
from glob import glob
from math import floor

import ffmpeg

sys.path.append("..")
import os
import unittest

from wahi_korero import Segmenter, default_segmenter
from wahi_korero.audiosegment import MyAudioSegment
from wahi_korero.exceptions import FormatError


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

# NOTE: These files shall not be committed to our repo as its public and under
# the Kaitiakitanga License these files are not to be "open".
LOCAL_TEST_FILES_DIRECTORY = os.path.join(
    find_base_path(), "tests", "sounds/local_tests"
)


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
    nga_take = os.path.join(find_base_path(), "tests", "sounds/nga_take.m4a")

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
        """
        for whatever reason someone changed the squash rate, so this one sets
        it to what kaituhi uses
        """
        config = {**self.kaituhi_config, "squash_rate": 8000}
        segmenter = Segmenter(**config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10 * 1000,
            max_caption_len_ms=100 * 1000,
        )

        stream = segmenter.segment_stream(self.silence_with_audio, output_audio=False)
        caps = []
        for seg, _ in stream:
            start, end, _ = seg
            dt = end - start
            mins = floor(dt / 60)
            secs = round(dt - mins * 60)
            print(
                f"{round(start):> 3.0f}",
                f"{round(end):> 3.0f}",
                f"{ mins:02.0f}:{secs:02.0f}",
            )
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

    def test_the_min_cap_length(self):

        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=500,
        )

        stream = segmenter.segment_stream(self.hello_wav_path, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator
            start, end, _ = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(start, end)

        assert caps[0]["end"] == caps[1]["start"]
        assert caps[1]["end"] == 2.79
        assert caps[2]["start"] == 2.79

    def test_5_min_silence_max_min_captions(self):
        """
        squash rate is not 8k here, that's diff from the kaituhi test above
        """
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10 * 1000,
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
            print(f"{round(start):>3.0f}", f"{round(end):>3.0f}", round(end - start))

        # NOTE Below assertions are essential, DO NOT CHANGE
        # These assertions are specific as we want to make sure silence is
        # merged in the most logical places
        assert round(caps[0]["end"]) == 100
        assert round(caps[2]["end"]) == 300
        assert round(caps[3]["end"] - caps[3]["start"]) == 30
        # assert round(caps[9]["end"]) == 16

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

        # NOTE Below assertions are essential, DO NOT CHANGE
        # these ensure the small amounts of voiced frames in the buffer that
        # triggers a voice frame collection is included with the voiced frames.
        assert caps[3]["end"] == 330.3
        assert caps[4]["end"] == 414.36

    def test_ngatake_max_min_captions(self):
        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
            max_caption_len_ms=100 * 1000,
        )

        stream = segmenter.segment_stream(self.nga_take, output_audio=False)
        caps = []
        for seg, _ in stream:  # We don't return audio in this iterator

            start, end, voiced = seg
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )
            print(f"{round(start):>3.0f}", f"{round(end):>3.0f}", round(end - start))

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

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

        # Below assertions are essential, DO NOT CHANGE
        # these ensure the small amounts of voiced frames in the buffer that
        # triggers a voice frame collection is included with the voiced frames.
        assert caps[0]["end"] == caps[1]["start"]
        assert caps[0]["end"] == 330.3
        assert caps[8]["start"] == 414.36
        assert caps[8]["end"] == 744.69

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
        except Exception:
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
            with open(os.path.join(outdir, "segments.json"), "r") as f:
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
            with open(os.path.join(output_dir, "segments.json"), "r") as f:
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
            with open(os.path.join(output_dir, "segments.json"), "r") as f:
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

    def test_failure_not_end_silence(self):
        """
        A file that ends hard, no silence, tests final yield in caption.
        Tests a failure mode we encountered in writing this code.
        """
        config = {**self.kaituhi_config, "squash_rate": 8000}
        segmenter = Segmenter(**config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10 * 1000,
            max_caption_len_ms=100 * 1000,
        )
        path = os.path.join(find_base_path(), "tests", "sounds/no_end_silence.m4a")
        stream = segmenter.segment_stream(path, output_audio=False)
        caps = []
        for seg, _ in stream:
            start, end, _ = seg
            dt = end - start
            mins = floor(dt / 60)
            secs = round(dt - mins * 60)
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

    def test_last_cap_gap(self):
        """
        A file that ends hard, no silence, tests final yield in caption.
        Tests a failure mode we encountered in writing this code.
        """
        config = {**self.kaituhi_config, "squash_rate": 8000}
        segmenter = Segmenter(**config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10 * 1000,
        )
        audio_path = os.path.join(
            find_base_path(), "tests", "sounds/last_cap_failure_gap.m4a"
        )
        stream = segmenter.segment_stream(audio_path, output_audio=False)
        caps = []
        for seg, _ in stream:
            start, end, _ = seg
            dt = end - start
            mins = floor(dt / 60)
            secs = round(dt - mins * 60)
            print(
                f"{(start):> 3.2f}",
                f"{(end):> 3.2f}",
                f"{ mins:02.0f}:{secs:02.0f}",
            )
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

    # Basic test whether the stream runs smoothly on a small file
    def test_recursive_aggression(self):
        """
        start with aggression 1, and go for it.
        """
        config = {**self.kaituhi_config, "squash_rate": 8000, "aggression": 1}
        segmenter = Segmenter(**config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10 * 1000,
            max_caption_len_ms=100 * 1000,
        )

        stream = segmenter.segment_stream(self.silence_with_audio, output_audio=False)
        caps = []
        for seg, _ in stream:
            start, end, _ = seg
            dt = end - start
            mins = floor(dt / 60)
            secs = round(dt - mins * 60)
            print(
                f"{round(start):> 3.0f}",
                f"{round(end):> 3.0f}",
                f"{ mins:02.0f}:{secs:02.0f}",
            )
            caps.append(
                {
                    "start": start,
                    "end": end,
                }
            )

        for i in range(len(caps) - 1):
            assert round(caps[i]["end"] - caps[i]["start"]) <= 100
            assert round(caps[i]["end"] - caps[i]["start"]) >= 10
            assert caps[i]["end"] == caps[i + 1]["start"]

    def test_recursive_aggression_captions_local_files(self):
        """
        Tests for key files
        """
        caption_configs = [
            {
                "caption_threshold_ms": 10,
                "min_caption_len_ms": 10 * 1000,
                "max_caption_len_ms": 90 * 1000,
                "target_caption_len_ms": 20 * 1000,
            },
            {
                "caption_threshold_ms": 20,
                "min_caption_len_ms": 10 * 1000,
                "target_caption_len_ms": 20 * 1000,
                "max_caption_len_ms": 90 * 1000,
            },
            {
                "caption_threshold_ms": 10,
                "min_caption_len_ms": 10 * 1000,
                "max_caption_len_ms": 120 * 1000,
                "target_caption_len_ms": 40 * 1000,
            },
            {
                "caption_threshold_ms": 20,
                "min_caption_len_ms": 10 * 1000,
                "max_caption_len_ms": 120 * 1000,
                "target_caption_len_ms": 40 * 1000,
            },
            {
                "caption_threshold_ms": 120,
                "min_caption_len_ms": 10 * 1000,
                "max_caption_len_ms": 120 * 1000,
                "target_caption_len_ms": 40 * 1000,
            },
        ]

        for caption_config in caption_configs:
            print(caption_config)
            for f in glob(os.path.join(LOCAL_TEST_FILES_DIRECTORY, "*")):
                print(f)
                data = ffmpeg.probe(f)
                duration = None
                for stream in data["streams"]:
                    duration = float(stream.get("duration", None))
                print(duration)

                if duration / 60 <= 30:
                    aggression = 1
                else:
                    aggression = 1
                config = {
                    "frame_duration_ms": 30,
                    "buffer_length_ms": 1200,
                    "threshold_silence_ms": 30,
                    "threshold_voice_ms": 120,
                    "aggression": aggression,
                    "squash_rate": 8000,
                }
                segmenter = Segmenter(**config)
                segmenter.enable_captioning(**caption_config)

                stream = segmenter.segment_stream(f, output_audio=False)
                caps = []

                seg, _ = next(stream, None)
                while seg is not None:
                    next_seg = next(stream, None)
                    if next_seg:
                        next_seg, _ = next_seg
                    start, end, _ = seg
                    caps.append(
                        {
                            "start": start,
                            "end": end,
                        }
                    )
                    dt = end - start
                    mins = floor(dt / 60)
                    secs = round(dt - mins * 60)
                    print(
                        f"{round(start):> 8.0f}",
                        f"{round(end):> 8.0f}",
                        f"{ mins:> 5.0f}:{secs:02.0f}",
                    )

                    if next_seg is not None:
                        print("TEST", seg, next_seg)
                        assert (
                            round(dt)
                            >= caption_config["min_caption_len_ms"] / 1000 * 0.9
                        )  # allow % error.
                        assert next_seg[0] == end
                    assert (
                        round(dt) <= caption_config["max_caption_len_ms"] / 1000 * 1.1
                    )

                    seg = next_seg

                print()
                del segmenter


if __name__ == "__main__":
    unittest.main(verbosity=2)
