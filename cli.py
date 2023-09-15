import argparse
import db
import recompile

parser = argparse.ArgumentParser(
        prog="esm"
        )
parser.add_argument('--flush-cache', action='store_true')

subparsers = parser.add_subparsers()
create_db = subparsers.add_parser("create_db")
create_db.set_defaults(func=db.create_db)


recompile_parser = subparsers.add_parser("recompile")
recompile_parser.set_defaults(func=recompile.recompile)


if __name__ == "__main__":
    args = parser.parse_args()
    args.func(flush_cache=args.flush_cache)
