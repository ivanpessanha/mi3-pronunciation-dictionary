#!/usr/bin/env python3
"""Validates the dictionaries and prepares a publication. Standard library only.

    python tools/dictionary.py validate [--locale pt-BR]
    python tools/dictionary.py build --locale pt-BR --out dist --repository owner/name

The rules below mirror PronunciationLexicon.verify() in the app: a file that
passes here is accepted there.
"""
import argparse
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FORMAT = 1
MANIFEST_SCHEMA = 1
COLUMNS = ('key', 'kind', 'lang', 'source', 'ref', 'approx', 'flags', 'ipa', 'alias', 'voices', 'entity')
KINDS = {'n', 't', 's'}
CONFIDENCES = {'h', 'm', 'l'}
MAX_ALIAS_LENGTH = 200
LOCALE = re.compile(r'^[a-z]{2,3}(-[A-Z][a-zA-Z0-9]{1,7})?$')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')
ROOT = Path(__file__).resolve().parent.parent


class DictionaryError(Exception):
    pass


def validate_alias(alias, where):
    if len(alias) > MAX_ALIAS_LENGTH or CONTROL.search(alias):
        raise DictionaryError(f'{where}: invalid alias')


def validate_row(row, where):
    fields = row.split('\t')
    if len(fields) != len(COLUMNS):
        raise DictionaryError(f'{where}: expected {len(COLUMNS)} columns, found {len(fields)}')
    key, kind, _, source, ref, approx, flags, _, alias, voices, _ = fields
    if not key or key != key.lower() or key != key.strip() or key.startswith('#') or '’' in key:
        raise DictionaryError(f'{where}: key must be normalized: {key!r}')
    if kind not in KINDS:
        raise DictionaryError(f'{where}: unknown kind {kind!r}')
    if ref not in CONFIDENCES or approx not in CONFIDENCES:
        raise DictionaryError(f'{where}: unknown confidence')
    if not source:
        raise DictionaryError(f'{where}: missing source')
    if not set(flags) <= {'a', 'x'}:
        raise DictionaryError(f'{where}: unknown flags {flags!r}')
    validate_alias(alias, where)
    pairs = voices.split(';') if voices else []
    for pair in pairs:
        voice, separator, value = pair.partition('=')
        if not voice or not separator:
            raise DictionaryError(f'{where}: invalid voice alias {pair!r}')
        validate_alias(value, where)
    if not alias and not pairs:
        raise DictionaryError(f'{where}: no alias')
    return key


def parse(text, locale):
    """Returns the rows of a source file after checking all of it."""
    if '\r' in text:
        raise DictionaryError('use LF line endings')
    if not text.endswith('\n'):
        raise DictionaryError('the file must end with a newline')
    lines = text[:-1].split('\n')
    headers = {}
    while lines and lines[0].startswith('#'):
        name, _, value = lines.pop(0)[1:].partition('=')
        headers[name] = value
    if headers.get('format') != str(FORMAT):
        raise DictionaryError(f'expected #format={FORMAT}')
    if headers.get('locale') != locale:
        raise DictionaryError(f'expected #locale={locale}')
    if not lines:
        raise DictionaryError('no rows')
    previous = None
    for number, row in enumerate(lines, start=len(headers) + 1):
        key = validate_row(row, f'line {number}')
        encoded = key.encode('utf-8')
        if previous is not None and previous >= encoded:
            raise DictionaryError(f'line {number}: {key!r} is duplicated or out of order')
        previous = encoded
    return lines


def source_path(root, locale):
    if not LOCALE.match(locale):
        raise DictionaryError(f'invalid locale {locale!r}')
    return root / 'dictionaries' / locale / 'lexicon.tsv'


def read_source(root, locale):
    return source_path(root, locale).read_bytes().decode('utf-8')


def locales(root):
    return sorted(p.parent.name for p in (root / 'dictionaries').glob('*/lexicon.tsv'))


def read_manifest(root):
    path = root / 'manifest.json'
    if not path.exists():
        return {'schema': MANIFEST_SCHEMA, 'dictionaries': {}}
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schema') != MANIFEST_SCHEMA:
        raise DictionaryError('unknown manifest schema')
    return manifest


def distribution(rows, locale, revision):
    """The file served to the app, with its publication stamped in the header."""
    header = f'#format={FORMAT}\n#locale={locale}\n#revision={revision}\n#version={locale}-r{revision}\n'
    data = (header + '\n'.join(rows) + '\n').encode('utf-8')
    # mtime=0 makes the same content always produce the same bytes.
    return gzip.compress(data, compresslevel=9, mtime=0)


def build(root, locale, out, repository, now=None):
    """Writes the release file and updates the manifest; None when nothing changed."""
    text = read_source(root, locale)
    rows = parse(text, locale)
    source_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    manifest = read_manifest(root)
    current = manifest['dictionaries'].get(locale)
    if current and current['sourceSha256'] == source_hash:
        return None
    revision = (current['revision'] if current else 0) + 1
    tag = f'{locale}-r{revision}'
    name = f'lexicon-{tag}.tsv.gz'
    data = distribution(rows, locale, revision)
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(data)
    published = (now or datetime.now(timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifest['dictionaries'][locale] = {
        'format': FORMAT,
        'revision': revision,
        'publishedAt': published,
        'entries': len(rows),
        'url': f'https://github.com/{repository}/releases/download/{tag}/{name}',
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'sourceSha256': source_hash,
    }
    (root / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n'
    )
    return {'tag': tag, 'file': str(out / name), 'revision': revision, 'entries': len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('validate')
    check.add_argument('--locale')
    publish = commands.add_parser('build')
    publish.add_argument('--locale', required=True)
    publish.add_argument('--out', type=Path, default=Path('dist'))
    publish.add_argument('--repository', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            for locale in [args.locale] if args.locale else locales(ROOT):
                rows = parse(read_source(ROOT, locale), locale)
                print(f'{locale}: {len(rows)} entries OK')
            read_manifest(ROOT)
        else:
            result = build(ROOT, args.locale, args.out, args.repository)
            print(f'changed={"true" if result else "false"}')
            for name, value in (result or {}).items():
                print(f'{name}={value}')
    except (DictionaryError, OSError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
