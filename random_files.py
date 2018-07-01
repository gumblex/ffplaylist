#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import glob
import random
import itertools

fnlist = sys.argv[1:] or '*'

while 1:
    files = list(itertools.chain.from_iterable(map(glob.glob, fnlist)))
    if not files:
        break
    print(random.choice(files))
