#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import glob
import os
import re
import argparse

"""
Merge all of the CSV metrics files in the simulated-60dpi
directory into a single CSV file.

We also modify the fields somewhat to make the resulting file
more useful.
"""

arg_parser = argparse.ArgumentParser(
    description='Merge CSV metrics files into one single CSV file')


arg_parser.add_argument('--basedir', default='.',
                        help='Base directory to work from')
arg_parser.add_argument('subdir', help='Subdirectory to process')

args = arg_parser.parse_args()

fre = re.compile(r'.*/([a-z-]*)-([A-Z][A-Za-z-]*)-'
                 r'page(\d)-merged-(.*)\.csv')
# when processing linedata files, the filename is different
lfre = re.compile(r'.*/([a-z-]*)_([A-Z][A-Za-z_0-9-]*)_(\d+)'
                  r'-merged-(.*)\.csv')

if args.basedir != '.':
    os.chdir(args.basedir)

with open('all-merged%s.csv' % args.subdir, 'w', newline='') as csvoutfile:
    csvout = csv.writer(csvoutfile)
    csvout.writerow(['text', 'font', 'page', 'blurring',
                     'chars', 'words', 'cdist', 'wdist',
                     'cdistq', 'wdistq'])
    for c in sorted(glob.glob('%s/*/*-merged-*.csv' % args.subdir)):
        cmatch = fre.match(c)
        if cmatch:
            textname, font, page, blurring = cmatch.groups()
        else:
            cmatch = lfre.match(c)
            if cmatch:
                textname, font, page, blurring = cmatch.groups()
            else:
                print('Could not match filename %s; skipping' % c)
                continue
        with open(c, newline='') as csvinfile:
            csvin = csv.DictReader(csvinfile)
            for row in csvin:
                csvout.writerow([textname, font, page, blurring,
                                 row['Chars'], row['Words'],
                                 row['C dist'], row['W dist'],
                                 row['C dist quotes'],
                                 row['W dist quotes']])
