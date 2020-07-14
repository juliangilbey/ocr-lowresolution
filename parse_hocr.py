#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This takes an hOCR output from tesseract and the input image,
and parses the hOCR file to produce a list of words identified.
"""

import sys
import re
import os
from html.parser import HTMLParser
from lxml import etree

# Magic constant: confidence penalty for a non-dictionary word
nondictpenalty = 30

bbox_plain_re = re.compile(r'bbox (\d+) (\d+) (\d+) (\d+)')
bbox_word_re = re.compile(r'bbox (\d+) (\d+) (\d+) (\d+); x_wconf (\d+)$')
puncs = []
dictionary = set()
datapath = os.path.dirname(os.path.abspath(__file__))


def parse_plain_bboxdata(data):
    """The bboxdata elements are in the order: ulx, uly, lrx, lry[;...]"""

    m = bbox_plain_re.match(data)
    if m:
        return ([int(m.group(1)), int(m.group(2)), int(m.group(3)),
                 int(m.group(4))], None)
    else:
        return (None, 'Could not parse bbox data: %s\n' % data)


def parse_word_bboxdata(data):
    """The bboxdata elements are in the order: ulx, uly, lrx, lry; conf"""

    m = bbox_word_re.match(data)
    if m:
        return ([int(m.group(1)), int(m.group(2)), int(m.group(3)),
                 int(m.group(4))], int(m.group(5)), None)
    else:
        return (None, 0, 'Could not parse bbox data: %s\n' % data)


class hOCRParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.inword = False
        self.bboxdata = None
        self.word = None
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            for attr in attrs:
                if attr[0] == 'class':
                    if attr[1] == 'ocrx_word':
                        self.inword = True
                elif attr[0] == 'title':
                    bboxdata = attr[1]
            if self.inword and bboxdata:
                self.bboxdata = parse_word_bboxdata(bboxdata)[0:2]

    def handle_endtag(self, tag):
        if tag == 'span' and self.inword:
            if self.bboxdata[0] is not None:
                self.words.append({'word': self.word,
                                   'bbox': self.bboxdata[0],
                                   'conf': self.bboxdata[1]})
            self.inword = False
            self.bboxdata = None
            self.word = None

    def handle_data(self, data):
        if self.inword:
            self.word = data


def process_etree(root):
    """Take the rooted hOCR tree, and extract the OCR information

    The output is a simplified tree in the form of nested lists.

    We assume that the output is for a single page.
    """

    err = ''
    page = {'areas': []}

    # root[0] = <head>...
    # root[1] = <body>...
    body = root[1]
    ocrpage = body[0]
    pageclass = ocrpage.get('class')
    if pageclass != 'ocr_page':
        err = 'body[0] is not an ocr_page div\n'
        return (page, err)
    for a in ocrpage:
        # these should be ocr_carea divs
        aclass = a.get('class')
        aid = a.get('id')
        if aclass != 'ocr_carea':
            err += ('expected ocr_carea class, got %s, at id %s\n'
                    % (aclass, aid))
            continue
        (bbox, berr) = parse_plain_bboxdata(a.get('title'))
        if berr is not None:
            err += 'Failed to parse bbox at id %s: %s' % (aid, berr)
            continue
        area = {'id': aid, 'bbox': bbox, 'pars': []}
        for p in a:
            # these should be ocr_par <p>s
            pclass = p.get('class')
            pid = p.get('id')
            if pclass != 'ocr_par':
                err += ('expected ocr_par class, got %s, at id %s\n'
                        % (pclass, pid))
                continue
            (bbox, berr) = parse_plain_bboxdata(a.get('title'))
            if berr is not None:
                err += 'Failed to parse bbox at id %s: %s' % (pid, berr)
                continue
            par = {'id': pid, 'bbox': bbox, 'lines': []}
            for l in p:
                # these should be ocr_line or ocr_caption or ocr_textfloat
                # <span>s
                lclass = l.get('class')
                lid = l.get('id')
                # see GetHOCRText in src/api/hocrrenderer.cpp
                if lclass not in ['ocr_line', 'ocr_caption',
                                  'ocr_textfloat', 'ocr_header']:
                    err += ('expected ocr_line class, got %s, at id %s\n'
                            % (lclass, lid))
                    continue
                (bbox, berr) = parse_plain_bboxdata(l.get('title'))
                if berr is not None:
                    err += 'Failed to parse bbox at id %s: %s' % (pid, berr)
                    continue
                line = {'id': lid, 'bbox': bbox, 'words': []}
                for w in l:
                    # these should be ocrx_word spans
                    wclass = w.get('class')
                    wid = w.get('id')
                    if wclass != 'ocrx_word':
                        err += ('expected ocrx_word class, got %s, at id %s\n'
                                % (wclass, wid))
                        continue
                    (bbox, conf, berr) = parse_word_bboxdata(w.get('title'))
                    if berr is not None:
                        err += ('Failed to parse bbox and conf at id %s: %s'
                                % (pid, berr))
                        continue
                    wtext = w.xpath("string()")
                    word = {'id': wid, 'bbox': bbox, 'conf': conf,
                            'word': wtext}
                    line['words'].append(word)
                par['lines'].append(line)
            area['pars'].append(par)
        page['areas'].append(area)

    return (page, err)


def calculate_modconf_60(conf):
    """Calculate a more realistic confidence score based on the confidence.

    Tesseract does not estimate its confidence so well for low
    resolution images.  This function outputs a modified confidence score
    which more reasonably estimates the confidence of the word.

    This function was derived empirically from a large amount of data
    at 60 dpi; there is a lot of variation, and this is just
    a rough approximation, so is good enough.
    """

    if conf < 80:
        return int(0.5 * conf + 30)
    else:
        return int(1.7 * conf - 65)


def calculate_modconf_75(conf):
    """Calculate a more realistic confidence score based on the confidence.

    This is the same as calculate_modconf_60 but for 75 dpi images.
    """

    if conf < 84:
        return int(0.7 * conf + 20)
    else:
        return int(1.6 * conf - 55)


def tidy_ocr_page(page, resolution=60, tag_ids=False, tag_id=None):
    """Take output from process_etree, and make a copy with whitespace removed

    The original tree is left untouched.

    Inputs:
        page: output from process_etree
        resolution: resolution of the image; this is used to calculate
            the modconf values
        tags_ids: boolean; whether to tag ids with filename
        tag_id: override the filename with this string

    Output:
        a tidied tree

    We assume that the input is in the same form as the output of
    process_etree; this includes the output being a single page.

    If tag_ids is set to True, then the id attrib is set to fn:id throughout,
    so that the source of each word can be tracked.  This is only done if
    page has a 'fn' element.

    An extra step is to look up the word in a dictionary.  We create
    a new dict value: w['dictconf'], which equals w['conf'] if the
    word appears in the dictionary, but w['conf'] - 20 (min 0) if not.
    This way, we are more inclined to accept a dictionary word than a
    non-dictionary word.

    We also calculate a modified confidence, stored as w['modconf'].
    This is an empirically derived confidence based on the original
    confidence level, as tesseract consitently overestimates its
    confidence.  We currently do not calculate w['moddictconf'],
    though it would be easy to do so.  To do this,
    """

    if not dictionary:
        for word in open(os.path.join(datapath, 'british-english-large')):
            dictionary.add(word.strip().lower())

    page2 = page.copy()
    if 'filename' in page:
        if tag_id is None:
            tag_id = page['filename']
    elif tag_id is None:
        tag_ids = False
    page2['areas'] = []

    for ia in range(len(page['areas'])):
        a = page['areas'][ia]
        a2 = page['areas'][ia].copy()
        a2['pars'] = []
        if tag_ids:
            a2['id'] = tag_id + '+' + a['id']
        for ip in range(len(a['pars'])):
            p = a['pars'][ip]
            p2 = a['pars'][ip].copy()
            p2['lines'] = []
            if tag_ids:
                p2['id'] = tag_id + '+' + p['id']
            for il in range(len(p['lines'])):
                ln = p['lines'][il]
                ln2 = p['lines'][il].copy()
                ln2['words'] = []
                if tag_ids:
                    ln2['id'] = tag_id + '+' + ln['id']
                for iw in range(len(ln['words'])):
                    w = ln['words'][iw]
                    w2 = ln['words'][iw].copy()
                    if tag_ids:
                        w2['id'] = tag_id + '+' + w['id']
                    wd = w['word'].strip()
                    if wd != '':
                        w2['word'] = wd
                        if trimword(wd) in dictionary:
                            w2['dictconf'] = w2['conf']
                        else:
                            w2['dictconf'] = \
                                max(w2['conf'] - nondictpenalty, 0)
                        if resolution == 60:
                            w2['modconf'] = calculate_modconf_60(w2['conf'])
                        elif resolution == 75:
                            w2['modconf'] = calculate_modconf_75(w2['conf'])
                        else:
                            w2['modconf'] = w2['conf']
                        ln2['words'].append(w2)
                if len(ln2['words']) > 0:
                    p2['lines'].append(ln2)
            if len(p2['lines']) > 0:
                a2['pars'].append(p2)
        if len(a2['pars']) > 0:
            page2['areas'].append(a2)

    return page2


def trimword(w):
    """Remove leading or trailing punctuation from a word, and lower() it

    Sometimes words end in a full stop, for example, and then it won't
    be found in the dictionary.  If we remove those, then we can be
    more confident about whether we have a good word.

    Tesseract includes just what we need: eng.punc lists lots of known
    punctuation patterns, so we will use this.  Just a couple of small
    tweaks made to it to give our version (removing the punctuation-less
    initial entry, and removing the trailing spaces in the pattern
    '_!!!)__' where underscore indicates a trailing space).
    """

    if not puncs:
        for pat in open(os.path.join(datapath, 'eng.punc')):
            # trailing spaces are significant in this file, so only
            # strip newline characters
            pat = pat.replace('\n', '')
            # for some reason, re.escape escapes spaces
            pat = pat.replace(' ', 'X')
            pat = re.escape(pat)
            pat = pat.replace('X', r'(\w+)')
            puncs.append(re.compile(pat + '$'))

    for pat in puncs:
        m = pat.match(w)
        if m:
            return m.group(1).lower()

    return w.lower()


def ocr_page_to_text(page):
    """Turn a structured page into plain text"""

    text = ''

    for a in page['areas']:
        for p in a['pars']:
            for ln in p['lines']:
                line = ''
                for w in ln['words']:
                    if line == '':
                        line = w['word']
                    else:
                        line += ' ' + w['word']
                text += line + '\n'
            text += '\n'

    # remove final extra newline
    return text[:-1]


def parse_hocr_file(fn, resolution=60):
    """Parse an hOCR file, and return the parsed object if successful

    This function should be given the full pathname of the hOCR relative
    to the current working directory or an absolute pathname.
    """

    raw_parsed = etree.parse(fn)
    (tree, err) = process_etree(raw_parsed.getroot())

    if err != '':
        print('There were some parsing errors - expect problems ahead:\n%s' %
              err, file=sys.stderr)

    # keep hold of the filename
    tree['filename'] = fn

    tidied = tidy_ocr_page(tree, resolution=resolution, tag_ids=True)

    return tree, tidied
