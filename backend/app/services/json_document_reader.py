"""Read selected JSON containers incrementally without a whole-document DOM.

The standard decoder still checks every value. A row may then pass through its
ordinary JSON model validator before the next row is read. Working text grows
with the largest individual value, not the total size of a product array.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any, TextIO

from pydantic_core import from_json


class JsonDocumentReader:
    def __init__(self, source: TextIO, *, chunk_size: int = 64 * 1024):
        if chunk_size < 1:
            raise ValueError('chunk_size must be positive')
        self.source, self.chunk_size = source, chunk_size
        self.buffer, self.position, self.eof = '', 0, False
        self.decoder = json.JSONDecoder()
        self.read_seconds = 0.0

    def _fill(self):
        self.buffer = self.buffer[self.position:]
        self.position = 0
        started = perf_counter()
        try:
            chunk = self.source.read(self.chunk_size)
        finally:
            self.read_seconds += perf_counter()-started
        self.buffer += chunk
        self.eof = not chunk

    def peek(self):
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position] in ' \t\r\n':
                self.position += 1
            if self.position < len(self.buffer):
                return self.buffer[self.position]
            if self.eof:
                return ''
            self._fill()

    def take(self, character):
        if self.peek() != character:
            raise ValueError(f'Invalid JSON: expected {character!r}')
        self.position += 1

    def value(self, validate_json: Callable[[str], Any] | None = None):
        self.peek()
        while True:
            try:
                _value, end = self.decoder.raw_decode(self.buffer,self.position)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self._fill()
                continue
            del _value
            # A number can continue in the next chunk (1 / 2, 1e / +2).
            # Demand its complete JSON delimiter before accepting this value.
            if not self.eof and (end == len(self.buffer) or self.buffer[end] not in ' \t\r\n,]}:'):
                self._fill()
                continue
            raw = self.buffer[self.position:end]
            self.position = end
            # The decoder locates one row. Native JSON parsing still decides
            # accepted syntax (including invalid Unicode), as for whole-file
            # validation; Python's decoder alone accepts lone surrogates.
            return validate_json(raw) if validate_json else from_json(raw)

    def object(self, fields: Mapping[str, Callable[[], Any]]):
        if self.peek() != '{':
            return self.value()  # Let the ordinary model reject a wrong shape.
        self.take('{')
        result = {}
        if self.peek() == '}':
            self.take('}')
            return result
        while True:
            key = self.value()
            if not isinstance(key,str):
                raise json.JSONDecodeError('Object key must be a string',self.buffer,self.position)
            self.take(':')
            result[key] = fields[key]() if key in fields else self.value()
            if self.peek() == '}':
                self.take('}')
                return result
            self.take(',')
            # No trailing comma: the next iteration must decode a key.

    def array(self, row: Callable[[], Any]):
        if self.peek() != '[':
            return self.value()
        self.take('[')
        result = []
        if self.peek() == ']':
            self.take(']')
            return result
        while True:
            result.append(row())
            if self.peek() == ']':
                self.take(']')
                return result
            self.take(',')

    def finish(self):
        if self.peek():
            raise ValueError('Invalid JSON: trailing content')
