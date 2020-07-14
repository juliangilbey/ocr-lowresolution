#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from copy import deepcopy
from collections import defaultdict
from operator import itemgetter
import re


def find_bbox_overlap(bbox1, bbox2):
    """Determine the overlap between two bounding boxes, if any.

    Input: two bounding boxes in hOCR format: [left, top, right, bottom]
    with left < right, top < bottom.

    Returns None if there is no overlap, otherwise returns:
    { 'bbox': ..., 'frac1': ..., 'frac2': ... }
    where bbox is the bounding box of the overlap,
    frac1 is the fraction of the area of bbox1 covered by the overlap,
    and frac2 is similar.
    """

    l1, t1, r1, b1 = bbox1
    l2, t2, r2, b2 = bbox2
    if r2 <= l1 or r1 <= l2 or b1 <= t2 or b2 <= t1:
        return None
    l0 = max(l1, l2)
    t0 = max(t1, t2)
    r0 = min(r1, r2)
    b0 = min(b1, b2)
    area1 = (r1 - l1) * (b1 - t1)
    area2 = (r2 - l2) * (b2 - t2)
    area0 = (r0 - l0) * (b0 - t0)
    return {'bbox': [l0, t0, r0, b0],
            'frac1': area0 / area1, 'frac2': area0 / area2}


