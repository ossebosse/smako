"""Losslessly archive an explicitly reviewed, unused Smako test tree.

Caller must hold the production operation lease. No discovery or automatic
retention policy: supply one exact reviewed directory. Never use on live data.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inventory(root):
    result = {}
    for p in [root, *sorted(root.rglob('*'))]:
        s = p.lstat()
        if os.listxattr(p, follow_symlinks=False):
            raise ValueError('extended_attributes_require_separate_archive_review')
        if not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode)):
            raise ValueError('unsupported_special_file')
        row = {'stat': [s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                        s.st_mode, s.st_uid, s.st_gid]}
        if p.is_symlink():
            row['link'] = os.readlink(p)
        elif p.is_file():
            row['sha256'] = sha(p)
        result[p.relative_to(root.parent).as_posix()] = row
    return result


def unused(root):
    ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
    containers = json.loads(subprocess.check_output(['docker', 'inspect', *ids])) if ids else []
    references = [Path(m['Source']).resolve() for c in containers for m in c['Mounts']]
    for process in Path('/proc').glob('[0-9]*'):
        for link in [process/'cwd', process/'exe', *list((process/'fd').glob('*'))]:
            try:
                references.append(link.resolve(strict=True))
            except (OSError, RuntimeError):
                pass
    if any(q == root or q.is_relative_to(root) or root.is_relative_to(q)
           for q in references if q != Path('/')):
        raise ValueError('tree_referenced_by_container_or_process')
    # Do not archive paths named in current deployment/service configuration.
    for base in [Path('/opt/smako/overrides'), Path('/etc/systemd/system'), Path('/etc/cron.d')]:
        for p in base.rglob('*'):
            if (p.is_file() and not p.is_symlink() and p.stat().st_size < 2_000_000
                    and str(root).encode() in p.read_bytes()):
                raise ValueError('tree_referenced_by_service_configuration')


def verify(archive, expected):
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if member.name in seen or member.name not in expected:
                raise ValueError('archive_member_mismatch')
            seen.add(member.name)
            row = expected[member.name]
            mode = row['stat'][4]
            if (member.mode != stat.S_IMODE(mode)
                    or (member.uid, member.gid) != tuple(row['stat'][5:7])):
                raise ValueError('archive_metadata_mismatch')
            if 'sha256' in row:
                if not (member.isfile() or member.islnk()):
                    raise ValueError('archive_file_type_mismatch')
                with tar.extractfile(member) as handle:
                    if hashlib.file_digest(handle, 'sha256').hexdigest() != row['sha256']:
                        raise ValueError('archive_hash_mismatch')
            elif 'link' in row:
                if not member.issym() or member.linkname != row['link']:
                    raise ValueError('archive_link_mismatch')
            elif not member.isdir():
                raise ValueError('archive_directory_mismatch')
    if seen != set(expected):
        raise ValueError('archive_incomplete')


def archive_tree(root, destination, *, allowed_parent=Path('/var/tmp'), guard=unused):
    root, destination = Path(root), Path(destination)
    if (root.is_symlink() or root.resolve() != root or root.parent != allowed_parent.resolve()
            or not root.name.startswith('smako-') or 'ica' in root.name or not root.is_dir()):
        raise ValueError('target_outside_reviewed_test_root')
    if destination.resolve().is_relative_to(root):
        raise ValueError('archive_inside_source')
    if destination.resolve() != destination:
        raise ValueError('archive_destination_must_be_absolute_without_symlinks')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive = destination / (root.name + '.tar.gz')
    proof = destination / (root.name + '.inventory.private.json')
    if archive.exists() or proof.exists():
        raise FileExistsError('archive_already_exists_review_before_retry')
    guard(root)
    expected = inventory(root)
    before = sum(p.lstat().st_blocks * 512 for p in [root, *root.rglob('*')])
    # Bound staging space without assuming a compression ratio.
    apparent = sum(row['stat'][1] for row in expected.values() if 'sha256' in row)
    if shutil.disk_usage(destination).free < max(before, apparent) + 536_870_912:
        raise ValueError('insufficient_archive_staging_space')
    with proof.open('x', encoding='utf8') as handle:
        os.chmod(proof, 0o600)
        json.dump(expected, handle)
        handle.flush()
        os.fsync(handle.fileno())
    with archive.open('xb') as handle:
        os.chmod(archive, 0o600)
        with tarfile.open(fileobj=handle, mode='w:gz', compresslevel=1, dereference=False) as tar:
            tar.add(root, arcname=root.name)
        handle.flush()
        os.fsync(handle.fileno())
    verify(archive, expected)
    guard(root)
    if inventory(root) != expected:
        raise ValueError('source_changed_original_retained')
    directory = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    # The exact absolute root was validated and all contents verified above.
    shutil.rmtree(root)
    return {'source': str(root), 'archive': str(archive), 'entries_verified': len(expected),
            'before_allocated_bytes': before, 'archive_bytes': archive.stat().st_size,
            'archive_sha256': sha(archive), 'original_removed_after_verification': True}
