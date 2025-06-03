import argparse
from misc.archive import parse_cli_archive

def main():
    parser = argparse.ArgumentParser(description="TM2PY CLI tool")
    parser.add_argument('--version', action='version', version='tm2py-utils 1.0')

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive a model run by compressing important model files")
    archive_parser.add_argument("model_directory", help="Directory of model run to archive")
    archive_parser.add_argument("archive_directory", help="Destination to dump the archived files")
    archive_parser.add_argument("-n", "--name", help="Optional model run name", default="")
    archive_parser.set_defaults(func=parse_cli_archive)

    # Parse and dispatch
    args = parser.parse_args()
    args.func(args)