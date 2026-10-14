"""Bygg fristående HTML från referenskoden. Kräver endast Python-standardbiblioteket."""
from pathlib import Path


def build_html() -> str:
    folder = Path(__file__).resolve().parents[1] / 'prototype'
    html = (folder / 'index.html').read_text(encoding='utf-8')
    for name in ('tokens.css', 'styles.css'):
        html = html.replace(f'<link rel="stylesheet" href="{name}">',
                            '<style>' + (folder / name).read_text(encoding='utf-8') + '</style>')
    return html.replace('<script src="app.js"></script>',
                        '<script>' + (folder / 'app.js').read_text(encoding='utf-8') + '</script>')


if __name__ == '__main__':
    output = Path(__file__).resolve().parents[1] / 'smako-ui-preview.html'
    output.write_text(build_html(), encoding='utf-8')
    print(output)
