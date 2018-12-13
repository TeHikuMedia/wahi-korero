from __future__ import absolute_import, division, print_function

if hasattr(__builtins__, "raw_input"):
    input = raw_input

"""
Adapted from https://github.com/wiseman/py-webrtcvad/blob/master/example.py
"""

from collections import deque
from .exceptions import ConfigError, FormatError
import json
import wave
from os import path
from .utils import open_audio, _quadraphonic_to_mono
import webrtcvad

# Default parameters that you can use to create your own `Segmenter` objects.
DEFAULT_CONFIG = \
    {
        "frame_duration_ms": 10,
        "threshold_silence_ms": 30,
        "threshold_voice_ms": 270,
        "buffer_length_ms": 300,
        "aggression": 3,
        "squash_rate": 4000,
    }


def default_segmenter():
    """
    Returns a `Segmenter` which uses some default, hand-picked parameters.
    :return: `Segmenter`
    """
    return Segmenter(**DEFAULT_CONFIG)


class _Frame(object):
    """ Represents a single frame of audio data. """

    def __init__(self, timestamp, duration_s, wr, nf):
        self.bytes = wr.readframes(nf)
        self.timestamp = timestamp
        self.duration = duration_s

    def __str__(self):
        return "Frame(..., timestamp={}, duration={})".format(
            self.timestamp, self.duration)


def _frame_generator(frame_duration_ms, audio, overlap_ms=0):
    """
    Construct a generator which yields successive frames of an audio track.

    :param audio: an `AudioSegment`.
    :param overlap_ms: if set, frames will overlap.
    :return: a generator which yields `Frame` objects.
    """

    # NOTE: PCM audio is made up of a collection of what it calls frames, each of which contains one sample per
    # channel (where the size of a sample is `sample_width`). To avoid confusion, we call these `PCM frames`.

    if overlap_ms < 0 or overlap_ms >= frame_duration_ms:
        raise ValueError("Must have `0 <= overlap_ms < frame_duration_ms`, but have `0 <= {} < {}`."
                         .format(overlap_ms, frame_duration_ms))

    wave_reader = audio.get_wave_reader()

    total_frames = wave_reader.getnframes()
    frame_duration_s = frame_duration_ms / 1000.0
    step_duration_s = (frame_duration_ms - overlap_ms) / 1000.0

    timestamp = 0.0  # location in the PCM data, stepping in seconds
    num_frames = int(audio.frame_rate*frame_duration_ms/1000)
    fp = audio.get_file_path()
    frame_position = 0
    while frame_position <= total_frames:
        yield _Frame(timestamp, frame_duration_s, wave_reader, num_frames)
        timestamp = round(timestamp + step_duration_s, 3)
        frame_position = frame_position + num_frames + 1


def frame_stream(frame_duration_ms, audio_fpath, output_audio=False, overlap_ms=0):
    """
    Produces a generator which yields successive segments of a specified frame size.
    :param frame_duration_ms: the size of the frames (in ms).
    :param audio_fpath: location of the audio to segment.
    :param output_audio: whether or not the voiced segments should be extracted into separate `AudioSegment` \
        objects.
    :param overlap_ms: frames are allowed to overlap. If set, then the distance between the start of frames will be \
        `frame_duration_ms - overlap`. Otherwise there will be no overlap between frames.
    :return: a generator which yields pairs `(segment, audio)`. A segment is a tuple `(start, stop)`, where `start` \
        and `stop` are timestamps (in seconds) in the track. If `output_audio` is set, then `audio` will be a \
        `pydub.AudioSegment` containing the appropriate audio, extracted from the input track; otherwise, `audio` \
        will be `None`.
    """
    audio = open_audio(audio_fpath)
    fg = _frame_generator(frame_duration_ms, audio, overlap_ms=overlap_ms)
    for frame in fg:
        start = round(frame.timestamp, 3)
        end = round(frame.timestamp + frame.duration, 3)
        seg = start, end
        if output_audio:
            yield seg, audio[start * 1000: end * 1000]
        else:
            yield seg, None


