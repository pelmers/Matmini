#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
matmini.py
Minify Matlab code
'''

import re, sys, os.path
from itertools import permutations
alphabet = 'abcdefghijklmnopqrstuvwxyz'
alphabet = set(alphabet + alphabet.upper())
symbols = {"'",'~','.','=',',','/','+','*','^','(',')',';','[',']','-',':','@','\\','{','}'}
keywords = {'break','case','catch','classdef','continue','else','elseif',
        'end','for','function','global','if','otherwise','parfor',
        'persistent','return','spmd','switch','try','while'}

def extract_strings(code_lines):
    # should be more clever about determining if it's string or transpose
    strings = []
    for i, line in enumerate(code_lines):
        # non-greedily match everything between single quotes
        matches = re.findall(r"'(.*?)'", line)
        for match in matches:
            # try determine if each match really is a string
            if all((m in symbols) for m in match) or match[0] in {' ',','}:
                # either just a bunch of symbols or probably is transpose
                continue
            strings.append(match)
            code_lines[i] = code_lines[i].replace(match,"'%d'"%(len(strings)-1))
    print "Found strings: ", strings
    return strings

def inject_strings(code_lines, strings):
    n = 0
    for i, s in enumerate(strings):
        while "'%d'" % i not in code_lines[n]:
            if n == len(code_lines) - 1: break
            n += 1
        code_lines[n] = code_lines[n].replace("'%d'" % i, strings[i])

def decomment(code_lines):
    # strip comments (everything after % unless % is in format string)
    return [l.split(r'%')[0] if 'printf' not in l else l for l in code_lines]

def cleanup(code_lines):
    # multi-statement lines will confuse lexer, so disambiguate them
    parsed_lines = []
    for l in code_lines:
        in_parens = 0
        prev = 0
        for i, s in enumerate(l):
            if s in {'[','('}:
                in_parens += 1
            elif s in {')',']'}:
                in_parens -= 1
            elif (s == ',' and in_parens == 0) or s == ';':
                # split line here
                parsed_lines.append(l[prev:i+1])
                prev = i+1
        parsed_lines.append(l[prev:])
    # strip whitespace and trailing commas
    return [l.strip().rstrip(',') for l in parsed_lines if l.strip()]

def symbols_to_spaces(code):
    return ''.join([c if c not in symbols else ' ' for c in code])

def find_names(code_lines):
    # return a set of the variables used in the matlab file
    names = set([])
    for line in code_lines:
        if line.startswith('function'):
            # add function name and arguments to names
            line = line.lstrip('function').lstrip()
            if len(line.split('=')) == 2:
                left, right = line.split('=')
                names.update(set(symbols_to_spaces(left).split()))
                names.update(set(symbols_to_spaces(right).split()))
            else:
                names.update(set(symbols_to_spaces(line).split()))
        elif line.startswith('for'):
            line = line.lstrip('for').lstrip()
            if len(line.split('=')) == 2:
                left = line.split('=')[0]
                names.update(set(symbols_to_spaces(left).split()))
        else:
            if len(line.split('=')) == 2:
                left = line.split('=')[0]
                if '(' in left and ')' in left:
                    # take out everything between parens
                    left = ' '.join([left[:left.find('(')],
                        left[left.rfind(')')+1:]])
                names.update(set(symbols_to_spaces(left).split()))
    names = {n for n in names if not n.isdigit()}.difference(keywords)
    return names

def map_names(names, valid_chars, length = 1):
    # map variables names to their minified versions
    p = length
    m = None
    mapping = {}
    perms = permutations(valid_chars, p)
    for n in names:
        tries = 0
        while (not m) or (m in names) or (m in mapping.values()) or (
                not m[0] in alphabet) or (m in keywords):
            if tries >= 2:
                perms = permutations(alphabet, 1)
                print "Not enough valid characters, continuing with default."
            try:
                m = ''.join(next(perms))
            except StopIteration:
                tries += 1
                p += 1
                perms = permutations(valid_chars, p)
        mapping[n] = m
        m = not m
    print "Variable mapping:", mapping
    return mapping

def find_name(name, line):
    # return the index of the name in line if it's used there, else -1
    if name not in line:
        return -1
    if name == line:
        return 0
    ind = line.find(name)
    if ind == 0:
        # at the start of the line
        if line[ind+len(name)] in symbols or line[ind+len(name)] == ' ':
            return ind
        return len(name)+find_name(name, line[ind+len(name):])
    elif ind+len(name) == len(line):
        # at the end of the line
        if line[ind-1] in symbols or line[ind-1] == ' ':
            return ind
    else:
        if ((line[ind+len(name)] in symbols or line[ind+len(name)] == ' ') and
                (line[ind-1] in symbols or line[ind-1] == ' ')):
            return ind
        return ind+len(name)+find_name(name, line[ind+len(name):])

def minify_join(lines):
    # make everything one line
    #return '\n'.join(lines)
    m = [l + ',' if l[-1] != ';' else l for l in lines]
    for i in range(1, len(m)):
        if m[i].startswith('function'):
            m[i-1] = m[i-1][:-1]
        elif i == len(m)-1:
            m[i] = m[i][:-1]
    return ' '.join(m)

def minify(lines, valid_chars, length = 1):
    lines = decomment(lines)
    strings = extract_strings(lines)
    lines = cleanup(lines)
    mapping = map_names(find_names(lines), valid_chars, length)
    minified = []
    for line in lines:
        stripped = symbols_to_spaces(line)
        for name in stripped.split():
            if name in mapping:
                line = ''.join([line[:find_name(name, line)],
                    mapping[name], line[find_name(name, line)+len(name):]])
        minified.append(line)
    inject_strings(minified, strings)
    return minify_join(minified)

def minify_file(filename, valid_chars, length):
    with open(filename) as f:
        m = minify(f.readlines(), valid_chars, length)
        out = m[m.find('function')+9:m.find(',')].strip() + '.m'
        with open(out, 'w') as o:
            o.write(m)
            print "Written to",out

def main():
    valid_chars = alphabet
    # show help
    if len(sys.argv[1:]) == 0 or '-h' in sys.argv[1:]:
        print "matmini.py [files] -l [min. var length] --alpha [valid chars]"
        return
    # set the length
    arg = ''.join(sys.argv[1:])
    length = arg[arg.find('-l')+2:].split()[0]
    length = int(length) if length.isdigit() else 1
    # set valid_chars
    if '--alpha' in sys.argv[1:]:
        valid_chars = [c for c in sys.argv[sys.argv.index('--alpha')+1]]
        #valid_chars = list(set(sys.argv[sys.argv.index('--alpha')+1]))
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            minify_file(arg, valid_chars, length)

if __name__ == '__main__':
    main()
