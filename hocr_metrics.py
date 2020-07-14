#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import difflib
import editdistance
import csv


def get_metrics(pagetxt, gt, filename):
    """Produce metrics on the Levenshtein distance from the ground truth

    Input:
        pagetxt: the text of a processed page
        gt: the ground truth
        filename: the image filename, saved in the CSV text

    Outputs:
        cmptxt: a textual representation of the comparison
        cmpcsv: a CSV representation of the same

    Both comparisons include both a direct comparison and one with
    left and right quote marks converted to straight quotes, and both
    a character and word comparison.

    All extraneous spaces are stripped, so whitespace differences
    are ignored.
    """

    pagestr = re.sub(r'\s+', ' ', pagetxt.strip())
    gtstr = re.sub(r'\s+', ' ', gt.strip())
    pagewords = pagestr.split()
    gtwords = gtstr.split()
    cdist = editdistance.eval(pagestr, gtstr)
    wdist = editdistance.eval(pagewords, gtwords)

    qtrans = str.maketrans('“”‘’—–', '""' + "''--")
    pagestrq = pagestr.translate(qtrans)
    pagewordsq = pagestrq.split()
    gtstrq = gtstr.translate(qtrans)
    gtwordsq = gtstrq.split()
    cdistq = editdistance.eval(pagestrq, gtstrq)
    wdistq = editdistance.eval(pagewordsq, gtwordsq)

    cmptxt = 'Ground truth chars: %d\n' % len(gtstr)
    cmptxt += 'Ground truth words: %d\n' % len(gtwords)
    cmptxt += 'OCR chars: %d\n' % len(pagestr)
    cmptxt += 'OCR words: %d\n' % len(pagewords)
    cmptxt += 'Levenstein distance chars: %d\n' % cdist
    cmptxt += 'Levenstein distance words: %d\n' % wdist
    cmptxt += 'CLA: %.2f\n' % (100 * (1 - cdist / len(gtstr)))
    cmptxt += 'WLA: %.2f\n' % (100 * (1 - wdist / len(gtwords)))
    cmptxt += '\n'
    cmptxt += 'With simplified quotes:\n'
    cmptxt += 'Levenstein distance chars: %d\n' % cdistq
    cmptxt += 'Levenstein distance words: %d\n' % wdistq
    cmptxt += 'CLA: %.2f\n' % (100 * (1 - cdistq / len(gtstr)))
    cmptxt += 'WLA: %.2f\n' % (100 * (1 - wdistq / len(gtwords)))

    cmpcsv = ','.join(['Filename',
                       'Chars', 'Words', 'C dist', 'W dist', 'CLA',
                       'WLA', 'C dist quotes', 'W dist quotes',
                       'CLA quotes', 'WLA quotes']) + '\n'
    cmpcsv += ('%s,%d,%d,%d,%d,%.4f,%.4f,%d,%d,%.4f,%.4f\n' %
               (filename,
                len(gtstr), len(gtwords), cdist, wdist,
                1 - cdist / len(gtstr),
                1 - wdist / len(gtwords),
                cdistq, wdistq,
                1 - cdistq / len(gtstr),
                1 - wdistq / len(gtwords)))

    return cmptxt, cmpcsv


def compute_hocr_diff(hocrpage, gt):
    """Compute whether each hOCR word is correct or not

    Input:
        hocrpage: a processed hOCR page
        gt: the ground truth of the page

    Outputs:
        The hocrpage is modified in place to include an indicator
        of whether each word is correct or not.

    This function only uses the straight-quotes version of the
    ground truth.  It uses difflib rather than Levenstein distance,
    so might not exactly match the results of the above function.

    For each word in the hOCR page, this function decides whether
    it is correct or not.  The results are saved in the 'correct'
    dict element.

    All extraneous spaces are stripped, so whitespace differences
    are ignored.
    """

    pagetext = []
    pagerefs = []

    for a in hocrpage['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                for w in ln['words']:
                    pagetext.append(w['word'])
                    pagerefs.append(w)

    qtrans = str.maketrans('“”‘’—–', '""' + "''--")
    gtq = gt.translate(qtrans)
    gttext = gtq.split()

    s = difflib.SequenceMatcher(None, pagetext, gttext)
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'replace' or tag == 'delete':
            for i in range(i1, i2):
                pagerefs[i]['correct'] = False
        elif tag == 'insert':
            pass
        elif tag == 'equal':
            for i in range(i1, i2):
                pagerefs[i]['correct'] = True
        else:
            print('Unknown tag: %s' % tag)


def output_hocr_diff_metrics(hocrpage, csvfile):
    """Output word-level metrics on the accuracy of hOCR output

    Input:
        hocrpage: an hOCR page processed with compute_hocr_diff
        csvfile: the name of the csv output file

    Outputs:
        The words in the hOCR page are written out to the CSV file
        with their confidence and whether or not they are correct.
    """

    headrow = ['Word', 'Confidence', 'Correct']
    outrows = []
    for a in hocrpage['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                for w in ln['words']:
                    outrows.append([w['word'], w['conf'], w['correct']])

    with open(csvfile, 'w') as outfile:
        outwriter = csv.writer(outfile)
        outwriter.writerow(headrow)
        outwriter.writerows(outrows)


if __name__ == '__main__':
    """
    Command line: $0 [--csv] gt.txt output.txt

    Computes the difference between the ground truth and output
    and displays the results as text or as a CSV file if the --csv
    option is given.

    The output is sent to stdout.
    """

    import argparse
    import sys

    arg_parser = argparse.ArgumentParser(
        description='Compute difference between '
                    'ground truth and tess output')

    arg_parser.add_argument('--csv', action='store_true',
                            help='Output CSV format')
    arg_parser.add_argument('gt', help='Ground truth')
    arg_parser.add_argument('output', help='Tesseract output to compare')
    args = arg_parser.parse_args()

    try:
        gt = open(args.gt).read()
    except OSError:
        print('Failed to read ground truth file')
        sys.exit(1)

    try:
        output = open(args.output).read()
    except OSError:
        print('Failed to read tesseract text output file')
        sys.exit(1)

    cmptxt, cmpcsv = get_metrics(output, gt, '')
    if args.csv:
        print(cmpcsv)
    else:
        print(cmptxt)
