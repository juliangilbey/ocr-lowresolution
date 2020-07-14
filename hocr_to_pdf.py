#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This takes an hOCR data structure and the input image,
and draws the bounding boxes on the input image so we can see
how the segmentation worked.
"""

import os
import sys
import subprocess
from PIL import Image, ImageColor, ImageDraw
import numpy as np
import parse_hocr

# Support for LaTeX output files
latex_template = r'''\documentclass{article}

\usepackage{geometry}
\geometry{%%
  paperwidth=%(wd)fbp,   %% = img width / 300 * 72 ("bp" = PostScript points)
  paperheight=%(ht)fbp,  %% = img_width / 300 * 72
  margin=0pt,
  ignoreall,
  noheadfoot,
  }

\usepackage{pdfcomment}
\usepackage[absolute]{textpos}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\setlength{\topskip}{0pt}
\pagestyle{empty}

\begin{document}
%% \includegraphics fails because it adds some extra padding somewhere
\vbox to 0pt{\hbox to 0pt{%%
    \pdfximage width %(wd)fbp height %(ht)fbp depth 0bp {%(fn)s}%%
    \pdfrefximage\pdflastximage
  \hss}\vss}%%
%(annot)s
\end{document}
'''

annot_template = r'''\begin{textblock*}{%(wd)fbp}(%(left)fbp,%(top)fbp)%%
  \pdftooltip{\rule{%(wd)fbp}{0pt}\rule{0pt}{%(ht)fbp}}{%(txt)s}%%
\end{textblock*}
'''


def texify(w):
    """Escape special characters"""
    wout = ''
    for c in w:
        if c in r'\{}$&#^_%~"':
            wout += '\\'
        wout += c
    return wout


def rgcolor(f):
    red = 0
    green = 120
    hsv = 'hsv(%d,70%%,100%%)' % (f * green + (1 - f) * red)
    rgb = np.array(ImageColor.getrgb(hsv), dtype=np.float32)
    return rgb / 255


def produce_hocr_pdf(img, words, outbase, debug=False):
    """Take an img and a word list, and output a coloured annotated PDF

    The word list is in our internal format, as produced by hOCRParser.

    The output PDF is outbase.pdf, and outbase.tex is produced en route.

    If debug=True, then outbase.tex is not deleted.

    This function needs to be called from the directory in which
    outbase is to be saved.
    """
    saveenv = os.environ['PATH']
    os.environ['PATH'] += ':/Library/TeX/texbin:/opt/local/bin'

    (wd, ht) = img.size
    img_arr = np.asarray(img)
    img_mask = np.full((ht, wd, 3), 1, dtype=np.float32)

    annots = ''
    for w in words:
        (ulx, uly, lrx, lry) = w['bbox']
        col = rgcolor(w['conf'] / 100)
        for x in range(ulx, lrx):
            for y in range(uly, lry):
                img_mask[y, x, :] = col
        annotdir = {}
        annotdir['wd'] = (lrx - ulx) / 300 * 72
        annotdir['ht'] = (lry - uly) / 300 * 72
        annotdir['left'] = ulx / 300 * 72
        annotdir['top'] = uly / 300 * 72
        annotdir['txt'] = '"%s" (%d)' % (texify(w['word']), w['conf'])
        annots += annot_template % annotdir

    img_new = np.empty((ht, wd, 3), dtype=np.uint8)
    for c in range(3):
        img_new[:, :, c] = img_arr * img_mask[:, :, c]

    imgcol = Image.fromarray(img_new, mode='RGB')
    imgcol.save(outbase + '-hocr.png')

    latexdir = {'fn': outbase + '-hocr.png',
                'wd': wd / 300 * 72, 'ht': ht / 300 * 72,
                'annot': annots}
    latex_content = latex_template % latexdir
    with open(outbase + '-hocr.tex', 'w') as latexfile:
        print(latex_content, file=latexfile)

    try:
        output = subprocess.run(['pdflatex', '--interaction=batchmode',
                                 outbase + '-hocr.tex'],
                                check=True, capture_output=True)
    except Exception:
        os.environ['PATH'] = saveenv
        print('pdflatex %s-hocr.tex failed' % outbase, file=sys.stderr)
        print('stdout output: %s' % output.stdout, file=sys.stderr)
        print('stderr output: %s' % output.stderr, file=sys.stderr)
        return

    # clean up
    os.remove(outbase + '-hocr.aux')
    os.remove(outbase + '-hocr.log')
    os.remove(outbase + '-hocr.out')
    os.remove(outbase + '-hocr.upa')
    os.remove(outbase + '-hocr.upb')
    if not debug:
        os.remove(outbase + '-hocr.tex')

    os.environ['PATH'] = saveenv


def ocr_page_to_pdf(img, page, outbase, bbox='', debug=False):
    """Take an img and an ocr page, and output a coloured annotated PDF

    The word list is in our internal format, as produced by hOCRParser.

    The output PDF is outbase.pdf, and outbase.tex is produced en route.

    If debug=True, then outbase.tex is not deleted.

    bbox is a string; if 'area' in bbox, then draw the area bounding
    boxes, and similarly for 'par' and 'line'.

    This function needs to be called from the directory in which
    outbase is to be saved.
    """
    saveenv = os.environ['PATH']
    os.environ['PATH'] += ':/Library/TeX/texbin:/opt/local/bin'

    (wd, ht) = img.size
    img_arr = np.asarray(img)
    img_mask = np.full((ht, wd, 3), 1, dtype=np.float32)
    bbox_mask = Image.new('RGB', (wd, ht), color=(0, 0, 0))
    bbox_draw = ImageDraw.Draw(bbox_mask)

    acol = ImageColor.getrgb('hsv(240, 70%, 100%)')
    pcol = ImageColor.getrgb('hsv(290, 70%, 100%)')
    lcol = ImageColor.getrgb('hsv(180, 70%, 100%)')

    annots = ''
    for area in page['areas']:
        for par in area['pars']:
            for ln in par['lines']:
                for w in ln['words']:
                    (ulx, uly, lrx, lry) = w['bbox']
                    col = rgcolor(w['conf'] / 100)
                    for x in range(ulx, lrx):
                        for y in range(uly, lry):
                            img_mask[y, x, :] = col
                    annotdir = {}
                    annotdir['wd'] = (lrx - ulx) / 300 * 72
                    annotdir['ht'] = (lry - uly) / 300 * 72
                    annotdir['left'] = ulx / 300 * 72
                    annotdir['top'] = uly / 300 * 72
                    annotdir['txt'] = '"%s" (%d)' % (texify(w['word']),
                                                     w['conf'])
                    annots += annot_template % annotdir
                if 'line' in bbox:
                    bbox_draw.rectangle(ln['bbox'], outline=lcol, width=3)
            if 'par' in bbox:
                bbox_draw.rectangle(par['bbox'], outline=pcol, width=5)
        if 'area' in bbox:
            bbox_draw.rectangle(area['bbox'], outline=acol, width=7)

    img_new = np.empty((ht, wd, 3), dtype=np.uint8)
    for c in range(3):
        img_new[:, :, c] = img_arr * img_mask[:, :, c]

    # overwrite img_new with bounding boxes if there are any
    bbox_arr = np.asarray(bbox_mask)
    bbox_sum = np.sum(bbox_arr, axis=2)
    # this is clunky; there's probably a better way, but it will do
    for i in range(ht):
        for j in range(wd):
            if bbox_sum[i, j] > 0:
                img_new[i, j, :] = bbox_arr[i, j, :]

    imgcol = Image.fromarray(img_new, mode='RGB')
    imgcol.save(outbase + '-hocr.png')

    latexdir = {'fn': outbase + '-hocr.png',
                'wd': wd / 300 * 72, 'ht': ht / 300 * 72,
                'annot': annots}
    latex_content = latex_template % latexdir
    with open(outbase + '-hocr.tex', 'w') as latexfile:
        print(latex_content, file=latexfile)

    try:
        output = subprocess.run(['pdflatex', '--interaction=batchmode',
                                 outbase + '-hocr.tex'],
                                check=True, capture_output=True)
    except Exception:
        os.environ['PATH'] = saveenv
        print('pdflatex %s-hocr.tex failed' % outbase, file=sys.stderr)
        print('stdout output: %s' % output.stdout, file=sys.stderr)
        print('stderr output: %s' % output.stderr, file=sys.stderr)
        return

    # clean up
    os.remove(outbase + '-hocr.aux')
    os.remove(outbase + '-hocr.log')
    os.remove(outbase + '-hocr.out')
    os.remove(outbase + '-hocr.upa')
    os.remove(outbase + '-hocr.upb')
    if not debug:
        os.remove(outbase + '-hocr.tex')

    os.environ['PATH'] = saveenv


def process_file(fn, hocr=None, debug=False, bbox='area,par,line'):
    imgdir, imgfn = os.path.split(fn)
    if imgdir:
        cwd = os.getcwd()
        os.chdir(imgdir)
    else:
        cwd = None

    imgbase, imgext = os.path.splitext(imgfn)

    if hocr:
        hocrbase, hocrext = os.path.splitext(hocr)
        if hocrext != '.hocr':
            print('hocr filename does not end .hocr, things may go wrong')
    else:
        hocr = imgbase + '.hocr'
        hocrbase = imgbase
    page, tidied = parse_hocr.parse_hocr_file(hocr)

    try:
        img_orig = Image.open(imgfn)
    except OSError as err:
        if cwd is not None:
            os.chdir(cwd)
        print('%s file not found' % imgfn, file=sys.stderr)
        raise err

    ocr_page_to_pdf(img_orig, tidied, hocrbase, bbox=bbox, debug=debug)

    if cwd is not None:
        os.chdir(cwd)


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description='Turns hOCRs into PDFs')
    arg_parser.add_argument('-d', '--debug', action='store_true',
                            help='Produce debugging information')
    arg_parser.add_argument('image',
                            help='Image file to process')
    arg_parser.add_argument('hocr', nargs='?', default=None,
                            help='Image file to process')
    args = arg_parser.parse_args()
    debug = True if args.debug else False

    process_file(args.image, hocr=args.hocr, debug=debug, bbox='')
