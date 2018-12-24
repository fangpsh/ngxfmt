#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'FPs'

import argparse
import shutil
import os
import sys

sys.setrecursionlimit(10000)

COLS = 120
INDENT_W = 2
SPACE_W = 1
NGX_BLOCKS = ["charset_map", "events", "geo", "http", "if",
              "limit_except", "location", "mail", "map",
              "match", "split_clients", "stream", "tcp",
              "types", "upstream"]
DUP_ITEM = ['server']


class Conf(object):
    def __init__(self, import_path, export_path):
        self.import_path = import_path
        self.export_path = export_path
        self.export_content = ''
        self.level = 0
        self.simple_buffer = []
        self.status = 'init'

    def _indent(self):
        return self.level * ' ' * INDENT_W

    @staticmethod
    def _split_line(line, words):
        if line == "":
            words.append('\n')
            return words
        w = ""
        i = 0
        while i < len(line):
            if line[i] == '#':
                words.append(line[i:-1])
                words.append('\n')
                break
            elif line[i] in ['\'', '\"']:
                end = line.find(line[i], i+1)
                if end == -1:
                    words.append(line[i])
                    i += 1
                else:
                    words.append(line[i:end+1])
                    i = end + 1
            elif line[i] in ['{', '}', ';']:
                if w != "":
                    words.append(w)
                    w = ""
                words.append(line[i])
                i += 1
            elif line[i] == ' ':
                if w != "":
                    words.append(w)
                    w = ""
                i += 1
            elif line[i] == '\n':
                if w != "":
                    words.append(w)
                    w = ""
                words.append('\n')
                i += 1
            elif line[i] in ['\t']:
                i += 1
            else:
                w += line[i]
                i += 1
        return words

    def _clear_simple_buffer(self):
        if len(self.simple_buffer) == 0:
            return
        if self.status == 'simple_end':
            self.export_content += '\n'

        max_w = max([len(w[0]) for w in self.simple_buffer])

        items_max_w = {}
        for w in self.simple_buffer:
            if w[0] not in items_max_w:
                items_max_w[w[0]] = [len(w[0])]
            for i in xrange(1, w.index(';')):
                if len(items_max_w[w[0]]) <= i:
                    items_max_w[w[0]].append(len(w[i]))
                else:
                    items_max_w[w[0]][i] = max(items_max_w[w[0]][i], len(w[i]))

        for index, w in enumerate(self.simple_buffer):
            num = w.index(';')
            # line feed
            if w[0] in ['log_format'] and num > 3:
                self.export_content += self._indent() + w[0].ljust(max_w) + SPACE_W*' ' + w[1] + SPACE_W*' ' + w[2]
                _w = self._indent() + ' '*max_w + SPACE_W*' ' + ' '*len(w[1]) + ' '*SPACE_W
                for i in xrange(3, num):
                    self.export_content += '\n' + _w + w[i]
            elif w[0] in ['server_name', 'charset_types', 'gzip_types'] and num > 4:
                self.export_content += self._indent() + w[0].ljust(max_w) + SPACE_W*' ' + w[1]
                _w = self._indent() + ' '*max_w + SPACE_W*' '
                for i in xrange(2, num):
                    self.export_content += '\n' + _w + w[i]
            else:
                justify = False
                if index > 0 and self.simple_buffer[index-1][0] == w[0]:
                    justify = True
                if index+1 < len(self.simple_buffer) and self.simple_buffer[index+1][0] == w[0]:
                    justify = True

                if justify:
                    self.export_content += self._indent() + w[0].ljust(max_w)
                    for i in xrange(1, num):
                        self.export_content += SPACE_W*' ' + w[i].ljust(items_max_w[w[0]][i])
                else:
                    self.export_content += self._indent() + w[0].ljust(max_w)
                    for i in xrange(1, num):
                        self.export_content += SPACE_W*' ' + w[i]

            self.export_content += ';'
            if w[-1][0] == '#':
                self.export_content += '  ' + w[-1]
            self.export_content += '\n'

        del self.simple_buffer[:]
        self.status = 'simple_end'

    def _parser_comment(self, comment):
        content = comment.lstrip('#').strip()
        i = 0
        while i < len(content):
            self.export_content += self._indent() + ('# ' + content[i:][0:(COLS-2)] + '\n')
            i += (COLS-2)
        self.status = "comment_end"

    def _parser_beg_block(self, words, comment):
        self.status = 'block_beg'
        self.export_content += self._indent() + words[0]
        for w in words[1:]:
            self.export_content += SPACE_W * ' ' + w
        if comment != "":
            self.export_content += SPACE_W * ' ' + comment

        self.export_content += '\n'
        self.level += 1

    def _parser_end_block(self):
        self.level -= 1
        self.export_content += self._indent() + '}' + '\n'
        self.status = 'block_end'

    def _parser_simple(self, words):
        self.simple_buffer.append(filter(lambda w: w != '\n', words))

    def _parser(self, words):
        if len(words) == 0:
            self._clear_simple_buffer()
            return
        elem = words[0]

        if 'by_lua' in elem and 'by_lua_file' not in elem:
            print 'NOT SUPPORT LUA BLOCK!!!'
            sys.exit()
        elif elem[0] == '#':
            if self.status == 'simple_end':
                self.export_content += '\n'
            self._clear_simple_buffer()
            self._parser_comment(words[0])
            words = words[2:]
        elif elem in ['\n', ';']:
            words.remove(elem)
            self._clear_simple_buffer()
        elif (elem in DUP_ITEM and words[1] == '{') or (elem in NGX_BLOCKS):
            if self.status in ['block_end', 'simple_end']:
                self.export_content += '\n'
            self._clear_simple_buffer()
            i = words.index('{')
            comment = ""
            if i+1 < len(words) and words[i+1][0] == '#':
                    comment = words[i+1]
                    words.remove(comment)
            self._parser_beg_block(words[0:i+1], comment)
            words = words[i+1:]
        elif elem == '}':
            self._clear_simple_buffer()
            words.remove(elem)
            self._parser_end_block()
        else:
            i = words.index(';')
            if i+1 < len(words) and words[i+1][0] == '#':
                i += 1
            if i+1 < len(words) and words[i+1][0] == '\n':
                i += 1
            self._parser_simple(words[0:i+1])
            words = words[i+1:]

        self._parser(words)

    def fmt(self):
        with open(self.import_path) as f:
            words = []
            while True:
                line = f.readline()
                if not line:
                    break
                words = self._split_line(line, words)

        self._parser(words)
        with open(self.export_path, 'w') as f:
            f.writelines(self.export_content)


def main():
    parser = argparse.ArgumentParser(prog='ngxfmt', description='nginx conf fmt tool')
    parser.add_argument('-f', action='store', metavar='nginx.conf', dest='conf_file', help='conf file')
    parser.add_argument('-d', action='store', metavar='conf.d', dest='conf_dir', help='conf directory')

    args = parser.parse_args()
    if args.conf_file is None and args.conf_dir is None:
        parser.print_help()
    if args.conf_file:
        fmt_file = args.conf_file+'.fmt'
        conf = Conf(args.conf_file, fmt_file)
        conf.fmt()
        print args.conf_file + ' -> ' + fmt_file
    if args.conf_dir:
        fmt_dir = args.conf_dir + '.fmt'
        shutil.copytree(args.conf_dir, fmt_dir)
        print args.conf_dir + ' -> ' + fmt_dir
        for root, dirs, files in os.walk(fmt_dir):
            for f in files:
                if os.path.splitext(f)[-1] != '.conf':
                    continue
                path = os.path.join(root, f)
                conf = Conf(path, path)
                conf.fmt()


if __name__ == "__main__":
    main()
