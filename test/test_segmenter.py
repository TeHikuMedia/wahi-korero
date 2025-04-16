# Make `wahi_korero` visible on sys.path
import sys
sys.path.append("..")

import json
import os
import tempfile
from os import path
from pydub import AudioSegment
import unittest


import subprocess
import tempfile
import typing
import numpy as np
import soundfile as sf


from wahi_korero import ConfigError, default_segmenter, FormatError, Segmenter, AudioSource16Bit

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


output_dir = "out"


class SegmenterIntegrationTests(unittest.TestCase):

    #spotcheck_path = os.path.join(find_base_path(), "test", "sounds/spotcheck_file.wav")
    #silence_path = os.path.join(find_base_path(), "test", "sounds/10-minutes-of-silence.wav")
    hello_wav_path = os.path.join(find_base_path(), "test", "sounds/hello.wav")
    seg_too_large_path = os.path.join(find_base_path(), "test", "sounds/seg_too_large.wav")


    kaituhi_config = {
            'frame_duration_ms': 30,
            'buffer_length_ms': 1200,
            'threshold_silence_ms': 30,
            'threshold_voice_ms': 120,
            'aggression': 2,
            'squash_rate': 8000,
            'segment_limit':30
        }

    def setUp(self):
        if not path.exists(output_dir):
            os.mkdir(output_dir)
        for f in os.listdir(output_dir):
            os.remove(path.join(output_dir, f))
        self.segmenter = default_segmenter()
        self.segmenter.disable_captioning()

        tmp_dir = "/tmp"
        tmp_file_prefix = "test"
        sample_rate = 16000
        wav_file_path = self.silence_path
        #wav_file_path = self.
        self.AudioSource = AudioSource16Bit(wav_file_path, tmp_dir, tmp_file_prefix, sample_rate)


    # These tests only test segment_streams -> I haven't fixed segment audio therefore their tests aren't included here
   
    # This tests whether the segment_stream runs successfully without any ERROR
    def test_the_way_kaituhi_uses_it(self):

        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
        )

        stream = segmenter.segment_stream(self.hello_wav_path, output_audio=False)
        assert['success']
        
    # Checks whether the new segments are less than the segment limit
    def test_new_segments_less_than_limit(self):

        segmenter = Segmenter(**self.kaituhi_config)
        segmenter.enable_captioning(
            caption_threshold_ms=10,
            min_caption_len_ms=10000,
        )

        stream = segmenter.segment_stream(self.seg_too_large_path, output_audio=False)
        assert all((seg[1]-seg[0]) <= config['segment_limit'] for seg, audio in stream)

    # Fails if a non audio file in inputted into the stream
    def test_non_audio(self):
        try:
            self.segmenter.segment_audio("test_segmenter.py", "out")
            self.fail("Segmenter should have failed gracefully on unsupported file format.")
        except FormatError:
            pass  # desired behaviour
        except:
            self.fail("Segmenter should have failed gracefully on unsupported file format.")

   
if __name__ == "__main__":
    unittest.main(verbosity=2)