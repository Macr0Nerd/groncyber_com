import argparse
import os
import os.path
import re
import sys

import markdown as md


def arguments() -> dict:
    parser = argparse.ArgumentParser(
        prog='groncyber_generator',
        description='Static file generator for blog.groncyber.com',
        epilog='Developed by Gabriele Ron (developer@groncyber.com)'
    )

    parser.add_argument('webroot', help='set content webroot')
    parser.add_argument('-t', '--template', help='set template file', required=True)
    parser.add_argument('-s', '--source', help='set source file directory', required=True)
    parser.add_argument('-f', '--force', help='overwrite existing files', action='store_true',default=False)

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(0)

    args = vars(parser.parse_args())

    return args


def main() -> int:
    args = arguments()

    with open(args['template'], 'r') as f:
        template = f.read()

    base_root = None

    for root, dirs, files in os.walk(args['source']):
        if not base_root:
            base_root = root

        relative_root = root.replace(base_root, '')

        file_map = {}

        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(args['webroot'], relative_root, file.replace('.md', '.html'))

            if not os.path.exists(dst_file) or args['force']:
                with open(src_file, 'r') as f:
                    raw_data = f.read()

                content = md.markdown(raw_data, output_format='html', extensions=['extra'])

                if file == 'index.md' or not (match := re.search(r'#+ ?(?P<title>.*)', raw_data)):
                    title = 'init 0'
                else:
                    title = match.group('title')

                file_map[title] = os.path.join(relative_root, file.replace('.md', '.html'))

                with open(dst_file, 'w') as f:
                    f.write(template.format(title=title, content=content))

        if 'index.md' not in files:
            content = '<ul>\n'
            for title, path in file_map.items():
                content += f'<li><a href="{path}" target="_self">{title}</a></li>\n'
            content += '</ul>'

            with open(os.path.join(args['webroot'], relative_root, 'index.html'), 'w') as f:
                f.write(template.format(title='init 0', content=content))

    return 0


if __name__ == '__main__':
    sys.exit(main())
