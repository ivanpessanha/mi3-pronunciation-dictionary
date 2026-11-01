import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import dictionary  # noqa: E402

HEADER = '#format=1\n#locale=pt-BR\n'
ROW = 'prompt\tt\ten\tcurated\th\th\t\t\tprômpti\t\t\n'


def row(key='a', kind='t', source='c', ref='h', approx='h', flags='', alias='x', voices=''):
    return f'{key}\t{kind}\ten\t{source}\t{ref}\t{approx}\t{flags}\t\t{alias}\t{voices}\t\n'


class ParseTest(unittest.TestCase):
    def test_accepts_a_valid_file(self):
        rows = dictionary.parse(HEADER + row('gpu', 's', alias='Gê-Pê-U') + ROW, 'pt-BR')
        self.assertEqual(len(rows), 2)

    def test_accepts_a_voice_alias_without_a_general_one(self):
        dictionary.parse(HEADER + row(alias='', voices='antonio=x;thalita=-'), 'pt-BR')

    def test_orders_by_utf8_bytes(self):
        dictionary.parse(HEADER + row('z') + row('é'), 'pt-BR')
        with self.assertRaises(dictionary.DictionaryError):
            dictionary.parse(HEADER + row('é') + row('z'), 'pt-BR')

    def test_rejects(self):
        cases = {
            'no rows': HEADER,
            'crlf': HEADER + ROW.replace('\n', '\r\n'),
            'no final newline': HEADER + ROW.rstrip('\n'),
            'other locale': '#format=1\n#locale=en-US\n' + ROW,
            'other format': '#format=2\n#locale=pt-BR\n' + ROW,
            'missing column': HEADER + 'a\tt\ten\tc\th\th\t\t\tx\t\n',
            'duplicate': HEADER + ROW + ROW,
            'unsorted': HEADER + row('b') + row('a'),
            'uppercase key': HEADER + row('A'),
            'curly apostrophe': HEADER + row('o’neil'),
            'spaces around key': HEADER + row(' a'),
            'unknown kind': HEADER + row(kind='z'),
            'unknown confidence': HEADER + row(ref='q'),
            'unknown flag': HEADER + row(flags='z'),
            'no source': HEADER + row(source=''),
            'no alias': HEADER + row(alias=''),
            'control character': HEADER + row(alias='x\x07y'),
            'long alias': HEADER + row(alias='x' * 201),
            'broken voice': HEADER + row(voices='antonio'),
            'long voice alias': HEADER + row(voices='antonio=' + 'x' * 201),
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(dictionary.DictionaryError):
                dictionary.parse(text, 'pt-BR')


class BuildTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.write(HEADER + ROW)

    def write(self, text):
        path = self.root / 'dictionaries' / 'pt-BR' / 'lexicon.tsv'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))

    def build(self):
        return dictionary.build(
            self.root, 'pt-BR', self.root / 'dist', 'owner/repo',
            now=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )

    def manifest(self):
        return json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))

    def test_first_publication(self):
        result = self.build()
        self.assertEqual(result['tag'], 'pt-BR-r1')
        entry = self.manifest()['dictionaries']['pt-BR']
        data = Path(result['file']).read_bytes()
        self.assertEqual(entry['revision'], 1)
        self.assertEqual(entry['entries'], 1)
        self.assertEqual(entry['size'], len(data))
        self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(
            entry['url'],
            'https://github.com/owner/repo/releases/download/pt-BR-r1/lexicon-pt-BR-r1.tsv.gz',
        )
        self.assertEqual(
            gzip.decompress(data).decode('utf-8'),
            '#format=1\n#locale=pt-BR\n#revision=1\n#version=pt-BR-r1\n' + ROW,
        )

    def test_unchanged_content_publishes_nothing(self):
        self.build()
        before = self.manifest()
        self.assertIsNone(self.build())
        self.assertEqual(self.manifest(), before)

    def test_changed_content_advances_only_its_locale(self):
        self.build()
        manifest = self.manifest()
        manifest['dictionaries']['en-US'] = {'revision': 7}
        (self.root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.write(HEADER + row('a') + ROW)
        self.assertEqual(self.build()['revision'], 2)
        self.assertEqual(self.manifest()['dictionaries']['en-US'], {'revision': 7})

    def test_an_invalid_file_changes_nothing(self):
        self.build()
        before = self.manifest()
        self.write(HEADER + row('b') + row('a'))
        with self.assertRaises(dictionary.DictionaryError):
            self.build()
        self.assertEqual(self.manifest(), before)

    def test_same_content_gives_the_same_bytes(self):
        rows = dictionary.parse(HEADER + ROW, 'pt-BR')
        self.assertEqual(
            dictionary.distribution(rows, 'pt-BR', 1),
            dictionary.distribution(rows, 'pt-BR', 1),
        )

    def test_rejects_a_locale_that_could_escape_the_folder(self):
        with self.assertRaises(dictionary.DictionaryError):
            dictionary.source_path(self.root, '../../etc')


class RepositoryTest(unittest.TestCase):
    def test_published_dictionaries_are_valid(self):
        root = Path(dictionary.__file__).resolve().parent.parent
        found = dictionary.locales(root)
        self.assertIn('pt-BR', found)
        for locale in found:
            dictionary.parse(dictionary.read_source(root, locale), locale)
        dictionary.read_manifest(root)


if __name__ == '__main__':
    unittest.main()
