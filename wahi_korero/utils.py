
from .exceptions import FormatError
import os
from os import path
from .audiosegment import MyAudioSegment as AudioSegment
import subprocess
import tempfile

# The segmenter is capable of loading these formats. We could probably support more, it depends on ffmpeg.
SUPPORTED_FORMATS = [
    "flv", "mp3", "ogg", "wav", "m4a", "mp4", "aac", "flac", "aiff",
    "wma"
]


def _quadraphonic_to_mono(audio):
    """
    Converts the given quadraphonic audio track to a mono track.
    :param audio: a quadraphonic AudioSegment.
    :return: a mono AudioSegment.
    """

    # We're going to export to `fpath_in` then use ffmpeg directly to transcode to `fpath_out`.
    fd_in, fpath_in = tempfile.mkstemp()
    fd_out, fpath_out = tempfile.mkstemp()

    try:
        audio.export(fpath_in, format="wav")
        ffmpeg_cmd = ["ffmpeg",
                      "-y",  # overwrite output files without asking
                      "-i", fpath_in,
                      "-ac", "1",  # 1 channel
                      "-acodec", "pcm_s16le",  # use PCM width a sample width of 16 bits = 2 bytes
                      "-f", "wav",  # use wav format specifically
                      fpath_out]

        # Redirect stdout and stderr to DEVNULL to silence output. Do explicitly for Python 2 compatibility.
        with open(os.devnull, "w") as DEVNULL:
            subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)
        return AudioSegment.from_file(fpath_out, format="wav")
    finally:
        os.remove(fpath_in)
        os.remove(fpath_out)


def is_format_supported(ext):
    """
    Check if the format is supported by wahi-korero.

    :param ext: a string. For example, "mp3" or ".mp3".
    :return: bool
    """
    return ext.lstrip(".").lower() in SUPPORTED_FORMATS


def open_audio(fpath):
    """
    Open the file located at `fpath` as an `AudioSegment`.

    :param fpath:
    :return: an `AudioSegment` object.
    :raises FormatError: if the file is in an unrecognisable format.
    """

    _, ext = path.splitext(fpath)  # Determine file type from extension.
    ext = ext.lstrip(".")  # Get rid of leading dot
    if ext not in SUPPORTED_FORMATS:
        raise FormatError("File format {} not supported".format(ext))
    audio_segment = AudioSegment(fpath)
    return audio_segment
