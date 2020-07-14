#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Perform OCR on an image (default 60dpi greyscale), and calculate
# the Levenshtein distance of the results from the ground truth, if found

# This requires a modified version of tesseract that can handle
# low-resolution images

import sys
import os
import subprocess
# import json
import argparse
from PIL import Image
import parse_hocr
import compare_hocr
import hocr_metrics

"""
Command line: $0 [options] <img>.png

This program will process the image with tesseract,
and the resulting .hocr file(s) will have .hocr in place of .png.
The merged result will be saved as <img>-merged.hocr and a text
version will be saved as <img>-merged.txt.

If there is a known ground truth, it should be saved as <img>.gt.txt,
or specified on the command line.  The Levenstein distances will be
calculated if this file exists, and the results will be output to
<img>.metrics
"""

home = os.environ.get('HOME', '/Users/jdg')
tessdatadir = home + '/Cognizant/tesstrain/'

arg_parser = argparse.ArgumentParser(
    description='Processes images with multiple tesseract runs')

arg_parser.add_argument('-s', '--scalings', default='C0',
                        help='Scalings/blurs to use; '
                             'B/L/C = box/bilinear/bicubic followed by blur '
                             'amount, eg B0, and '
                             'use specially-trained network')
arg_parser.add_argument('-r', '--resolution', metavar='RES',
                        default=0, type=int,
                        help='Resolution of images (default=60)')
arg_parser.add_argument('-d', '--debug', action='store_true',
                        help='Produce debugging information')
arg_parser.add_argument('-g', '--ground-truth',
                        help='Ground truth text file (default is image '
                             'name with .gt.txt extension)')
arg_parser.add_argument('--simulate', action='store_true',
                        help='Downscale a given 300dpi image before starting')
arg_parser.add_argument('-f', '--force', action='store_true',
                        help='Force rerunning of tesseract')
arg_parser.add_argument('--outbase',
                        help='basename of output files; default is basename '
                             'of input image file')
arg_parser.add_argument('--force-image', action='store_true',
                        help='Force regenerating simulated image')
arg_parser.add_argument('--tessbin-dir',
                        help='Directory in which tesseract appears; '
                             'default is to search on PATH')
arg_parser.add_argument('--tessenv', action='append',
                        help='Add this to the tesseract environment, eg '
                             '"DYLD_LIBRARY_PATH=../tesseract/src/api/.libs"'
                             ' Can be used multiple times')
arg_parser.add_argument('--tessdata-path', default=tessdatadir,
                        help='Use this path to the tessdata directory')
arg_parser.add_argument('--tessdata', default='dataRES_SCALING+BLUR',
                        help='Use this directory for the tessdata; '
                             'RES is replaced by the resolution '
                             'SCALING is replaced by the scaling name and '
                             'BLUR is replaced by the blur amount')
arg_parser.add_argument('-w', '--wmetrics', action='store_true',
                        help='Produce word-level metrics for image')
arg_parser.add_argument('image', help='Image to process')

args = arg_parser.parse_args()
debug = args.debug

if args.tessbin_dir:
    tessbin = os.path.join(args.tessbin_dir, 'tesseract')
else:
    tessbin = 'tesseract'

curdir = os.getcwd()

imgdir, imgfn = os.path.split(args.image)
imgbase, imgext = os.path.splitext(imgfn)
if imgdir:
    os.chdir(imgdir)
if args.outbase:
    outbase = args.outbase
else:
    outbase = imgbase

if args.tessenv:
    for env in args.tessenv:
        if '=' in env:
            var, val = env.split('=', maxsplit=1)
            os.environ[var] = val
        else:
            print('--tessenv value does not have an = in it: %s' % env)
            print('ignoring this environment variable')

if args.resolution == 0:
    args.resolution = 60

