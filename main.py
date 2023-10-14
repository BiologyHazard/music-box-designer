import argparse

from musicboxdesigner import (convert, generate_draft,
                              get_note_count_and_length, logger)


def convert_func(args) -> None:
    return convert(args.source, args.destination, args.overwrite)


def draft_func(args) -> None:
    return generate_draft(args.file_path, args.settings_path, args.overwrite)


def count_func(args) -> None:
    note_count, length_mm = get_note_count_and_length(args.file_path,
                                                      args.transposition,
                                                      not args.keep_blank,
                                                      not args.keep_near_notes,
                                                      args.bpm,
                                                      args.scale)
    print(f'Notes: {note_count}')
    print(f'Length: {length_mm / 1000:.2f}m')


parser = argparse.ArgumentParser(description='Music Box Designer')
subparsers = parser.add_subparsers(
    title='commands',
    required=True,
)

convert_parser = subparsers.add_parser(
    'convert',
    help='Convert .emid / .fmp / .mid file to another format.',
    description='Convert .emid / .fmp / .mid file to another format.',
    epilog=f'''examples:
  {parser.prog} convert examples/example.emid examples/example.mid
  {parser.prog} convert examples/example.emid .mid    # equivalent to the previous command
  {parser.prog} convert examples/*.mid examples/*.fmp
  {parser.prog} convert examples/*.mid .fmp    # equivalent to the previous command
''',
    formatter_class=argparse.RawDescriptionHelpFormatter
)
convert_parser.set_defaults(func=convert_func)
convert_parser.add_argument(
    'source',
    type=str,
    help="Specify the source file path, or just the extension (including the leading '.', e.g. 'directory/*.fmp', which will convert all .fmp files in directory/).",
)
convert_parser.add_argument(
    'destination',
    type=str,
    help="If source specified a file, destination can either be a path or an extension. If source provided an extension, destination should be a different extension.",
)
convert_parser.add_argument('-o', '--overwrite', action='store_true')

draft_parser = subparsers.add_parser(
    'draft', help='Generate draft pics.')
draft_parser.set_defaults(func=draft_func)
draft_parser.add_argument('file_path', type=str)
draft_parser.add_argument('settings_path', type=str, nargs='?', default='settings.yml')
draft_parser.add_argument('-o', '--overwrite', action='store_true')

count_parser = subparsers.add_parser(
    'count', help='Count notes and length.')
count_parser.set_defaults(func=count_func)
count_parser.add_argument('file_path', type=str)
count_parser.add_argument('-t', '--transposition',  type=int, default=0)
count_parser.add_argument('-k', '--keep-blank',  action='store_true')
count_parser.add_argument('-n', '--keep-near-notes', action='store_true')
count_parser.add_argument('-b', '--bpm', type=float, default=None)
count_parser.add_argument('-s', '--scale', type=float, default=1)


@logger.catch()
def main() -> None:
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    main()