def frame_audio(frame_duration_ms, audio_fpath, output_dir, output_audio=True, overlap_ms=0, verbose=True):
    """
    Segments an audio file into a number of fixed-width frames.

    :param frame_duration_ms: how long each frame should be.
    :param audio_fpath: location of the audio to segment.
    :param output_dir: directory where the segmented tracks and data should be output.
    :param output_audio: if set, each frame will be saved as a separate audio track.
    :param overlap_ms: if set, frames will overlap by this amount.
    :param verbose: if set, this function will print to stdout as it runs.
    :return: `None`
    """
    if type(output_dir) != str:
        raise TypeError("Output directory must be a `str`, but it's a `{}`".format(type(output_dir)))
    if not path.exists(output_dir):
        raise FileNotFoundError("Output directory `{}` doesn't exist.".format(output_dir))
    if not path.exists(audio_fpath):
        raise FileNotFoundError("Input file `{}` doesn't exist.".format(audio_fpath))
    if type(output_audio) is not bool:
        raise TypeError("`output_audio` flag must be a `bool`, but it's a `{}`".format(type(output_audio)))
    if type(verbose) is not bool:
        raise TypeError("`verbose` flag must be a `bool`, but it's a `{}`".format(type(verbose)))

    fs = frame_stream(frame_duration_ms, audio_fpath, output_audio=output_audio, overlap_ms=overlap_ms)

    seg_data = _SegData(audio_fpath)
    for i, (seg, audio) in enumerate(fs):
        additional_kvs = {}
        if output_audio:
            fname = "seg-%005d.wav" % i
            output_fpath = path.join(output_dir, fname)
            if verbose:
                print("Writing {}".format(output_fpath))
            audio.export(output_fpath, format="wav").close()  # export returns an open file handle
            additional_kvs["fname"] = fname
        start, end = seg
        seg_data.add(start, end, additional_kvs)

    seg_data.save_to_file(
        output_fpath=path.join(output_dir, "segments.json"),
        verbose=verbose,
    )


class _SegData(object):

    def __init__(self, fpath):
        self.duration_seconds = round(open_audio(fpath).duration_seconds, 3)  # round to ms
        self.num_segs = 0
        self.track_name = path.basename(fpath)
        self.segments = []
        self.kvs = {}

    def add(self, start, end, additional_kvs=None):
        if additional_kvs is None:
            additional_kvs = {}

        args = {"start": start, "end": end}
        for key in additional_kvs.keys():
            args[key] = additional_kvs[key]

        self.segments.append(args)
        self.num_segs += 1

    def save_to_file(self, output_fpath, verbose=True):
        with open(output_fpath, "w+") as json_file:
            if verbose:
                print("Writing {}".format(output_fpath))
            data = self.to_json()
            json_file.write(json.dumps(data, indent=2))  # pretty prints to the JSON file; might be inefficient

    def to_json(self):
        return {
            "track_duration": self.duration_seconds,
            "num_segments": self.num_segs,
            "track_name": self.track_name,
            "segments": self.segments,
        }

    def __str__(self):
        return self.to_json().__str__()

    def __repr__(self):
        return self.to_json().__repr__()


