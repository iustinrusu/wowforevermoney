"""Minimal parser for Lua data literals (addon data files and SavedVariables).

Handles: tables ({...} with [key]=, name=, and positional values), strings ("..", '..', [[..]], [=[..]=]),
numbers (incl. hex and negative), true/false/nil, and -- / --[[ ]] comments.
Not a Lua interpreter: function calls and expressions are not supported.
"""
from __future__ import annotations

import re

_NUM = re.compile(r'-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)')
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_ESC = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', "'": "'", '\n': '\n', 'a': '\a', 'b': '\b',
        'f': '\f', 'v': '\v', '0': '\0'}


class LuaParseError(ValueError):
    pass


class _Parser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def ws(self):
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in ' \t\r\n,;':
                self.i += 1
            elif s.startswith('--', self.i):
                m = re.match(r'--\[(=*)\[', s[self.i:self.i + 20])
                if m:
                    end = s.find(']' + m.group(1) + ']', self.i)
                    self.i = n if end < 0 else end + len(m.group(1)) + 2
                else:
                    end = s.find('\n', self.i)
                    self.i = n if end < 0 else end + 1
            else:
                break

    def value(self):
        self.ws()
        if self.i >= self.n:
            raise LuaParseError('unexpected end of input')
        c = self.s[self.i]
        if c == '{':
            return self.table()
        if c in '"\'':
            return self.qstring(c)
        if c == '[' and re.match(r'\[=*\[', self.s[self.i:self.i + 10]):
            return self.lstring()
        m = _NUM.match(self.s, self.i)
        if m:
            self.i = m.end()
            t = m.group(0)
            if 'x' in t or 'X' in t:
                return int(t, 16)
            if re.fullmatch(r'-?\d+', t):
                return int(t)
            return float(t)
        m = _NAME.match(self.s, self.i)
        if m:
            self.i = m.end()
            word = m.group(0)
            if word == 'true':
                return True
            if word == 'false':
                return False
            if word == 'nil':
                return None
            raise LuaParseError(f'unsupported identifier {word!r} at {m.start()}')
        raise LuaParseError(f'unexpected {c!r} at {self.i}')

    def qstring(self, quote):
        s = self.s
        self.i += 1
        out = []
        while self.i < self.n:
            c = s[self.i]
            if c == quote:
                self.i += 1
                return ''.join(out)
            if c == '\\':
                nxt = s[self.i + 1]
                if nxt.isdigit():
                    m = re.match(r'\d{1,3}', s[self.i + 1:])
                    out.append(chr(int(m.group(0))))
                    self.i += 1 + len(m.group(0))
                    continue
                out.append(_ESC.get(nxt, nxt))
                self.i += 2
                continue
            out.append(c)
            self.i += 1
        raise LuaParseError('unterminated string')

    def lstring(self):
        m = re.match(r'\[(=*)\[', self.s[self.i:])
        close = ']' + m.group(1) + ']'
        start = self.i + len(m.group(0))
        end = self.s.find(close, start)
        if end < 0:
            raise LuaParseError('unterminated long string')
        self.i = end + len(close)
        text = self.s[start:end]
        return text[1:] if text.startswith('\n') else text

    def table(self):
        self.i += 1
        arr: list = []
        hsh: dict = {}
        while True:
            self.ws()
            if self.i >= self.n:
                raise LuaParseError('unterminated table')
            if self.s[self.i] == '}':
                self.i += 1
                break
            if self.s[self.i] == '[' and not re.match(r'\[=*\[', self.s[self.i:self.i + 10]):
                self.i += 1
                key = self.value()
                self.ws()
                if self.s[self.i] != ']':
                    raise LuaParseError(f'expected ] at {self.i}')
                self.i += 1
                self.ws()
                if self.s[self.i] != '=':
                    raise LuaParseError(f'expected = at {self.i}')
                self.i += 1
                hsh[key] = self.value()
                continue
            m = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)').match(self.s, self.i)
            if m:
                self.i = m.end()
                hsh[m.group(1)] = self.value()
                continue
            arr.append(self.value())
        if not hsh:
            return arr
        for idx, v in enumerate(arr, 1):
            hsh[idx] = v
        n = len(hsh)
        if all(isinstance(k, int) and not isinstance(k, bool) for k in hsh) and set(hsh) == set(range(1, n + 1)):
            return [hsh[i] for i in range(1, n + 1)]     # Lua array written with explicit [1]=, [2]= keys
        return hsh


def parse_value(text: str):
    return _Parser(text).value()


def parse_assignments(text: str) -> dict:
    """Parse `name = <literal>` / `ns.Name = <literal>` statements (SavedVariables, generated data files)."""
    out: dict = {}
    for m in re.finditer(r'^(?:local\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?=[{"\'\[\-0-9tfn])', text, re.M):
        name = m.group(1).split('.')[-1]
        p = _Parser(text)
        p.i = m.end()
        try:
            out[name] = p.value()
        except LuaParseError:
            continue
    return out
