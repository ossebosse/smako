"""Run with Python 3.12 on Linux; these tests never contact Docker or production."""
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from archive_cold_test_tree import archive_tree, inventory, verify


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'listxattr'), 'Linux archive metadata')
class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'smako-test'
        self.root.mkdir()
        (self.root / 'data').write_bytes(b'price evidence\x00' * 100)
        (self.root / 'link').symlink_to('data')
        self.dest = self.parent / 'archives'

    def run_archive(self, guard=lambda _: None):
        return archive_tree(self.root, self.dest, allowed_parent=self.parent, guard=guard)

    def test_roundtrip_retains_every_byte_and_symlink(self):
        original = inventory(self.root)
        result = self.run_archive()
        self.assertFalse(self.root.exists())
        verify(Path(result['archive']), original)
        restored = self.parent / 'restored'
        with tarfile.open(result['archive']) as tar:
            tar.extractall(restored, filter='data')
        self.assertEqual((restored/'smako-test/data').read_bytes(), b'price evidence\x00' * 100)
        self.assertTrue((restored/'smako-test/link').is_symlink())

    def test_reference_guard_preserves_original(self):
        def guard(_):
            raise ValueError('in_use')
        with self.assertRaisesRegex(ValueError, 'in_use'):
            self.run_archive(guard)
        self.assertTrue((self.root / 'data').exists())

    def test_change_during_archive_preserves_original(self):
        calls = []
        def guard(_):
            calls.append(True)
            if len(calls) == 2:
                (self.root / 'data').write_bytes(b'new user work')
        with self.assertRaisesRegex(ValueError, 'source_changed'):
            self.run_archive(guard)
        self.assertEqual((self.root / 'data').read_bytes(), b'new user work')

    def test_symlink_root_and_outside_root_rejected(self):
        link = self.parent / 'smako-link'
        link.symlink_to(self.root, target_is_directory=True)
        for root, parent in [(link, self.parent), (self.root, self.parent/'other')]:
            with self.assertRaisesRegex(ValueError, 'outside_reviewed'):
                archive_tree(root, self.dest, allowed_parent=parent, guard=lambda _: None)
        self.assertTrue(self.root.exists())

    def test_repeated_archive_never_overwrites_evidence(self):
        self.run_archive()
        self.root.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_archive()

    def test_corrupt_archive_cannot_verify(self):
        expected = inventory(self.root)
        result = self.run_archive()
        archive = Path(result['archive'])
        archive.write_bytes(b'corrupt')
        with self.assertRaises(tarfile.ReadError):
            verify(archive, expected)


if __name__ == '__main__':
    unittest.main()
