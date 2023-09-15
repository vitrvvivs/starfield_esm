from os import PathLike
from typing import Any, overload
from config import DB_DIR
from common import int16, int32, cstr, uint16
from struct import pack
import zlib


Group = str
EDID = str


class FormID(str):
    def __new__(cls, b: Any):
        if type(b) is bytes:
            return super().__new__(cls, ''.join(f"{i:02X}" for i in b[3::-1]))
        return super().__new__(cls, b)


class Record:
    def __init__(self, header: bytes, data: bytes = b'', edid_index={}) -> None:
        self.data = {}
        self.raw_data = data
        self.header = header
        self.group = header[0:4].decode('ascii')
        self.size = int32(header[4:8])
        self.formid = FormID(header[12:16])
        self.path = (DB_DIR / self.group / (self.formid + '.bin'))
        self.edid = edid_index.get(self.formid, "")
        self.originally_compressed = (self.header[10] & 4) > 0
        self.compressed = self.originally_compressed
        self.fields = []

        if data:
            self.parse(data)

    def parse(self, data: bytes | None = None) -> None:
        if data:
            self.raw_data = data
        self.decompress()
        self.parse_edid()

        fields = []
        i = 0
        size_override = 0
        while i < self.actual_size:
            field = self.raw_data[i:i+4].decode('ascii')
            size = uint16(self.raw_data[i+4:i+6]) + size_override
            value = self.raw_data[i+6:i+6+size]

            if field == 'XXXX':
                size_override = int32(value)
            else:
                size_override = 0
            fields.append((field, size, value))
            i += size + 6
        self.fields = fields

    def parse_edid(self) -> EDID:
        if self.raw_data[:4] == b'EDID':
            edid_len = int16(self.raw_data, 4)
            self.edid = cstr(self.raw_data, edid_len, 6)
        return self.edid

    @property
    def actual_size(self):
        return len(self.raw_data)

    def decompress(self):
        if self.compressed:
            expected_size = int32(self.raw_data[:4])
            self.raw_data = zlib.decompress(self.raw_data[4:])
            actual_size = len(self.raw_data)
            if actual_size != expected_size:
                print(f"Warning: decompression: from {self.size} to {actual_size} ({expected_size} expected)")
            self.compressed = False

    def compress(self):
        if not self.compressed:
            self.raw_data = pack("I", len(self.raw_data)) + zlib.compress(self.raw_data, 8)
            self.compressed = True

    def __repr__(self):
        return f"{self.group}({self.formid} {self.edid})"

    def __getitem__(self, item):
        return self.data.get(item)

    def __setitem__(self, key, value):
        self.data[key] = value

    @overload
    @classmethod
    def load(cls, path: str, edid_index={}) -> "Record": pass

    @overload
    @classmethod
    def load(cls, path: PathLike, edid_index={}) -> "Record": pass

    @classmethod
    def load(cls, group: str, formid: str | None = None) -> "Record":
        if isinstance(group, PathLike):
            path = group
        elif isinstance(group, str):
            if formid is None:
                group, formid = group.split('/', 1)
            path = (DB_DIR / group / (formid + '.bin'))
        with path.open('rb') as fd:
            header = fd.read(24)
            record = Record(header)
            record.raw_data = fd.read()
            record.compressed = False
        return record

    def save(self):
        with self.path.open('wb') as fd:
            fd.write(self.header)
            fd.write(self.raw_data)
