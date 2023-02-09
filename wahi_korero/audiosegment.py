'''
This is a quick fix/swap out of pydub's audio segment because it loads entire
files into memory which is bad. This class doesn't do that, but does get
useful audio file attributes and provides a way to read bytes from audio
as required rather than loading up the whole thing.

https://github.com/jiaaro/pydub/blob/master/pydub/audio_segment.py

'''
import array
import subprocess
import os
import tempfile
import wave
import errno
from ffmpeg import FFmpeg, Progress
from pydub import AudioSegment
from tempfile import NamedTemporaryFile


class MyAudioSegment():

    def __init__(self, file_path, file_handle=None, **kwargs):
        self.file_path = file_path
        self.use_tmp = False
        self.tmp_file = None
        self.tmp_dir = None
        self.base_name = os.path.basename(self.file_path)
        self.wave_reader = None
        self.set_durations()
        self.set_channels()
        self.set_frame_rate()
        self.file_size = os.path.getsize(self.file_path)
        self.samples = self.duration_seconds * self.frame_rate * self.channels
        self.sample_width = self.file_size // self.samples
        self.frame_width = self.channels * self.sample_width
        self.file_handle = file_handle

    def __del__(self):
        if self.wave_reader:
            self.wave_reader.close()
        if self.file_handle:
            self.file_handle.close()
        try:
            os.remove(self.tmp_file)
            try:
                os.rmdir(self.tmp_dir)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise e
        except:
            pass

    def __len__(self):
        """
        returns the length of this audio segment in milliseconds
        """
        return round(self.duration_milliseconds)

    def __iter__(self):
        return (self[i] for i in xrange(len(self)))

    def __getitem__(self, millisecond):
        if isinstance(millisecond, slice):
            if millisecond.step:
                return (
                    self[i:i + millisecond.step]
                    for i in xrange(*millisecond.indices(len(self)))
                )

            start = millisecond.start if millisecond.start is not None else 0
            end = millisecond.stop if millisecond.stop is not None \
                else len(self)

            start = min(start, len(self))
            end = min(end, len(self))
        else:
            start = millisecond
            end = millisecond + 1

        in_file = self.file_path
        print(self.file_path, self.tmp_file)
        print(in_file)
        ffmpeg = (
            FFmpeg()
            .option('y')
            .input(in_file)
            .output(
                "pipe:1",
                {"codec:a": "copy",
                 "ss": f"{start}ms",
                 "to": f"{end}ms",
                 },
                vn=None,
                f=self.get_extension(),
            )
        )

        @ffmpeg.on("start")
        def on_start(arguments: list[str]):
            print("arguments:", arguments)

        data = ffmpeg.execute()

        file_object = NamedTemporaryFile('wb', suffix=self.get_extension())
        file_object.write(data)
        segment = self.__class__(file_object.name, file_handle=file_object)

        # ensure the output is as long as the requester is expecting
        expected_length = end - start
        missing = round(expected_length - segment.duration_milliseconds)
        if missing:
            print(expected_length, segment.duration_milliseconds)
            print(missing)
            if abs(missing) > 100:
                raise Exception(
                    f"{missing} ms - you should never be filling in more than 10 ms with silence"
                )
            if 0 < missing <= 100:
                ffmpeg = (
                    FFmpeg()
                    .option('y')
                    .input(in_file)
                    .output(
                        "pipe:1",
                        {

                            "ss": f"{start}ms",
                            "to": f"{end}ms",
                            "af": f"areverse,apad=pad_dur={missing}ms,areverse",
                        },
                        vn=None,
                        f=self.get_extension(),
                    )
                )

                @ffmpeg.on("start")
                def on_start(arguments: list[str]):
                    print("arguments:", arguments)
                data = ffmpeg.execute()
                del segment
                file_object = NamedTemporaryFile(
                    'wb', suffix=self.get_extension())
                file_object.write(data)
                segment = self.__class__(
                    file_object.name, file_handle=file_object)

        return segment

    def from_file(file_path, format=None):
        return MyAudioSegment(file_path)

    def get_base_name(self):
        return os.path.basename(self.get_file_path())

    def get_file_path(self):
        if not self.use_tmp:
            return self.file_path
        else:
            return self.tmp_file

    def get_duration_seconds(self):
        return self.duration_se

    def set_durations(self):

        p = subprocess.Popen(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             self.get_file_path()],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        output, errors = p.communicate()

        self.duration_seconds = float(output)
        self.duration_milliseconds = float(output)*1000.0

        if self.duration_milliseconds == 0:
            raise Error('No sound in file.')

    def set_channels(self, channels=None):
        if not channels:
            command = [
                'ffprobe',  '-show_entries', 'stream=channels',
                '-select_streams', 'a', '-of', 'compact=p=0:nk=1', '-v', '0',
                self.get_file_path()]

            p = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)

            output, errors = p.communicate()
            self.channels = int(output)
        else:
            # Convert audio to new channel amount
            tmp_dir = tempfile.mkdtemp()
            tmp_file = os.path.join(tmp_dir, self.get_base_name())

            try:
                ffmpeg_cmd = ["ffmpeg",
                              "-y",  # overwrite output files without asking
                              "-i", self.get_file_path(),
                              "-ac", str(channels),  # 1 channel
                              tmp_file]

                # Redirect stdout and stderr to DEVNULL to silence output. Do explicitly for Python 2 compatibility.
                with open(os.devnull, "w") as DEVNULL:
                    subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)
            finally:

                if self.use_tmp:
                    # Delete old tmp file
                    os.remove(self.tmp_file)
                    try:
                        os.rmdir(self.tmp_dir)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise e

                self.tmp_file = tmp_file
                self.tmp_dir = tmp_dir
                self.use_tmp = True
                self.channels = channels
                self.update_derived()

        if self.channels == 0:
            raise Error('No channels found in audio.')

    def update_derived(self):
        if self.use_tmp:
            self.file_size = os.path.getsize(self.tmp_file)
        else:
            self.file_size = os.path.getsize(self.file_path)

        self.samples = self.duration_seconds * self.frame_rate * self.channels
        self.sample_width = self.file_size // self.samples
        self.frame_width = self.channels * self.sample_width

    def set_frame_rate(self, rate=None):
        if not rate:
            command = [
                'ffprobe',  '-show_entries', 'stream=sample_rate',
                '-select_streams', 'a', '-of', 'compact=p=0:nk=1', '-v', '0',
                self.get_file_path()]
            p = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            output, errors = p.communicate()
            self.frame_rate = int(output)
        else:
            # Convert audio to new frame rate
            tmp_dir = tempfile.mkdtemp()
            tmp_file = os.path.join(tmp_dir, self.get_base_name())

            try:
                ffmpeg_cmd = ["ffmpeg",
                              "-y",  # overwrite output files without asking
                              "-i", self.get_file_path(),
                              "-ar", str(rate),
                              tmp_file]
                # Redirect stdout and stderr to DEVNULL to silence output.
                # Do explicitly for Python 2 compatibility.
                with open(os.devnull, "w") as DEVNULL:
                    subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)
            finally:

                if self.use_tmp:
                    # Delete old tmp file
                    os.remove(self.tmp_file)
                    try:
                        os.rmdir(self.tmp_dir)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise e

                self.tmp_file = tmp_file
                self.tmp_dir = tmp_dir
                self.use_tmp = True
                self.frame_rate = rate
                self.update_derived()

    def set_format(self, format, ext=None):
        # Convert audio to new format

        if ext:
            base_name, _ = os.path.splitext(self.get_base_name())
            base_name = base_name + '.' + ext
        else:
            base_name = self.self.get_base_name()

        tmp_dir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_dir, base_name)

        try:
            ffmpeg_cmd = ["ffmpeg",
                          "-y",  # overwrite output files without asking
                          "-i", self.get_file_path()] + format + [tmp_file]

            # Redirect stdout and stderr to DEVNULL to silence output. Do explicitly for Python 2 compatibility.
            with open(os.devnull, "w") as DEVNULL:
                subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)
        finally:

            if self.use_tmp:
                # Delete old tmp file
                os.remove(self.tmp_file)
                try:
                    os.rmdir(self.tmp_dir)
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise e

            self.tmp_file = tmp_file
            self.tmp_dir = tmp_dir
            self.use_tmp = True
            self.update_derived()

    def close(self):
        self.__del__()

    def export(self, destination, format='wav'):
        '''
        Export the audio file from one format to another.
        This uses ffmpeg and *should* work with any input file
        :param destination: (required) path to save file to
        :param format: (default=wave) format to convert audio to
        :result destination of exported file
        '''

        # Ensure destination has proper extension
        dest, ext = os.path.splitext(destination)
        ext = ext.lstrip(".")  # Get rid of leading dot

        if format == 'wav':
            if ext != 'wav':
                destination = dest + '.wav'

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", self.file_path,
            "-f", "wav",
            destination
        ]

        with open(os.devnull, "w") as DEVNULL:
            subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)

        # then this just works?
        return self

    def get_wave_reader(self):
        '''Return a wave_reader. This is useful for webrtcvad. We
        should check that we actually have a wave file before doing this?
        '''

        if not self.wave_reader:
            self.wave_reader = wave.open(self.get_file_path(), 'rb')
        return self.wave_reader

    def frame_count(self, ms=None):
        """
        returns the number of frames for the given number of milliseconds, or
            if not specified, the number of frames in the whole AudioSegment
        """
        if ms is not None:
            return ms * (self.frame_rate / 1000.0)
        else:
            return float(self.file_size // self.frame_width)

    def _parse_position(self, val):
        if val < 0:
            val = len(self) - abs(val)
        val = self.frame_count(ms=len(self)) if val == float("inf") else \
            self.frame_count(ms=val)
        return int(val)

    def _spawn(self, data, overrides={}):
        """
        Creates a new audio segment using the metadata from the current one
        and the data passed in. Should be used whenever an AudioSegment is
        being returned by an operation that would alters the current one,
        since AudioSegment objects are immutable.
        """
        # accept lists of data chunks
        if isinstance(data, list):
            data = b''.join(data)

        if isinstance(data, array.array):
            try:
                data = data.tobytes()
            except:
                data = data.tostring()

        # accept file-like objects
        if hasattr(data, 'read'):
            if hasattr(data, 'seek'):
                data.seek(0)
            data = data.read()

        metadata = {
            'sample_width': self.sample_width,
            'frame_rate': self.frame_rate,
            'frame_width': self.frame_width,
            'channels': self.channels
        }
        metadata.update(overrides)
        return AudioSegment(data=data, metadata=metadata)

    def get_extension(self):
        in_file = self.tmp_file if self.use_tmp else self.file_path
        _, ext = os.path.splitext(in_file)
        return ext.lstrip(".")
