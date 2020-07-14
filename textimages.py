#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Functions to create a lower-resolution image from a higher one

This module can also create a high-resolution image from text,
assuming that LuaLaTeX can cope with it.  It can create greyscale
or binary (black and white) images.
"""

import random
import subprocess
import os
import math
import warnings
import tempfile
import numpy as np
from PIL import Image


def hires_from_text(text, font, fontsize=10, rotation=0,
                    res=1200, border=12, debug=False):
    """Generate a high-res image of a given line of text.

    The font and font size can be specified, as well as an angle
    of rotation (in degrees), the resolution of the image (dpi)
    and the desired border in pixels.

    If debug is set to True, the this function will use the
    current working directory and won't clean up afterwards.

    Returns the word image as a PIL Image.
    """

    saveenv = os.environ['PATH']
    os.environ['PATH'] += ':/Library/TeX/texbin:/opt/local/bin'

    curdir = os.getcwd()
    if not debug:
        tempdir = tempfile.TemporaryDirectory()
        os.chdir(tempdir.name)

    borderpt = (border / res) * 72.27
    with open('hires-line.tex', 'w') as outtex:
        ltx_pre = r"""\documentclass[border=%.5fpt]{standalone}
\usepackage{fontspec}
\usepackage{verbatim}
\makeatletter
\def\verbatim@font{}
\makeatother
\usepackage{graphicx}
\usepackage{cprotect}
\begin{document}
\setmainfont{%s}
\fontsize{%fpt}{%fpt}\selectfont
""" % (borderpt, font, fontsize, fontsize)

        print(ltx_pre, end='', file=outtex)

        text = text.strip()
        if text == '':
            os.chdir(curdir)
            os.environ['PATH'] = saveenv
            return None

        for delim in '+-=^|"~?:#&':
            if delim not in text:
                vtext = r'\verb%s%s%s' % (delim, text, delim)
                break
        else:
            os.chdir(curdir)
            os.environ['PATH'] = saveenv
            raise Exception('cannot typeset this text; too many funny chars: '
                            '%s' % text)

        if rotation != 0:
            print(r'\newbox\hiresbox', file=outtex)
            print(r'\cprotect[mm]\setbox\hiresbox\hbox{%s}' % vtext,
                  file=outtex)
            print(r'\rotatebox{%f}{\usebox\hiresbox}' % rotation,
                  file=outtex)
        else:
            print(vtext, file=outtex)

        print(r'\end{document}', file=outtex)

    try:
        subprocess.run(['lualatex', '--interaction=batchmode',
                        'hires-line.tex'],
                       check=True, capture_output=True)
    except Exception:
        os.chdir(curdir)
        os.environ['PATH'] = saveenv
        raise

    try:
        subprocess.run(['pdftoppm', '-gray', '-r', str(res),
                        '-singlefile', 'hires-line.pdf', 'hires-line'],
                       check=True, capture_output=True)
    except Exception:
        os.chdir(curdir)
        os.environ['PATH'] = saveenv
        raise

    warnings.simplefilter('ignore', Image.DecompressionBombWarning)
    im = Image.open('hires-line.pgm')
    # Unfortunately, this image may have too much white space
    # around it, as the box may be larger than the actual text.
    # So we manually remove the requisite number of blank white
    # rows and columns.
    imarrayfull = np.asarray(im, dtype=np.uint8)
    imarrayinv = 255 - imarrayfull
    imcsum = np.sum(imarrayinv, axis=0)
    imrsum = np.sum(imarrayinv, axis=1)
    rfirst = cfirst = 0
    rows, cols = imarrayinv.shape
    for i in range(rows):
        if imrsum[i] != 0:
            rfirst = i
            break
    for i in range(rows - 1, rfirst, -1):
        if imrsum[i] != 0:
            rlast = i + 1
            break
    for i in range(cols):
        if imcsum[i] != 0:
            cfirst = i
            break
    for i in range(cols - 1, cfirst, -1):
        if imcsum[i] != 0:
            clast = i + 1
            break

    rfirst = max(rfirst - border, 0)
    cfirst = max(cfirst - border, 0)
    rlast = min(rlast + border, rows)
    clast = min(clast + border, cols)

    imout = Image.fromarray(imarrayfull[rfirst:rlast, cfirst:clast])

    os.chdir(curdir)
    os.environ['PATH'] = saveenv
    warnings.simplefilter('default', Image.DecompressionBombWarning)
    return imout


def hires_to_lores(im, scale, binary=False,
                   threshold=128, dorandom=True, offset=(0, 0),
                   exposure=0, noise=0, border=0):
    """Scales a high-resolution image to a lower greyscale one

    The input (im) and output are both PIL Images.

    The scale factor is given by "scale".  This should be an integer.
    It is not necessary for scale to divide the size of the image.
    The resulting lowres image will have enough pixels to ensure that
    every non-zero average is included in the result.  There will be no
    empty borders, unless border is set to a positive value, in which
    case there will be a border of that many white pixels.

    The offset used to calculate the lowres pixel corners is
    random if dorandom == True, otherwise the offset is given by
    offset = (row, column).

    The default is for the output to be greyscale.  If binary=True
    is given, then the output is black/white, thresholded at threshold.

    The exposure indicates to lighten or darken the image.  The
    brightness level is increased or decreased by 2% when the exposure
    is +/-1, prior to any thresholding.  Yes, it might be nicer to
    calculate this using morphological dilation / erosion of the
    original text image, but it is not necessary to be that precise.

    The noise is Gaussian and added (after the exposure modification)
    with a standard deviation given by "noise".  Note that it is
    added *after* the averaging process and not before, otherwise it
    would be almost completely eliminated.  (It is also applied after
    exposure correction.)
    """

    (cols, rows) = im.size
    imarray = np.full((rows + 2 * scale, cols + 2 * scale), 255,
                      dtype=np.uint8)
    imarray[scale:-scale, scale:-scale] = np.asarray(im, dtype=np.uint8)

    if dorandom:
        offr = random.randint(0, scale - 1)
        offc = random.randint(0, scale - 1)
    else:
        (offr, offc) = offset

    lowcols = math.ceil((cols - 1) / scale) + 1
    lowrows = math.ceil((rows - 1) / scale) + 1
    lowarray = np.empty((lowrows, lowcols), dtype=np.uint8)
    # The following is for numpy >= 1.17:
    # rng = np.random.default_rng()
    # noisearray = noise * rng.standard_normal((lowrows, lowcols))
    # This works on numpy < 1.17
    noisearray = noise * np.random.standard_normal((lowrows, lowcols))

    for r in range(lowrows):
        for c in range(lowcols):
            av = np.average(
                    imarray[offr + r * scale:offr + (r + 1) * scale,
                            offc + c * scale:offc + (c + 1) * scale])
            av *= 1 + 2 * exposure / 100
            av += noisearray[r, c]
            if binary:
                if av < threshold:
                    lowarray[r, c] = 0
                else:
                    lowarray[r, c] = 255
            else:
                lowarray[r, c] = np.clip(round(av), 0, 255)

    checked = False
    while not checked:
        for j in range(lowcols):
            if lowarray[0, j] != 255:
                checked = True
                break
        else:
            lowarray = np.delete(lowarray, 0, 0)
            lowrows -= 1
            if lowrows == 0:
                # the whole image is white
                return None

    checked = False
    while not checked:
        for j in range(lowcols):
            if lowarray[-1, j] != 255:
                checked = True
                break
        else:
            lowarray = np.delete(lowarray, -1, 0)
            lowrows -= 1

    checked = False
    while not checked:
        for i in range(lowrows):
            if lowarray[i, 0] != 255:
                checked = True
                break
        else:
            lowarray = np.delete(lowarray, 0, 1)
            lowcols -= 1

    checked = False
    while not checked:
        for i in range(lowrows):
            if lowarray[i, -1] != 255:
                checked = True
                break
        else:
            lowarray = np.delete(lowarray, -1, 1)
            lowcols -= 1

    if border > 0:
        lowarray = np.insert(lowarray, [0] * border + [lowrows] * border,
                             255, axis=0)
        lowarray = np.insert(lowarray, [0] * border + [lowcols] * border,
                             255, axis=1)

    return Image.fromarray(lowarray)
