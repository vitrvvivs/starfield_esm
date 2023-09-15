import struct
import zlib
import shutil
from pprint import pprint
from collections import OrderedDict
from struct import unpack

from config import STARFIELD_ESM, DB_DIR
from models.record import Record
from offsets import OffsetTree, iter_group_offsets, iter_record_offsets
from db import load_indices
from common import *


index, edids = load_indices()
pndt = Record.load(index["JaffaVI-cPlanetData"])
print(pndt)
pndt.parse()

biom = Record.load(index["FrozenNoLife11"])
biom.parse()

pccc = b''
for k, _, v in pndt.fields:
    if k == 'PCCC':
        continue
        pccc = v
    if k == 'RSCS':
        print(bytes_to_str(v))

fields = []
i = 0
while i < len(pccc):
    k = pccc[i:i+4]
    size = int32(pccc[i+4:i+8])
    v = pccc[i+8:i+8+size]

    if k == b'LIST':
        print(int32(v), len(v.split(b'\x00')))

    print(k, size, v)
    i += size + 8

#pprint(pndt.fields)
ot = OffsetTree.load()