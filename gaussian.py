#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import numpy as np
from scipy import signal
from PIL import Image


def gaussfilter_im(img, sd):
    """Filter a PIL Image using a spatial domain Gaussian filter

    The standard deviation of the Gaussian is given by the sd parameter.
    """

    if img.mode == '1':
        img = img.convert('L')
    imgnp = 255 - np.asarray(img)
    xsize, ysize = imgnp.shape

    # This originally said 11 * sd, but that seems excessive;
    # as exp(-16/2) = 0.0003, with s.d. 1, 4 pixels away contributes
    # less than 0.1 to the value of the current pixel.  So we reduce
    # to a support of 3 either side, so a width of 7; that should speed
    # things up significantly
    xsup = min(xsize, math.ceil(7 * sd))
    ysup = min(ysize, math.ceil(7 * sd))
    if xsup % 2 == 0:
        xsup += 1
    xsupm = (xsup - 1) // 2
    if ysup % 2 == 0:
        ysup += 1
    ysupm = (ysup - 1) // 2

    def gfn(x, y):
        dist2 = (x - xsupm) ** 2 + (y - ysupm) ** 2
        return np.exp(-dist2 / (2 * sd ** 2))

    gausskern = np.fromfunction(gfn, (xsup, ysup),
                                dtype=np.float64)
    gausskern /= np.sum(gausskern)

    imgout = signal.convolve2d(imgnp, gausskern, mode='same')
    imgoutnp = 255 - np.asarray(np.clip(np.rint(imgout), 0, 255),
                                dtype=np.uint8)
    return Image.fromarray(imgoutnp)
