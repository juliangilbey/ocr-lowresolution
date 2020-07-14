#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""This generates low resolution images and box files from given text.

The box files are not correct: they are the full size of the image, not
the size of the text within it.  Fixing this requires a tesseract run
with lstmbox, then running fix_lstm_box.py on it.
"""

# loosly based on ocrd-train/generate_line_box.py
# now https://github.com/tesseract-ocr/tesstrain
import argparse
import unicodedata
import random
import os
import os.path
import glob
import re
from textimages import hires_from_text, hires_to_lores


arg_parser = argparse.ArgumentParser(
    description='Creates tesseract training image and box files '
                'for given text strings')

arg_parser.add_argument('txt', metavar='TEXTFILE',
                        help='File containing text lines to generate')

arg_parser.add_argument('-b', '--binary', action='store_true',
                        help='Generate binary images (default: greyscale)')

arg_parser.add_argument('-r', '--resolution', metavar='RES',
                        default=60, type=int,
                        help='Resolution of images')

arg_parser.add_argument('-o', '--outdir', metavar='DIR',
                        help='Output directory for generated image files',
                        required=True)

arg_parser.add_argument('--outbase', metavar='BASENAME',
                        help='Basename for output files '
                             '(default: TEXTFILE basename)')

arg_parser.add_argument('--fonts', metavar='FONTS',
                        help='Font to generate, comma-separated list '
                        '(spaces can be replaced by underscores); '
                        'will cycle through them, one per line',
                        default='Times New Roman')

arg_parser.add_argument('--fontsizes', metavar='SIZES',
                        help='Fontsize, comma-separated list; will cycle '
                        'through them for each font, one per line',
                        default=10)

arg_parser.add_argument('--rotations', metavar='POLICY',
                        choices=['false', 'true', 'cycle'],
                        help='If "true", apply a random small rotation; '
                        'if "cycle", do with and without for each font/size')

arg_parser.add_argument('--exposure', metavar='EXP', type=int,
                        help='+ is lighter, - is darker',
                        default=0)

arg_parser.add_argument('--threshold', metavar='THRESH', type=int,
                        help='for binary images, '
                             '>128 is darker, <128 is lighter',
                        default=128)

arg_parser.add_argument('--noise', metavar='NOISE', type=int,
                        help='amount of Gaussian noise to add',
                        default=3)

arg_parser.add_argument('--seed', metavar='SEED',
                        help='random seed to use')

arg_parser.add_argument('-c', '--cont', action='store_true',
                        help='Add images to existing directory')

arg_parser.add_argument('-d', '--debug', action='store_true',
                        help='Run in debug mode')

args = arg_parser.parse_args()

if args.seed is not None:
    random.seed(args.seed)
else:
    random.seed(args.txt)
downscale = 300 // args.resolution
upscale = 300 // args.resolution

txtbase = os.path.basename(args.txt)
if args.outbase is None:
    outbase = os.path.splitext(txtbase)[0]
else:
    outbase = args.outbase

if args.cont:
    boxes = glob.glob(os.path.join(args.outdir, outbase + '*.box'))
    numre = re.compile(r'.*_(\d+)\.box')
    linenum = 0
    for b in boxes:
        bmatch = numre.search(b)
        if bmatch:
            ln = int(bmatch.group(1))
            if ln > linenum:
                linenum = ln
else:
    linenum = 0

fonts = args.fonts.replace('_', ' ').split(',')
fonts_nospace = list(map(lambda f: f.replace(' ', '_'), fonts))
sizes = list(map(float, args.fontsizes.split(',')))
if not args.rotations or args.rotations == 'false':
    rotations = [False]
elif args.rotations.lower() == 'true':
    rotations = [True]
else:
    rotations = [False, True]
fontnum = 0
sizenum = 0
rotnum = 0

with open(args.txt) as f:
    for line in f:
        line = line.strip()
        if rotations[rotnum]:
            rotation = random.gauss(0, 0.5)
        else:
            rotation = 0
        print('Processing %s line %d; font = %s, size = %s, rotation %f' %
              (txtbase, linenum + 1, fonts[fontnum], sizes[sizenum], rotation))

        hires = hires_from_text(line, fonts[fontnum],
                                fontsize=sizes[sizenum],
                                rotation=rotation, res=300,
                                debug=args.debug)
        if not hires:
            continue
        lores = hires_to_lores(hires, downscale, binary=args.binary,
                               exposure=args.exposure,
                               threshold=args.threshold,
                               noise=args.noise, border=2)
        if not lores:
            # the image was entirely white
            continue
        linenum += 1

        width, height = lores.size
        hiwidth = upscale * width
        hiheight = upscale * height
        boxtxt = ''

        for i in range(1, len(line)):
            char = line[i]
            prev_char = line[i-1]
            if unicodedata.combining(char):
                boxtxt += '%s %d %d %d %d 0\n' % \
                            ((prev_char + char), 0, 0, hiwidth, hiheight)
            elif not unicodedata.combining(prev_char):
                boxtxt += '%s %d %d %d %d 0\n' % \
                            (prev_char, 0, 0, hiwidth, hiheight)
        if not unicodedata.combining(line[-1]):
            boxtxt += '%s %d %d %d %d 0\n' % \
                        (line[-1], 0, 0, hiwidth, hiheight)
        boxtxt += ('%s %d %d %d %d 0' %
                   ("\t", hiwidth, hiheight, hiwidth + 1, hiheight + 1))

        outname = outbase + '_' + fonts_nospace[fontnum] + '_%03d' % linenum
        lores.save(os.path.join(args.outdir, outname + '.png'),
                   compression=None)
        with open(os.path.join(args.outdir, outname + '.gt.txt'), "w") as gt:
            print(line, file=gt)
        with open(os.path.join(args.outdir, outname + '.box'), "w") as box:
            print(boxtxt, file=box)

        # cycle through the options
        if rotnum < len(rotations) - 1:
            rotnum += 1
        else:
            rotnum = 0
            if sizenum < len(sizes) - 1:
                sizenum += 1
            else:
                sizenum = 0
                if fontnum < len(fonts) - 1:
                    fontnum += 1
                else:
                    fontnum = 0
