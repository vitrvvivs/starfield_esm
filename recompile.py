import struct
import zlib
import shutil
from pprint import pprint
from collections import OrderedDict
from struct import unpack

from config import STARFIELD_ESM, DB_DIR
from models.record import Record
from offsets import OffsetTree, iter_group_offsets, iter_record_offsets
from db import changed_files


ot = OffsetTree.load()


def save_to_esm(update_records: list[Record]):
    if len(update_records) == 0:
        print("Nothing to do")
        return

    # copy esm for backup
    orig_esm_path = STARFIELD_ESM.with_suffix(".esm.orig")
    if not orig_esm_path.exists():
        shutil.copy(STARFIELD_ESM, orig_esm_path)

    # get a list of size changes
    size_changes = []
    update_records.sort(key=lambda r: ot.get_formid(r.formid)[0])
    for r in update_records:
        start, end, parent, _ = ot.get_formid(r.formid)
        size_changes.append((start, end, parent, r))


    # convert to offset map
    # size_changes: (150, 200, +10), (300, 350, +10)
    # offset_map: {
    #   (0 - 150): (0 - 150),
    #   (150 - 210): Record,
    #   (210 - 310): (200 - 300),
    #   (310 - 370): Record,
    #   (370 - 520): (350 - 500)  }
    offset_map = OrderedDict()
    sumdiff = 0
    for start, end, parent, r in size_changes:
        rdiff = r.actual_size - r.size
        if len(offset_map.keys()) == 0:
            offset_map[(0, start)] = (0, start)
        else:
            prev_start, prev_end = list(offset_map.keys())[-1]
            offset_map[(prev_end, start+sumdiff)] = (prev_end-sumdiff, start)
        offset_map[(start+sumdiff, end+sumdiff+rdiff)] = r
        sumdiff += rdiff

    pprint(size_changes)
    total_size = ot.offsets[ot.starts[-1]].end
    prev_start, prev_end = list(offset_map.keys())[-1]
    offset_map[(prev_end, total_size+sumdiff)] = (prev_end-sumdiff, start-sumdiff)

    for k, v in offset_map.items():
        print([hex(x) for x in k], [hex(x) for x in v] if type(v) is tuple else v)
    print()

    # update GRUP sizes
    group_diffs = OrderedDict()
    for start, end, parent, r in size_changes:
        rdiff = r.actual_size - r.size
        group_diffs.setdefault(ot.get_formid(r.formid).parent, []).append(rdiff)

    sumdiff = 0
    overwrite_bytes = dict()
    for gstart, v in group_diffs.items():
        gnode = ot.offsets[gstart]
        goffset = gstart + sumdiff + 4
        gdiff = sum(v)
        gsize = gnode.end - gnode.start + gdiff
        overwrite_bytes[goffset] = struct.pack("I", gsize)
        sumdiff += gdiff

    # Write to file
    with orig_esm_path.open('rb') as orig_esm:
        with STARFIELD_ESM.open('r+b') as esm:
            for k, src in offset_map.items():
                start, end = k
                if start == 0: continue
                esm.seek(start)
                if isinstance(src, Record):
                    src.header = src.group.encode('ascii') + struct.pack("I", src.actual_size) + src.header[8:]
                    esm.write(src.header)
                    esm.write(src.raw_data)
                else:
                    src_start, src_end = src
                    orig_esm.seek(src_start)
                    i = start
                    while i < end:
                        esm.write(orig_esm.read(min(65536, end - i)))
                        i += 65536
            esm.seek(end)
            esm.truncate()
            for pos, byte in overwrite_bytes.items():
                esm.seek(pos)
                esm.write(byte)

    # check
    with STARFIELD_ESM.open('rb') as esm:
        for group, gstart, gend in iter_group_offsets(esm):
            s = esm.read(4).decode('ascii', 'ignore')


def recompile():
    changed_records = []
    for f in changed_files():
        record = Record.load(f)
        if record.originally_compressed:
            record.compress()
        changed_records.append(record)
    print(changed_records)
    save_to_esm(changed_records)


if __name__ == "__main__":
    recompile()