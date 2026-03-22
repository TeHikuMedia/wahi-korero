"""
Print time to segment
"""

import os
import sys
import time

from wahi_korero import Segmenter


def profile(path):
    print("No captions")
    for aggression in [1, 2, 3]:
        for squash in [2000, 4000, 8000]:
            print(f"Agrression: {aggression}, Squash Rate: {squash}")
            segmenter = Segmenter(
                **{
                    "frame_duration_ms": 30,
                    "buffer_length_ms": 1200,
                    "threshold_silence_ms": 30,
                    "threshold_voice_ms": 120,
                    "aggression": 2,
                    "squash_rate": 8000,
                }
            )
            start = time.time()
            segmenter.segment_audio(path, "./", output_audio=False)
            end = time.time()
            print(f"Took {end - start:}s to run")
            os.remove(os.path.join(os.path.abspath("./"), "segments.json"))
            print()

    print("Captions on")
    for aggression in [1, 2, 3]:
        for squash in [2000, 4000, 8000]:
            print(f"Agrression: {aggression}, Squash Rate: {squash}")
            segmenter = Segmenter(
                **{
                    "frame_duration_ms": 30,
                    "buffer_length_ms": 1200,
                    "threshold_silence_ms": 30,
                    "threshold_voice_ms": 120,
                    "aggression": 2,
                    "squash_rate": 8000,
                }
            )
            start = time.time()
            segmenter.enable_captioning(
                caption_threshold_ms=10,
                min_caption_len_ms=5000,
                max_caption_len_ms=100000,
                target_caption_len_ms=30000,
            )
            segmenter.segment_audio(path, "./", output_audio=False)
            end = time.time()
            print(f"Took {end - start:}s to run")
            os.remove(os.path.join(os.path.abspath("./"), "segments.json"))
            print()


def get_voiced_segments(path, directory):
    segmenter = Segmenter(
        **{
            "frame_duration_ms": 30,
            "buffer_length_ms": 1200,
            "threshold_silence_ms": 30,
            "threshold_voice_ms": 120,
            "aggression": 2,
            "squash_rate": 8000,
        }
    )
    if not directory:
        raise ValueError("must provide a directory")
    directory = os.path.join(os.path.abspath("./"), directory)
    os.makedirs(directory, exist_ok=True)
    segmenter.segment_audio(path, directory)


def caption(path, directory):
    segmenter = Segmenter(
        **{
            "frame_duration_ms": 30,
            "buffer_length_ms": 1200,
            "threshold_silence_ms": 30,
            "threshold_voice_ms": 120,
            "aggression": 2,
            "squash_rate": 4000,
        }
    )
    segmenter.enable_captioning(
        caption_threshold_ms=10,
        min_caption_len_ms=5000,
        max_caption_len_ms=20000,
        target_caption_len_ms=30000,
    )
    if directory:
        output_audio = True
    else:
        directory = "./"
        output_audio = False
    directory = os.path.join(os.path.abspath("./"), directory)
    os.makedirs(directory, exist_ok=True)
    segmenter.segment_audio(path, output_dir=directory, output_audio=output_audio)


def main():
    args = sys.argv
    _ = args.pop(0)
    action = args.pop(0)
    path = args.pop(0)
    try:
        directory = args.pop(0)
    except IndexError:
        directory = None
    print(action, path, directory)
    if action == "profile":
        profile(path)
    if action == "get_voiced_segments":
        get_voiced_segments(path, directory)
    if action == "caption":
        caption(path, directory)


if __name__ == "__main__":
    main()
