# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Nick Lanham <nick@afternight.org>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import re
from collections import deque
from unicodedata import normalize as ud_normalize
from unicodedata import east_asian_width

import deluge.common


def format_speed(speed):
    if speed > 0:
        return deluge.common.fspeed(speed)
    else:
        return '-'


def format_time(time):
    if time > 0:
        return deluge.common.ftime(time)
    else:
        return '-'


def format_date(time):
    if time > 0:
        return deluge.common.fdate(time)
    else:
        return ''


def format_date_never(time):
    if time > 0:
        return deluge.common.fdate(time)
    else:
        return 'Never'


def format_float(x):
    if x < 0:
        return '-'
    else:
        return '%.3f' % x


def format_seeds_peers(num, total):
    return '%d (%d)' % (num, total)


def format_progress(perc):
    if perc < 100:
        return '%.2f%%' % perc
    else:
        return '100%'


def format_pieces(num, size):
    return '%d (%s)' % (num, deluge.common.fsize(size))


def format_priority(prio):
    if prio == - 2:
        return '[Mixed]'
    if prio < 0:
        return '-'
    pstring = deluge.common.FILE_PRIORITY[prio]
    if prio > 0:
        return pstring[:pstring.index('Priority') - 1]
    else:
        return pstring


def trim_string(string, w, have_dbls):
    if w <= 0:
        return ''
    elif w == 1:
        return u' '
    elif have_dbls:
        # have to do this the slow way
        chrs = []
        width = 4
        idx = 0
        while width < w:
            chrs.append(string[idx])
            if east_asian_width(string[idx]) in ['W', 'F']:
                width += 2
            else:
                width += 1
            idx += 1
        if width != w:
            chrs.pop()
            chrs.append('.')
        return u'%s ' % (''.join(chrs))
    else:
        return u'%s ' % (string[0:w - 1])


def format_column(col, lim):
    dbls = 0
    # Chosen over isinstance(col, unicode) and col.__class__ == unicode
    # for speed - it's ~3 times faster for non-unicode strings and ~1.5
    # for unicode strings.
    if col.__class__ is unicode:
        # might have some double width chars
        col = ud_normalize('NFC', col)
        dbls = sum(east_asian_width(c) in 'WF' for c in col)
    size = len(col) + dbls
    if size >= lim - 1:
        return trim_string(col, lim, dbls > 0)
    else:
        return '%s%s' % (col, ' ' * (lim - size))


def format_row(row, column_widths):
    return ''.join([format_column(row[i], column_widths[i]) for i in range(0, len(row))])


_strip_re = re.compile('\\{!.*?!\\}')
_format_code = re.compile(r'\{\|(.*)\|\}')


def remove_formatting(string):
    return re.sub(_strip_re, '', string)


def wrap_string(string, width, min_lines=0, strip_colors=True):
    """
    Wrap a string to fit in a particular width.  Returns a list of output lines.

    :param string: str, the string to wrap
    :param width: int, the maximum width of a line of text
    :param min_lines: int, extra lines will be added so the output tuple contains at least min_lines lines
    :param strip_colors: boolean, if True, text in {!!} blocks will not be considered as adding to the
                              width of the line.  They will still be present in the output.
    """
    ret = []
    s1 = string.split('\n')
    indent = ''

    def insert_clr(s, offset, mtchs, clrs):
        end_pos = offset + len(s)
        while mtchs and (mtchs[0] <= end_pos) and (mtchs[0] >= offset):
            mtc = mtchs.popleft() - offset
            clr = clrs.popleft()
            end_pos += len(clr)
            s = '%s%s%s' % (s[:mtc], clr, s[mtc:])
        return s

    for s in s1:
        offset = 0
        indent = ''
        m = _format_code.search(remove_formatting(s))
        if m:
            if m.group(1).startswith('indent:'):
                indent = m.group(1)[len('indent:'):]
            elif m.group(1).startswith('indent_pos:'):
                begin = m.start(0)
                indent = ' ' * begin
            s = _format_code.sub('', s)

        if strip_colors:
            mtchs = deque()
            clrs = deque()
            for m in _strip_re.finditer(s):
                mtchs.append(m.start())
                clrs.append(m.group())
            cstr = _strip_re.sub('', s)
        else:
            cstr = s

        def append_indent(l, string, offset):
            """Prepends indent to string if specified"""
            if indent and offset != 0:
                string = indent + string
            l.append(string)

        while cstr:
            # max with for a line. If indent is specified, we account for this
            max_width = width - (len(indent) if offset != 0 else 0)
            if len(cstr) < max_width:
                break
            sidx = cstr.rfind(' ', 0, max_width - 1)
            sidx += 1
            if sidx > 0:
                if strip_colors:
                    to_app = cstr[0:sidx]
                    to_app = insert_clr(to_app, offset, mtchs, clrs)
                    append_indent(ret, to_app, offset)
                    offset += len(to_app)
                else:
                    append_indent(ret, cstr[0:sidx], offset)
                cstr = cstr[sidx:]
                if not cstr:
                    cstr = None
                    break
            else:
                # can't find a reasonable split, just split at width
                if strip_colors:
                    to_app = cstr[0:width]
                    to_app = insert_clr(to_app, offset, mtchs, clrs)
                    append_indent(ret, to_app, offset)
                    offset += len(to_app)
                else:
                    append_indent(ret, cstr[0:width], offset)
                cstr = cstr[width:]
                if not cstr:
                    cstr = None
                    break
        if cstr is not None:
            to_append = cstr
            if strip_colors:
                to_append = insert_clr(cstr, offset, mtchs, clrs)
            append_indent(ret, to_append, offset)

    if min_lines > 0:
        for i in range(len(ret), min_lines):
            ret.append(' ')

    # Carry colors over to the next line
    last_color_string = ''
    for i, line in enumerate(ret):
        if i != 0:
            ret[i] = '%s%s' % (last_color_string, ret[i])

        colors = re.findall('\\{![^!]+!\\}', line)
        if colors:
            last_color_string = colors[-1]

    return ret


def strwidth(string):
    """
    Measure width of a string considering asian double width characters
    """
    if not isinstance(string, unicode):
        string = unicode(string, 'utf-8')
    return sum([1 + (east_asian_width(char) in ['W', 'F']) for char in string])


def pad_string(string, length, character=' ', side='right'):
    """
    Pad string with specified character to desired length, considering double width characters.
    """
    w = strwidth(string)
    diff = length - w
    if side == 'left':
        return '%s%s' % (character * diff, string)
    elif side == 'right':
        return '%s%s' % (string, character * diff)


def delete_alt_backspace(input_text, input_cursor, sep_chars=' *?!._~-#$^;\'"/'):
    """
    Remove text from input_text on ALT+backspace
    Stop removing when countering any of the sep chars
    """
    deleted = 0
    seg_start = input_text[:input_cursor]
    seg_end = input_text[input_cursor:]
    none_space_deleted = False  # Track if any none-space characters have been deleted

    while seg_start and input_cursor > 0:
        if (not seg_start) or (input_cursor == 0):
            break
        if deleted and seg_start[-1] in sep_chars:
            if seg_start[-1] == ' ':
                if seg_start[-2] == ' ' or none_space_deleted is False:
                    # Continue as long as:
                    # * next char is also a space
                    # * no none-space characters have been deleted
                    pass
                else:
                    break
            else:
                break

        if not none_space_deleted:
            none_space_deleted = seg_start[-1] != ' '
        seg_start = seg_start[:-1]
        deleted += 1
        input_cursor -= 1

    input_text = seg_start + seg_end
    return input_text, input_cursor
