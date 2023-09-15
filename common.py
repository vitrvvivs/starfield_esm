from typing import Generator, Tuple, Any
from config import *
import json
from struct import unpack


index: dict[str, str] = {} #json.load((DB_DIR / "index.json").open('r'))
cached_files = {}


def db_load(filename: str) -> dict:
    if filename not in cached_files:
        cached_files[filename] = json.load((DB_DIR / filename).open('r'))
    return cached_files[filename]


def split_formid(s):
    sig_signame, s = s.split('[', 1)
    sig, signame = (x.strip() for x in sig_signame.split(' - ', 1))
    uid, s = s.split(']', 1)
    return sig, signame, uid


def walk_dict(d) -> Generator[Tuple[list[str], Any], None, None]:
    for outer_key, outer_value in d.items():
        if isinstance(outer_value, dict):
            for inner_key, inner_value in walk_dict(outer_value):
                yield ([outer_key] + inner_key, inner_value)
        else:
            yield ([outer_key], outer_value)


def int32(b: bytes, offset=0) -> int:
    return unpack("i", b[offset:offset+4])[0]
def uint32(b: bytes, offset=0) -> int:
    return unpack("I", b[offset:offset+4])[0]
def int16(b: bytes, offset=0) -> int:
    return unpack("h", b[offset:offset+2])[0]
def uint16(b: bytes, offset=0) -> int:
    return unpack("H", b[offset:offset+2])[0]

def cstr(b: bytes, length, offset=0) -> str:
    return unpack(str(length)+"s", b[offset:offset+length])[0][:-1].decode('ascii')

def bytes_from_str(s: str):
    return bytes.fromhex(s.replace(' ', ''))


def bytes_to_str(b: bytes, sep=' ', reverse=False):
    return sep.join(format(i, '02X') for i in b)


def uid_bytes_to_str(b: bytes):
    return bytes_to_str(b[::-1], '', True)


class Ref:
    def __init__(self, uid: bytes, uid_str=None):
        self.null = False
        if uid is None or uid == 0:
            self.null = True
        if uid_str:
            self.uid_str = uid_str
        elif type(uid) is bytes:
            self.uid_str = uid_bytes_to_str(uid)
        self.path = index.get(self.uid_str, "")
        self.group, self.edid = self.path.split('/', 1)
        self.edid = self.edid.replace('.json', '')

    @property
    def data(self):
        if self.null: return {}
        return db_load(self.path)

    def __repr__(self):
        if self.null:
            return f"Ref({self.uid_str} Null)"
        return f"Ref({self.uid_str} {self.group} {self.edid})"

    def __getitem__(self, item):
        return self.data.get(item)

    def __setitem__(self, key, value):
        self.data[key] = value

    @classmethod
    def from_formid_str(cls, formid_str: str):
        _, __, uid = split_formid(formid_str)
        return cls(b'', uid_str=uid)