if args.simulate:
    img = Image.open(imgfn)
    if img.mode == '1':
        img = img.convert(mode='L')

    # Our target images are 300 dpi
    if 300 % args.resolution != 0:
        print('Warning: resolution %d is not a factor of 300; '
              'using rounded quotient instead!' % args.resolution)
    factor = 300 // args.resolution

    (wd, ht) = img.size
    img = img.resize((wd // factor, ht // factor), resample=Image.BOX)
    imggbase = imgbase + '-simulated-%ddpi' % args.resolution
    if args.force_image or not os.path.isfile(imggbase + '.png'):
        img.save(imggbase + '.png')
        args.force = True

    (wd, ht) = img.size
    imgbig = None
else:
    imggbase = imgbase

pages = []
scalings = args.scalings.split(',')
scalingsstr = ''.join(scalings).replace('.', '')
orighocr = None
try:
    if args.ground_truth:
        gt = open(args.ground_truth).read()
    else:
        gt = open(imgbase + '.gt.txt').read()
except OSError:
    gt = None
    print('Failed to read ground truth file; skipping comparisons')

scaling_types = {'B': (0, 'box'),
                 'L': (1, 'bilinear'),
                 'C': (2, 'bicubic')}

for scaling in scalings:
    ext = '.png'
    if scaling[0] not in scaling_types:
        print('Unknown scaling type %s' % scaling[0])
        continue

    scaling_type = scaling_types[scaling[0]]
    blur = scaling[1:]
    scaling = scaling.replace('.', '')

    imgout = outbase + '-' + scaling

    if (args.force or not os.path.isfile(imgout + '.hocr')):
        ddir = args.tessdata.replace('RES', str(args.resolution))

        ddir = ddir.replace('SCALING', scaling_type[1])
        ddir = ddir.replace('BLUR', blur)

        ddir = os.path.join(args.tessdata_path, ddir, 'eng')
        os.environ['TESSDATA_PREFIX'] = ddir
        cmd = [tessbin,
               '--dpi', '300', '-l', 'eng',
               '-c', 'low_resolution_input=true',
               '-c', 'low_resolution_dpi=%d' % args.resolution,
               '-c', 'low_resolution_scaling=%d' % scaling_type[0],
               '-c', 'low_resolution_blurring=%s' % blur,
               '--psm', '6',
               imggbase + ext, imgout, 'txt', 'hocr']
        if debug:
            print('About to run: %s' % ' '.join(cmd), file=sys.stderr)
            print('TESSDATA_PREFIX = %s' % ddir)
        subprocess.run(cmd, check=True)
    tree, tidied = parse_hocr.parse_hocr_file(imgout + '.hocr',
                                                  resolution=args.resolution)
    pages.append(tidied)
    if not orighocr:
        orighocr = open(imgout + '.hocr').read()

    # produce word-level metrics if requested
    if args.wmetrics:
        if gt is not None:
            hocr_metrics.compute_hocr_diff(tidied, gt)
            hocr_metrics.output_hocr_diff_metrics(tidied,
                                                  imgout + '-wmetrics.csv')

    del tree, tidied

if not orighocr:
    print('No processing done; exiting')
else:
    out123 = compare_hocr.merge_ocr_pages(pages, debug)

    # update the hocr string to reflect the changes we've made
    hocr123 = compare_hocr.update_hocr(orighocr, out123)
    with open(outbase + '-merged-%s.hocr' % scalingsstr, 'w') as hocrout:
        print(hocr123, end='', file=hocrout)

    out123txt = parse_hocr.ocr_page_to_text(out123)
    with open(outbase + '-merged-%s.txt' % scalingsstr, 'w') as mergedtxt:
        print(out123txt, file=mergedtxt)

    if gt is not None:
        mergedfile = outbase + '-merged-%s.metrics' % scalingsstr
        mergedcsv = outbase + '-merged-%s.csv' % scalingsstr
        imgfilename = outbase + '-merged-%s' % scalingsstr
        cmptxt, cmpcsv = hocr_metrics.get_metrics(out123txt, gt, imgfilename)

        with open(mergedfile, 'w') as metrics:
            print(cmptxt, end='', file=metrics)
        with open(mergedcsv, 'w') as metrics:
            print(cmpcsv, end='', file=metrics)

os.chdir(curdir)