def merge_ocr_pages(pages, debug=False):
    """Merges a sequence of tidied hOCR pages, output by tidy_ocr_page

    Input: a sequence of hOCR renderings of the same page

    Output: a single merged page

    This algorithm is as follows: start with a given hOCR, then work
    through the following hOCRs in sequence.  For each one, for each
    identified word on the page, record the new hOCR's rendition of the
    word, if there is one.  Then take the combined best option for each
    word in the given hOCR.

    We do this by adding a new element to each word's dict containing
    a dict of options.
    """

    page1copy = deepcopy(pages[0])
    for a in page1copy['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                for w in ln['words']:
                    w['readings'] = defaultdict(list,
                                                {w['word']: [w]})

    # Since we need the words in this master page sorted for the
    # merge_ocr_pages_match function, we do this once now rather
    # than repeatedly within that function.
    # Note that these are references into page1copy, so we can modify
    # page1copy through them.
    words1 = []
    for a in page1copy['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                for w in ln['words']:
                    words1.append(w)
    # we now sort them by increasing upper y coordinate
    words1.sort(key=lambda w: w['bbox'][1])

    for page in pages[1:]:
        merge_ocr_pages_match(page1copy, words1, page, debug)

    # We now choose the "best" word for each position
    merge_ocr_pages_pick_best(words1, debug)

    return page1copy


def merge_ocr_pages_match(page1, words1, page2, debug=False, tracing=False):
    """Matches two tidied hOCR pages, as output by tidy_ocr_page

    Input: page1: master page, containing collated info
           page2: new page to match to page1

    page1 is modified to incorporate page2 data
    """

    # Code from merge_ocr_wordlists (above) is used in an adapted
    # form in this function.

    # As we don't modify the words in page2, there is no need to copy,
    # we just collect them.
    words2 = []
    for a in page2['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                for w in ln['words']:
                    words2.append(w)
    words2.sort(key=lambda w: w['bbox'][1])

    # We do not need to start at the beginning of words2 each time
    # as the y values increase, so this records where we start
    start = 0
    # No word is taller than this, we presume
    maxy = 100
    # what is the minimum overlap threshold to consider?
    othresh = 0.2

    for w in words1:
        for i2 in range(start, len(words2)):
            w2 = words2[i2]
            # could switch this on if tracing is required
            if tracing:
                print('comparing this pair of words: id1 = %s, id2 = %s, '
                      'w1 = %s, w2 = %s, dictconf1 = %d, dictconf2 = %d' %
                      (w['id'], w2['id'], w['word'], w2['word'],
                       w['dictconf'], w2['dictconf']))
            if w2['bbox'][1] + maxy < w['bbox'][1]:
                # no hope that this word (w2) or anything earlier
                # will match with this word (w) in words1 or anything
                # after it.
                start = i2 + 1
                if tracing:
                    print('skipping A')
                continue
            if w2['bbox'][1] > w['bbox'][3]:
                if tracing:
                    print('skipping B')
                break
            # w and w2i are potentially comparable; do they overlap?
            overlap = find_bbox_overlap(w['bbox'], w2['bbox'])
            if overlap is None:
                if tracing:
                    print('skipping C')
                continue
            if overlap['frac1'] < othresh or overlap['frac2'] < othresh:
                # these are probably different words
                if tracing:
                    print('skipping D')
                continue
            else:
                if tracing:
                    print('found two words in same position')
                w['readings'][w2['word']].append(w2)
                del words2[i2]
                break

    # We don't know how to merge in remaining words.
    # So we'll just report them for now.
    if debug:
        print('Words left out during run of merge_ocr_pages_match:')
        for w2 in words2:
            print('Word: %s, conf: %d, bbox: %s' %
                  (w2['word'], w2['id'], w2['conf'], w2['bbox']))


def merge_ocr_pages_pick_best(words, debug=False):
    """Chooses the "best" option for each word

    Input: words: the words in a page resulting from running
                  merge_ocr_pages_match

    Output: words modified to have the "best" word at each location

    The original id is preserved, so that it can be used for matching
    with the original hOCR file; the id or combination of ids of the word
    actually used is stored in 'idused'.
    """

    for w in words:
        readings = {}
        for r, occurs in w['readings'].items():
            totalconf = 0
            for o in occurs:
                totalconf += o['modconf']
            readings[r] = totalconf

        # We pick the option with the highest overall confidence
        maxrc = max(readings.items(), key=itemgetter(1))
        maxr = maxrc[0]
        # We now take the maximum confidence one from this word.
        # We don't try too hard to pick the best bounding box, etc.,
        # as it is not critical.
        maxconf = -1
        maxconfw = None
        for o in w['readings'][maxr]:
            if o['conf'] > maxconf:
                maxconf = o['conf']
                maxconfw = o
        if debug:
            print('replacing word: id = %s, w = %s, dictconf = %d\n' %
                  (w['id'], w['word'], w['dictconf']))
            print('with: id = %s, w = %s, dictconf = %d\n' %
                  (maxconfw['id'], maxconfw['word'], maxconfw['dictconf']))
        w['word'] = maxconfw['word']
        w['bbox'] = maxconfw['bbox']
        w['conf'] = maxconfw['conf']
        w['dictconf'] = maxconfw['dictconf']
        w['modconf'] = maxconfw['modconf']
        w['idused'] = maxconfw['id']


def update_hocr(hocr, page, debug=False):
    """Update the hOCR string with the current best text in page

    This function assumes that the ids in page are (except for tags)
    exactly the same as those in hocr for areas, pars and lines, but
    not necessarily for words; it creates the word lines from scratch.

    It returns the new hOCR string.
    """

    # This is not particularly efficient, but it will do
    lines = {}
    for area in page['areas']:
        for par in area['pars']:
            for ln in par['lines']:
                colloc = ln['id'].find('+')
                lines[ln['id'][colloc + 1:]] = ln

    hocrlines = hocr.split('\n')
    hocrnew = ''

    line_re = re.compile(r"<span class='ocr_\w+' id='(line_[^']*)'")
    lineend_re = re.compile(r" *</span>")

    inline = False
    for hline in hocrlines:
        # if we're not currently processing an ocr_line or equivalent,
        # append this line to hocrnew
        if not inline:
            hocrnew += hline + '\n'
        else:
            lineendmatch = lineend_re.match(hline)
            if lineendmatch:
                hocrnew += hline + '\n'
                inline = False

        linematch = line_re.search(hline)
        if linematch:
            inline = True
            lid = linematch.group(1)
            if lid in lines:
                for w in lines[lid]['words']:
                    if 'idused' in w:
                        wid = w['id'] + '+really+' + w['idused']
                    else:
                        wid = w['id']
                    hocrnew += ("      <span class='ocrx_word' id='%s' "
                                "title='bbox %d %d %d %d; "
                                "x_wconf %d'>%s</span>\n"
                                % (wid, *w['bbox'], w['conf'],
                                   w['word']))
            elif debug:
                print('Line id %s not found in words' % lid)

    return hocrnew
