# ffplaylist
Streaming dynamic playlist simply using FFMpeg.

For example, you have a directory containing audio files. You want to stream it to some server.

    python3 random_files.py 'music/*.m4a' | python3 ffplaylist.py -vv -p -- -vn -c:a copy -content_type audio/aac -password hackme icecast://10.0.0.2:9000/music.mp3

```
usage: ffplaylist.py [-h] [-e FFMPEG] [-v] [-p] ...

FFMpeg dynamic playlist input. Feed stdin with your list of media files.

positional arguments:
  args                  ffmpeg output arguments

optional arguments:
  -h, --help            show this help message and exit
  -e FFMPEG, --ffmpeg FFMPEG
                        ffmpeg/avconv executable, can be set using FFMPEG
                        environment variable
  -v, --verbose         verbosity level. -v prints filename, -vv shows ffmpeg
                        output.
  -p, --progress        show progress bar.
```


