"""Build GitHub Pages documentation without opening or exporting review data."""
import argparse
from pathlib import Path

from flask import render_template
from app import create_app


def render() -> str:
    app = create_app({'ADMIN_TOKEN': '', 'DATABASE': 'not-used-by-documentation.db'})
    with app.test_request_context('/'):
        return render_template('documentation.html', static_site=True) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    content = render()
    for name in ['index.html', 'documentation.html']:
        path = root / name
        if args.check:
            if path.read_text(encoding='utf-8') != content:
                raise SystemExit(f'{name} is stale; run python render_docs.py')
        else:
            path.write_text(content, encoding='utf-8', newline='\n')
    print('Documentation matches templates.' if args.check else 'Built static API documentation; no database access.')


if __name__ == '__main__':
    main()
