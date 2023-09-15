import pickle
import sys

from typing import IO, Generator, Tuple, Optional
from struct import unpack
from collections import namedtuple, OrderedDict
from itertools import islice
from pprint import pprint
import zlib
import bisect

from config import *
from common import int32
from models.record import Record, FormID


Signature = bytes
Group = str
EDID = bytes


def iter_group_offsets(esm: IO) -> Generator[Tuple[Group, int, int], None, None]:
    offset = 0
    while True:
        esm.seek(offset)
        header_data = esm.read(24)
        if header_data == b'': break

        sig = header_data[0:4]
        size = int32(header_data[4:8])

        if sig == b'TES4':
            offset += 24
        if sig == b'GRUP':
            group = header_data[8:12].decode('ascii', 'ignore')
            yield group, offset, offset+size
        offset += size


def iter_record_offsets(group: Group, start: int, end: int, esm: IO) -> Generator[Tuple[FormID, int, int], None, None]:
    offset = start
    while offset < end:
        esm.seek(offset)
        header = esm.read(24)
        record = Record(header, b'')

        if record.group != group:
            print("Error: record doesn't match group:", record.group, group, header)
            break

        yield record.formid, offset, offset+24+record.size
        offset += record.size + 24


def iter_offsets(fd: Optional[IO]=None) -> Generator[Tuple[str, str, int, int], None, None]:
    if fd is None:
        fd = STARFIELD_ESM.open('rb')

    with fd as esm:
        for group, gstart, gend in iter_group_offsets(esm):
            yield ("group", group, gstart, gend)
            for formid, rstart, rend in iter_record_offsets(group, gstart+24, gend, esm):
                yield ("record", formid, rstart, rend)


OffsetNode = namedtuple('OffsetNode', ['start', 'end', 'parent', 'names'])


class OffsetTree:
    filename = DB_DIR / 'OffsetTree.pickle'

    def __init__(self):
        self.offsets: dict[int, OffsetNode] = OrderedDict()
        self.index: dict[str, int] = dict()
        self.starts: list[int] = []  # list for bisection

    @classmethod
    def create(cls):
        self = cls()
        with STARFIELD_ESM.open('rb') as esm:
            for group, gstart, gend in iter_group_offsets(esm):
                self.offsets[gstart] = OffsetNode(gstart, gend, 0, [group])
                for formid, mstart, mend in iter_record_offsets(group, gstart+24, gend, esm):
                    self.offsets[mstart] = OffsetNode(mstart, mend, gstart, [formid])
                    self.index[formid] = mstart
        return self

    def add_node(self, start: int, end: int, parent_node: OffsetNode | None, names: list[str]) -> OffsetNode:
        if parent_node is not None:
            parent = parent_node.start
        else:
            parent = 0
        node = OffsetNode(start, end, parent, names)
        self.offsets[start] = node
        self.index[names[0]] = start
        return node

    def sort(self):
        self.starts = sorted(self.offsets.keys())

    def save(self):
        pickle.dump(self, self.filename.open('wb'))

    @classmethod
    def load(cls, flush_cache=False):
        self = cls()
        if flush_cache or not self.filename.exists():
            self = self.create()
            self.save()
        else:
            self = pickle.load(cls.filename.open('rb'))
        return self

    def search(self, offset: int) -> list[str]:
        i = bisect.bisect_left(list(self.offsets.keys()), offset)
        names = []
        node = list(self.offsets.values())[i-1]
        while node:
            names += node.names
            node = self.offsets.get(node.parent)
        names.reverse
        return names

    def get_formid(self, formid: str):
        return self.offsets[self.index[formid]]


if __name__ == "__main__":
    flush_cache = False
    if flush_cache or not OffsetTree.filename.exists():
        ot = OffsetTree.create()
        ot.save()
    else:
        ot = OffsetTree.load()
    if len(sys.argv) > 1:
        print(ot.search(int(sys.argv[1])))
        sys.exit(0)

