import time
from typing import Tuple

from config import *
from models.record import Record, FormID, Group, EDID
from offsets import iter_offsets, OffsetTree
import json

_edid_index_path = DB_DIR / "index.json"
Group_FormID = str


def last_created():
    return int((DB_DIR / "timestamp").open('r').read())


def changed_files():
    then = last_created()
    for dir in DB_DIR.iterdir():
        if not dir.is_dir(): continue
        for f in dir.iterdir():
            if not f.suffix == ".bin": continue
            mtime = f.stat().st_mtime
            if mtime > then:
                yield f


def load_indices() -> Tuple[dict[EDID, Group_FormID], dict[FormID, EDID]]:
    edids = {}
    formids = {}
    with _edid_index_path.open('r') as f:
         index = json.load(f)

    for edid, v in index.items():
        group, formid = v.split('/', 1)
        edids[formid] = edid

    return index, edids

# Populates DB_DIR with files 'group/formid.bin'
def create_db(flush_cache=False, only_index=False) -> None:
    edid_index = {}
    ot = OffsetTree()
    with STARFIELD_ESM.open('rb') as esm:
        for rtype, formid, start, end in iter_offsets(esm):
            if rtype == "group":
                group_node = ot.add_node(start, end, None, [formid])
                continue
            esm.seek(start)
            header = esm.read(24)
            record = Record(header)

            data = esm.read(record.size)
            record.raw_data = data
            try:
                record.decompress()
            except:
                print(record, header)
                print(data)
                print()
                continue

            edid = record.parse_edid()
            if edid:
                edid_index[edid] = record.group + '/' + record.formid

            ot.add_node(start, end, group_node, [formid])

            if not only_index:
                record.path.parent.mkdir(exist_ok=True)
                if flush_cache or not record.path.exists():
                    record.save()

    if flush_cache or not _edid_index_path.exists():
        with _edid_index_path.open('w') as f:
            json.dump(edid_index, f, indent=2)
        ot.sort()
        ot.save()

    (DB_DIR / "timestamp").open('w+').write(str(int(time.time())))


if __name__ == "__main__":
    create_db(True, False)