class Segmenter(object):
    """
    A `Segmenter` is used to extract segments of voiced speech from an audio track. It uses a sliding-buffer algorithm,
    deciding whether or not a section of audio is a segment based on the proportion of voiced frames in the buffer.

    The following parameters can be configured:
        - `frame_duration_ms`: the segmenter works by considering whether sequences of audio frames in the track are \
            voiced or not. This is the length of a single frame in milliseconds. The value must be 10, 20, or 30.
        - `buffer_length_ms`: the segmenter looks at this many frames at once. If enough of them are voiced, it starts \
            gathering them into a segment. If it gathering frames and enough of the frames in the buffer are unvoiced, \
            it outputs the frames gathered into a segment. The value must be a multiple of `frame_duration_ms`.
        - `threshold_silence_ms`: when the segmenter is gathering frames into a segment and sees this many seconds of \
            silence in the buffer, it will output the segment. The value must be a multiple of `frame_duration_ms` and \
            less than `buffer_length_ms`.
        - `threshold_voice_ms`: when the segmenter is not gathering frames and sees this many seconds of voice \
            activity in the buffer, it will begin gathering frames into a segment. The value must be a multiple of \
            `frame_duration_ms` and less than `buffer_length_ms`.
        - `aggression`: the segmenter can perform some noise filtering. Possible values are 1 (least aggressive), 2, \
            or 3 (most aggressive).
        - `squash_rate`: the segmenter will transcode the audio to this sample rate before segmenting it. This can \
            help minimise noises not in the frequency of human speech. Can be omitted.
    """

    def __init__(self, frame_duration_ms, threshold_silence_ms, threshold_voice_ms, buffer_length_ms, aggression=1,
                 squash_rate=None, caption_threshold=None, min_caption_len_ms=None):

        self.frame_duration_ms = frame_duration_ms
        self.threshold_silence_ms = threshold_silence_ms
        self.threshold_voice_ms = threshold_voice_ms
        self.buffer_length_ms = buffer_length_ms
        self.aggression = aggression
        self.squash_rate = squash_rate
        self.caption_threshold = caption_threshold
        self.min_caption_len_ms = min_caption_len_ms
        self._check_parameters()

    def _check_parameters(self):
        """
        Check whether the parameters of this Segmenter are valid.
        :return: None
        :raise ConfigError: if the parameters are invalid.
        """

        if self.buffer_length_ms % self.frame_duration_ms != 0:
            raise ConfigError("PADDING_DURATION_MS ({}) must be a multiple of frame_duration_ms ({})"
                              .format(self.buffer_length_ms, self.frame_duration_ms))
        if self.threshold_voice_ms % self.frame_duration_ms != 0:
            raise ConfigError("THRESHOLD_DURATION_MS ({}) must be a multiplier of frame_duration_ms ({})"
                              .format(self.threshold_voice_ms, self.frame_duration_ms))
        if self.threshold_silence_ms % self.frame_duration_ms != 0:
            raise ConfigError("threshold_silence_ms ({}) must be a multiple of frame_duration_ms ({})"
                              .format(self.threshold_silence_ms, self.frame_duration_ms))
        if self.threshold_silence_ms > self.buffer_length_ms:
            raise ConfigError("threshold_silence_ms ({}) must not be larger than buffer_length_ms ({})"
                              .format(self.threshold_silence_ms, self.buffer_length_ms))
        if self.threshold_voice_ms > self.buffer_length_ms:
            raise ConfigError("threshold_voice_ms ({}) must not be larger than buffer_length_ms ({})"
                              .format(self.threshold_voice_ms, self.buffer_length_ms))
        if self.min_caption_len_ms and not self.caption_threshold:
            raise ConfigError("min_caption_len_ms is set, but caption_threshold is not.")

    def _preprocess_audio(self, audio):
        """
        Process an `AudioSegment`, obtaining a new `AudioSegment` guaranteed to have 1 channel (mono), a sample width \
        of 2, and a sample rate of 8000Hz, 16000Hz, or 32000Hz.

        The optional `desired_sample_rate` doesn't have to be one of these three values; if you pass in something \
        different, the track will be converted to that sample rate, and then converted up to the nearest sample rate \
        in 8/16/32kHz. If you leave it as `None`, the track will simply convert down to the nearest sample.

        :param audio: the `AudioSegment` to process.
        :return: the processed `AudioSegment`.
        :raise FormatError: if the audio can't be transcoded to the appropriate format.
        """

        # First turn audio into valid wav pcm
        audio.set_format(
            ['-acodec', 'pcm_s16le', '-ac', '1', "-f", "wav"], ext='wav')

        valid_sample_rates = (32000, 16000, 8000)

        if self.squash_rate is not None:
            audio.set_frame_rate(self.squash_rate)
            new_fr = next(fr for fr in reversed(valid_sample_rates) if fr >= audio.frame_rate)
            audio.set_frame_rate(new_fr)
        else:
            if audio.frame_rate < 8000:
                raise FormatError("Frame rate `{}` is too low; I don't know what to do. If you want to preprocess this"
                                  "track, try passing in a `desired_sample_rate`.".format(audio.frame_rate))
            new_fr = next(fr for fr in valid_sample_rates if fr < audio.frame_rate)
            audio.set_frame_rate(new_fr)

        return audio

    def _vad_collector(self, sample_rate, vad, frames):
        """
        Construct a generator which will yield segments of voiced audio using a webrtcvad voice-activity detector.

        Uses a sliding window algorithm on a ring buffer of audio frames. When enough voiced frames are in the buffer, \
        we begin gathering frames into a segment. We end the segment when we see enough unvoiced frames in the buffer.

        :param sample_rate: the sample rate of the audio being segmented.
        :param vad: a webrtcvad voice-activity detector.
        :param frames: a generator which yields successive frames of the audio.
        :return: a generator that yields `Segment` objects.
        """

        # Figure out length of the buffer in frames. The start/end will be padded with a buffer length's worth of
        # frames, to help detection of voices at the start/end.
        buffer_len = int(self.buffer_length_ms / self.frame_duration_ms)
        buffer = deque(maxlen=buffer_len)

        # We stop/start collecting frames into a segment depending on how much of the buffer is voiced. The precise
        # amount is specified in milliseconds by the user when creating the Segmenter. Figure out how it is in frames.
        threshold_silence = int(self.threshold_silence_ms / self.frame_duration_ms)
        threshold_voice = int(self.threshold_voice_ms / self.frame_duration_ms)

        # Track whether or not we are currently gathering frames into a segment.
        collecting_voiced_frames = False

        # Holds the frames being gathered into a segment.
        voiced_frames = []

        for i, frame in enumerate(frames):

            # `is_speech` does a non-backwards compatible division operation, but casts it to `int` which makes it
            # compatible. See: https://github.com/wiseman/py-webrtcvad/blob/master/webrtcvad.py
            is_speech = vad.is_speech(frame.bytes, sample_rate)

            # Add frame to the buffer. If enough of the frames are voiced, start collecting frames into a segmenter. Any
            # frames currently in the buffer are part of this new segment.
            if not collecting_voiced_frames:
                buffer.append((frame, is_speech))
                num_voiced = len([f for f, spoken in buffer if spoken])
                if num_voiced > threshold_voice:
                    collecting_voiced_frames = True
                    for f, _ in buffer:
                        voiced_frames.append(f)
                    buffer.clear()
            # If enough of the buffer is unvoiced, we've reached the end of this segment. Yield the data we've gathered
            # so far and reset the above variables.
            else:
                voiced_frames.append(frame)
                buffer.append((frame, is_speech))
                num_unvoiced = len([f for f, spoken in buffer if not spoken])
                if num_unvoiced > threshold_silence:
                    collecting_voiced_frames = False
                    yield voiced_frames[0].timestamp, voiced_frames[-1].timestamp
                    buffer.clear()
                    voiced_frames = []

        # If we have any leftover voiced audio when we run out of input, yield it.
        if voiced_frames:
            yield voiced_frames[0].timestamp, voiced_frames[-1].timestamp

    def segment_stream(self, audio_fpath, output_audio=False):
        """
        Create a generator which segments the audio at `audio_fpath`, yielding successive segments.

        :param audio_fpath: location of the audio to segment.
        :param output_audio: whether or not the voiced segments should be extracted into separate `AudioSegment`
            objects.
        :return: a generator which yields pairs `(segment, audio)`. A segment is a tuple `(start, stop)`, where `start`
            and `stop` are timestamps (in seconds) in the track. If `output_audio` is set, then `audio` will be a
            `pydub.AudioSegment` containing the appropriate audio, extracted from the input track; otherwise, `audio`
            will be `None`.
        :raise ConfigError: if invalid parameters have been specified for the `Segmenter`.
        :raise FileNotFoundError: if `audio_fpath` doesn't exist.
        :raise FormatError: if the format of the file at `audio_fpath` isn't supported.
        :raise TypeError: if arguments of the wrong type have been passed to this function.
        """

        # Preprocess the audio so we can send it to VAD. This usually tarnishes the quality, so keep the original
        # around so at the end we can extract the segments from it and retain their quality.
        og_audio = open_audio(audio_fpath)
        audio = self._preprocess_audio(og_audio)

        # Set up the VAD, frame generator, and segment generator. Wrap with captioning, if that option has been set.
        frames = _frame_generator(self.frame_duration_ms, audio)
        vad = webrtcvad.Vad(self.aggression)
        segments = self._vad_collector(audio.frame_rate, vad, frames)
        if self.caption_threshold is not None:
            segments = self._caption_generator(segments, audio.duration_milliseconds)
            if self.min_caption_len_ms is not None:
                segments = self._caption_merger(segments)

        for segment in segments:
            if not output_audio:
                yield segment, None
            else:
                yield segment, og_audio[segment[0] * 1000: segment[1] * 1000]

    def segment_audio(self, audio_fpath, output_dir, output_audio=True, verbose=True):
        """
        Segments the audio at the given filepath.

        :param audio_fpath: location of the audio to segment.
        :param output_dir: directory where the segmentation tracks and data should be output.
        :param output_audio: if set, the segments will be extracted from the audio and saved separately.
        :param verbose: if set, this function will print to stdout.
        :return: `None`
        :raise ConfigError: if invalid parameters have been specified for the `Segmenter`.
        :raise FileNotFoundError: if `audio_fpath` or `output_dir` don't exist.
        :raise FormatError: if the format of the file at `audio_fpath` isn't supported.
        :raise TypeError: if arguments of the wrong type have been passed to this function.
        """
        if type(output_dir) != str:
            raise TypeError("Output directory must be a `str`, but it's a `{}`".format(type(output_dir)))
        if not path.exists(output_dir):
            raise FileNotFoundError("Output directory `{}` doesn't exist.".format(output_dir))
        if not path.exists(audio_fpath):
            raise FileNotFoundError("Input file `{}` doesn't exist.".format(audio_fpath))
        if type(output_audio) is not bool:
            raise TypeError("`output_audio` flag must be a `bool`, but it's a `{}`".format(type(output_audio)))
        if type(verbose) is not bool:
            raise TypeError("`verbose` flag must be a `bool`, but it's a `{}`".format(type(verbose)))

        stream = self.segment_stream(audio_fpath, output_audio)

        seg_data = _SegData(audio_fpath)
        for i, (seg, audio) in enumerate(stream):
            additional_kvs = {}
            if output_audio:
                fname = "seg-%005d.wav" % i
                output_fpath = path.join(output_dir, fname)
                if verbose:
                    print("Writing {}".format(output_fpath))
                audio.export(output_fpath, format="wav").close()  # export returns an open file handle
                additional_kvs["fname"] = fname
            start, end = seg
            seg_data.add(start, end, additional_kvs)

        seg_data.save_to_file(
            output_fpath=path.join(output_dir, "segments.json"),
            verbose=verbose,
        )

    def _caption_generator(self, segment_stream, track_length_ms):

        if self.caption_threshold is None:
            raise ValueError("Trying to call _caption_generator, but Segmenter doesn't have captioning enabled.")

        threshold = self.caption_threshold / 1000  # convert to seconds
        caption = 0, next(segment_stream)[1]

        # Repeatedly merge segments until we don't hit the threshold and are over the min_len.
        for seg in segment_stream:
            distance = seg[0] - caption[1]
            if distance < threshold:
                caption = caption[0], seg[1]
            else:
                half_distance = float(distance) / 2  # half goes to previous segment, half to next
                caption = caption[0], caption[1] + half_distance
                yield caption
                caption = seg[0] - half_distance, seg[1]

        # Any silence at the end goes into the last caption.
        caption = caption[0], track_length_ms / 1000
        yield caption

    def _caption_merger(self, caption_gen):

        if self.min_caption_len_ms is None:
            raise ValueError("Trying to call _caption_merger, but Segmenter doesn't have `min_caption_len_ms` set.")

        min_len = self.min_caption_len_ms / 1000  # convert to seconds
        caption = next(caption_gen)

        for caption2 in caption_gen:
            if caption[1] - caption[0] >= min_len:
                yield caption
                caption = caption2
            else:
                caption = caption[0], caption2[1]

        yield caption

    def enable_captioning(self, caption_threshold_ms, min_caption_len_ms=None):
        """
        Enable captioning on this `Segmenter`. After segmenting a track, it will merge segments within
        `caption_threshold_ms` of each other. Any silence is distributed between the segments on either side.

        :param caption_threshold_ms: segments within this many milliseconds of each other are merged.
        :param min_caption_len_ms: optional argument. If set, an attempt wil be made to greedily merge captions shorter
            than this amount.
        :raise ConfigError: if invalid arguments have been specified.
        :raise TypeError: if arguments of the wrong type are passed to this function.
        """
        if type(caption_threshold_ms) is not int:
            raise TypeError("`enable_captioning` must be called with `caption_threshold_ms` as an `int`, but it was"
                            " called with a `{}`".format(type(caption_threshold_ms)))
        if type(min_caption_len_ms) not in [int, type(None)]:
            raise TypeError("`enable_captioning` must be called with `min_caption_len_ms` as an `int`, but it was"
                            " called with a `{}`".format(type(min_caption_len_ms)))
        if caption_threshold_ms < 0:
            raise ConfigError("`enable_captioning` must be called with `caption_threshold_ms` >= 0, but it is `{}`"
                              .format(caption_threshold_ms))
        if min_caption_len_ms is not None and min_caption_len_ms < 0:
            raise ConfigError("`enable_captioning` must be called with `min_caption_len_ms` as an `int`, but it is `{}`"
                              .format(min_caption_len_ms))
        self.caption_threshold = float(caption_threshold_ms)
        self.min_caption_len_ms = float(min_caption_len_ms) if min_caption_len_ms is not None else None

    def disable_captioning(self):
        """ Disables captioning on this segmenter. Captioning can be turned on with `enable_captioning`. """
        self.caption_threshold = None
