#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import signal
import shutil
import argparse
import tempfile
import threading
import subprocess
import collections

import psutil

# status:
# a->b  b->(c)
# ^     ^
# playing: a

class FFMpegManager:
    def __init__(self, args, ffmpeg=None, verbose=1, progressbar=False):
        self.args = args
        self.ffmpeg = ffmpeg or os.environ.get('FFMPEG', 'ffmpeg')
        self.verbose = verbose
        self.progressbar = progressbar
        self.proc = None
        self.procinfo = None
        self.tmpdir = tempfile.mkdtemp(prefix='ffpl-')
        self.stop = threading.Event()

        self.plq = collections.deque()
        self.cond = threading.Condition()

        self.current = None
        self.currentfd = None
        self.progress = None
        self.progress_barlen = 48
        self.nextpl = None

    def check_progress(self):
        if self.proc is None:
            return
        filename = newprogress = None
        while self.plq:
            filename, symlfn, plname = self.plq[0]
            fd = None
            try:
                openfiles = self.procinfo.open_files()
            except psutil.AccessDenied:
                self.exit()
                return
            for openfile in openfiles:
                if openfile.path == filename:
                    fd = openfile.fd
                    newprogress = openfile.position/os.stat(filename).st_size
                    break
            if newprogress is None or (self.currentfd and fd != self.currentfd):
                with self.cond:
                    self.plq.popleft()
                    os.unlink(plname)
                    os.unlink(symlfn)
                    self.cond.notify()
                    self.currentfd = None
            else:
                self.currentfd = fd
                break
        self.progress_bar(filename, newprogress)

    def thr_check(self):
        while not self.stop.is_set():
            self.check_progress()
            self.stop.wait(1)

    def progress_bar(self, newfile=None, newprogress=None):
        if newprogress is None:
            if self.verbose > 0 and self.progressbar:
                print('')
            return
        newfile = newfile or self.current
        if self.current != newfile:
            if self.verbose > 0:
                if self.progressbar and self.progress is not None:
                    print('#' * (self.progress_barlen - round(
                                 self.progress*self.progress_barlen)), file=sys.stderr)
                print(newfile, file=sys.stderr)
                if self.progressbar:
                    print((' '*(self.progress_barlen+1)) + ']',
                          end='\r[', file=sys.stderr)
            self.current = newfile
            self.progress = 0
        if self.verbose > 0 and self.progressbar:
            print('#' * (round(newprogress*self.progress_barlen) -
                         round(self.progress*self.progress_barlen)),
                  end='', file=sys.stderr)
        sys.stderr.flush()
        self.progress = newprogress

    def proc_init(self, playlist):
        #print('play ' + playlist)
        cmd = [self.ffmpeg, '-nostats', '-safe', '0', '-re', '-i', playlist] + self.args
        output = (subprocess.DEVNULL if self.verbose < 2 else None)
        self.proc = subprocess.Popen(cmd, cwd=self.tmpdir,
            stdin=subprocess.DEVNULL, stdout=output, stderr=output)
        self.procinfo = psutil.Process(self.proc.pid)

    def write_playlist(self, filename):
        if self.stop.is_set():
            return
        if not self.nextpl:
            nextplfd, self.nextpl = tempfile.mkstemp(
                suffix='.txt', dir=self.tmpdir)
            os.close(nextplfd)
        filename = os.path.abspath(filename)
        with self.cond:
            while len(self.plq) > 1 and not self.stop.is_set():
                self.cond.wait(1)
            nextpl = self.nextpl
        #print('write ' + self.nextpl)
        with open(self.nextpl, 'wb') as f:
            f.write(b"ffconcat version 1.0\n")
            symlfn = os.path.splitext(self.nextpl)[0] + os.path.splitext(filename)[1]
            os.symlink(filename, symlfn)
            relfn = os.path.relpath(symlfn, self.tmpdir)
            f.write(("file '%s'\n" % relfn).encode('utf-8'))
            nextplfd, self.nextpl = tempfile.mkstemp(
                suffix='.txt', dir=self.tmpdir)
            os.close(nextplfd)
            relnextpl = os.path.relpath(self.nextpl, self.tmpdir)
            f.write(("file '%s'\n" % relnextpl).encode('utf-8'))
        self.plq.append((filename, symlfn, nextpl))
        if self.proc is None:
            self.proc_init(nextpl)
        return (filename, symlfn, nextpl)

    def exit(self):
        self.stop.set()
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.progress_bar()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(description="FFMpeg dynamic playlist input. Feed stdin with your list of media files.")
    parser.add_argument("-e", "--ffmpeg", help="ffmpeg/avconv executable, can be set using FFMPEG environment variable")
    parser.add_argument("-v", "--verbose", action='count', help="verbosity level. -v prints filename, -vv shows ffmpeg output.")
    parser.add_argument("-p", "--progress", action='store_true', help="show progress bar.")
    parser.add_argument("args", help="ffmpeg output arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    ffargs = args.args
    if ffargs[0] == '--':
        ffargs = ffargs[1:]
    fm = FFMpegManager(ffargs, args.ffmpeg, args.verbose or 0, args.progress)
    check_thread = threading.Thread(target=fm.thr_check, name='check', daemon=True)
    check_thread.start()
    try:
        for ln in sys.stdin:
            fm.write_playlist(ln.rstrip('\r\n'))
            if fm.stop.is_set():
                break
    finally:
        fm.exit()
    check_thread.join()

if __name__ == '__main__':
    main()
