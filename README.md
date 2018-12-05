

# wahi-korero
This is a tool for identifying and extracting segments of speech in audio.

The name comes from wāhi, which means "to split" or "to subdivide", and kōrero, meaning "speech".

## Set Up

You will need `ffmpeg` to use `wahi_korero`. When it has been installed, use `pip3 install -r requirements.txt` to get the Python dependencies.

Since `koreromaori.io` runs on Python 2, this project aims to be backwards compatible with Python 2.7. If you are using Python 2.7, install the Python dependencies with `pip install -r requirements.txt`.

## Command Line
The command-line segmenter can be run like so: `python3 cmdseg sounds/hello.wav -o out`. This will segment the file at `sounds/hello.wav`, producing a `segments.json` file and an audio file for each segment and saving them to the folder called `out`. If you omit `-o out`, nothing will be saved and the JSON will be printed to `stdout`.

You can configure how the segmenter should run from the command-line. Run `python3 cmdseg -h` and see the section below, entitled "Configuring Your Own Segmenter", for more information

## Python API
The code below will segment `myfile.wav`, saving the output to the `out` folder. If you specify the optional `output_audio` flag, each segment will be saved to its own `.wav` file. There will also be a `segments.json` containing information about the segments.

```Python
import wahi_korero
segmenter = wahi_korero.default_segmenter()
segmenter.segment_audio("myfile.wav", "out", output_audio=True)
```

If you want to use the segments inside the program without saving to a file, use `segment_stream`. It returns a generator that yields successive segments in the audio, represented as a tuple `(start, end)`.

```Python
import wahi_korero
segmenter = wahi_korero.default_segmenter()
stream = segmenter.segment_stream("myfile.wav", output_audio=True)
for seg, audio in stream:
    start, end = seg
    do_stuff(start, end, audio)
```

If you specify `output_audio=False`, the stream will always return an `audio` of `None`. This saves a bit of computational overhead, if all you care about is where the segments are located.

## Configuring Your Own Segmenter
You can make your own segmenters with custom parameters like below:
```Python3
from wahi_korero import Segmenter
segmenter = Segmenter(
   frame_duration_ms = 10,
   threshold_silence_ms = 50,
   threshold_voice_ms = 150,
   buffer_length_ms = 200,
   aggression = 1,
   squash_rate = 400,
)
```
Another way of doing this is to specify the parameters in a `dict` and pass them to the function using the splat operator. This is nice if you want to switch between several sets of parameters.

```Python3
from wahi_korero import Segmenter
config = {
   "frame_duration_ms": 10,
   "threshold_silence_ms": 50,
   "threshold_voice_ms": 150,
   "buffer_length_ms": 200,
   "aggression": 1,
   "squash_rate": 400,
}
segmenter = Segmenter(**config)
```

Here is an explanation of the parameters:

* `frame_duration_ms`: the segmenter works by considering whether sequences of audio frames in the track are voiced or not. This is the length of a single frame in milliseconds. The value must be 10, 20, or 30.
* `buffer_length_ms`: the segmenter looks at this many frames at once. If enough of them are voiced, it starts gathering them into a segment. If it is in a segment and enough of the frames in the buffer are unvoiced, it stops gathering them and outputs the segment. The value must be a multiple of `frame_duration_ms`.
* `threshold_silence_ms`: when the segmenter is gathering frames into a segment and sees this many seconds of silence in the buffer, it will output the segment. The value must be a multiple of `frame_duration_ms` and less than `buffer_length_ms`.
* `threshold_voice_ms`: when the segmenter is not gathering frames and sees this many seconds of voice activity in the buffer, it will begin gathering frames into a segment. The value must be a multiple of `frame_duration_ms` and less than `buffer_length_ms`.
* `aggression`: the segmenter can perform some noise filtering. Possible values are 1 (least aggressive), 2, or 3 (most aggressive).
* `squash_rate`: the segmenter will transcode the audio to this sample rate before segmenting it. This can help minimise noises not in the frequency of human speech. Can be omitted.

## Captioning

`wahi_korero` has support for generating captions. This works by joining any segments that are close to each other, and splitting all sections of silence between neighbouring segments. This outputs segments which span the whole track.

The following code will perform captioning on a track, joining any segments within 100ms of each other, and saving the results to a specified `output_dir`.

```Python
from wahi_korero import default_segmenter
segmenter = default_segmenter()
segmenter.enable_captioning(caption_threshold_ms=100)
segmenter.segment_audio("myfile.wav", output_dir="where/to/save/files")
```

There is an optional `min_caption_len_ms` argument. If set, the segmenter will move left-to-right over the captions and greedily merge any which are shorter than `min_caption_len_ms`. Note in some edge cases you can still get captions shorter than the `min_caption_len_ms`. Here's an example of how to use it:

```Python
from wahi_korero import default_segmenter
segmenter = default_segmenter()
segmenter.enable_captioning(caption_threshold_ms=100, min_caption_len_ms=1000)
segmenter.segment_audio("myfile.wav", output_dir="where/to/save/files")
```

## Documentation

Documentation is generated with `Sphinx` and can be found in the `docs/build/html` folder. It can be viewed by opening `docs/build/html/index.html` in a web browser. See `docs/README.md` for information on how to rebuild the documentation.

## Test

There are a few integration tests in `test`. See `tests/README.md` for information.



