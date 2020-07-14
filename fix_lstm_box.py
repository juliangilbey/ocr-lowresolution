#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Fix a box file by merging the output of tesseract lstmbox and a
box file with the correct character content but the wrong box size.

Usage: $0 basename

This will then merge <basename>-lstm.box and <basename>.box and
overwrite <basename>.box.
"""

import sys

basename = sys.argv[1]
boxdims = None

with open(basename + '-lstm.box') as lstmbox:
    for line in lstmbox:
        fields = line.split()
        boxdims = ' '.join(fields[-5:])
        break

# On rare occasions, tesseract can fail to make a meaningful
# boxfile using lstmbox; the result is an empty box file.
# We therefore do nothing more in that case.
# (The frequency of this in the entire set of eng.training_text
# across the 7 different types of enlargement tested was 348
# out of 1355032.)
if boxdims:
    newbox = ''
    with open(basename + '.box') as box:
        for line in box:
            if line[0] == '\t':
                newbox += '\t ' + boxdims + '\n'
                # this should be the final line, so we'll break here
                break
            else:
                newbox += line[0] + ' ' + boxdims + '\n'

    with open(basename + '.box', 'w') as box:
        print(newbox, end='', file=box)
