'''
This is a quick fix/swap out of pydub's audio segment because it loads entire
files into memory which is bad. This class doesn't do that, but does get
useful audio file attributes and provides a way to read bytes from audio
as required rather than loading up the whole thing.

'''
import subprocess
import os
import tempfile
import wave
import errno


class MyAudioSegment():

    def __init__(self, file_path, **kwargs):
        self.file_path = file_path
        self.use_tmp = False
        self.tmp_file = None
        self.tmp_dir = None
        self.base_name = os.path.basename(self.file_path)
        self.wave_reader = None
        self.set_durations()
        self.set_channels()
        self.set_frame_rate()
        self.sample_width = 2

    def __del__(self):
        try:
            os.remove(self.tmp_file)
            try:
                os.rmdir(self.tmp_dir)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise e

        except:
            pass

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
        print(output)
        self.duration_seconds = float(output)
        self.duration_milliseconds = float(output)*1000.0

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
            print(output)
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

                print(ffmpeg_cmd)
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

    def set_frame_rate(self, rate=None):
        if not rate:
            command = [
                'ffprobe',  '-show_entries', 'stream=sample_rate',
                '-select_streams', 'a', '-of', 'compact=p=0:nk=1', '-v', '0',
                self.get_file_path()]
            p = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            print(command)
            output, errors = p.communicate()
            print(output)
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
                print(ffmpeg_cmd)
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

            print(ffmpeg_cmd)
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

    def export(self, destination, format='wav'):
        '''
        Export the audio file from one format to another.
        This uses ffmpeg and *should* work with any input file
        :param destination: (required) path to save file to
        :param format: (default=wave) format to convert audio to
        :result destination of exported file
        '''

        # Ensure desitnation has proper extention
        dest, ext = os.path.splitext(destination)
        ext = ext.lstrip(".")  # Get rid of leading dot

        if fmt is 'wav':
            if ext is not 'wav':
                desitnation = dest + '.wav'

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", self.fpath,
            "-f", "wav",
            destination
        ]

        with open(os.devnull, "w") as DEVNULL:
            subprocess.call(ffmpeg_cmd, stdout=DEVNULL, stderr=DEVNULL)

        # then this just works?
        return destination

    def get_wave_reader(self):
        '''Return a wave_reader. This is usefule for webrtcvad. We
        should check that we actually have a wave file before doing this?
        '''

        if not self.wave_reader:
            self.wave_reader = wave.open(self.get_file_path(), 'rb')
        return self.wave_reader
