#!/usr/bin/env python
"""
Given a root directory, recurse in it and find all the duplicate
files, files that have the same contents, but not necessarily the
same filename.
"""
# This code is released as CC-0
# http://creativecommons.org/publicdomain/zero/1.0/

from collections import namedtuple
from sys import maxsize, stderr
import optparse
from os import readlink, cpu_count, scandir, PathLike
from os.path import islink, abspath, isdir
from fnmatch import fnmatch
from hashlib import sha1
from itertools import groupby
from operator import itemgetter
import multiprocessing.pool
from multiprocessing import Pool
from typing import Iterator, Iterable, Callable, Any

# Keep together associated file information
Finfo = namedtuple("Finfo", ["size", "path", "inode"])
SIZE, PATH, INODE = range(3)

# Keep stats on hashes performed and avoided
hashes_calculated, hashes_skipped = 0, 0


def main() -> None:
    parser = optparse.OptionParser(__doc__.strip())
    parser.add_option(
        "-M",
        "--max-size",
        type="int",
        default=maxsize,
        help="Ignore files larger than MAX_SIZE",
    )
    parser.add_option(
        "-m",
        "--min-size",
        type="int",
        default=1,
        help="Ignore files smaller than MIN_SIZE",
    )
    parser.add_option(
        "-l",
        "--enable-symlinks",
        action="store_true",
        default=False,
        help="Include symlinks in duplication report",
    )
    parser.add_option(
        "-g",
        "--glob",
        type="str",
        default="*",
        help="Limit matches to glob pattern",
    )
    parser.add_option(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Display progress information on STDERR",
    )
    opts, args = parser.parse_args()
    if not args:
        parser.error("You must specify directories to search.")

    find_duplicates(args, opts)


def scan_files(args: Iterable[str | PathLike[Any]], opts) -> Iterator[Finfo]:
    for dir in args:
        if isdir(dir):
            for entry in scandir(dir):
                if entry.is_dir(follow_symlinks=opts.enable_symlinks):
                    yield from scan_files([entry.path], opts)
                elif entry.is_file(follow_symlinks=opts.enable_symlinks):
                    if fnmatch(entry.name, opts.glob):
                        try:
                            path = entry.path
                            size = entry.stat().st_size
                            inode = entry.inode()
                            yield Finfo(size, path, inode)
                        except FileNotFoundError as err:
                            if opts.verbose:
                                print(err, file=stderr)


# NOTE: corrected manually, never caught by checkers
def hash_content(finfo: Finfo) -> tuple[str, str]:
    try:
        with open(finfo.path, "rb") as fh:
            content = fh.read()
            return (sha1(content).hexdigest(), finfo.path)
    except IOError as s:
        print(s, file=stderr)
        return ("_ERROR", finfo.path)


def parallel_hash(
    finfos: list[Finfo], pool: multiprocessing.pool.Pool
) -> list[tuple[str, str]]:
    global hashes_calculated, hashes_skipped
    # Might have exclusively paths of this size with same inode
    if len({finfo.inode for finfo in finfos}) == 1:
        inode = finfos[0].inode  # Any finfo will do
        hashes = [(f"<INODE {inode}>", finfo.path) for finfo in finfos]
        hashes_skipped += len(finfos)
        return hashes

    # Otherwise, split up the inodes with one versus several paths
    unique_inodes = [
        f[0] for _, f in group_by_key(finfos, INODE, Finfo) if len(f) == 1
    ]
    dup_inodes = [f for _, f in group_by_key(finfos, key=INODE) if len(f) > 1]

    # Use the pool to parallelize distinct inodes
    hashes = pool.map(hash_content, unique_inodes)
    hashes_calculated += len(hashes)

    # Might add to hashes if we have hardlink sets
    # Note: there COULD be many such inode sets, which are calculated
    #     serially.  However, the performance difference between serial
    #     and parallel is so small that it matters little.
    for dup_inode in dup_inodes:
        finfo = Finfo(*dup_inode[0])  # Use the first one
        digest, _ = hash_content(finfo)
        more_hashes = [(digest, dup[1]) for dup in dup_inode]
        hashes.extend(more_hashes)
        hashes_calculated += 1
        hashes_skipped += len(more_hashes) - 1

    return hashes


def group_by_key(
    records: Iterable[tuple],
    key: int = 0,
    val_type: Callable = lambda *x: tuple(x),
    reverse: bool = True,
) -> Iterator[tuple[int, list]]:
    """Combine records by common value in position (default first)

    This function is passed an interable each of whose values is a tuple;
    it yields a sequence of tuples whose first element is the identical
    key-position element from the original pairs, and whose second element
    is a list of tail elements corresponding to the same key element:

      >>> things = [(1,'foo', 17), (1,'bar', 119), (2, 'baz', 43)]
      >>> list(group_by_key(things))
      [(1, [(1, 'foo', 17), (1, 'bar', 119)]), (2, [(2, 'baz', 43)])]
      >>> Finfo = namedtuple("Finfo", ["size", "path", "inode"])
      >>> list(group_by_key(things, val_type=Finfo))
      [(1, [Finfo(size=1, path='foo', inode=17),
            Finfo(size=1, path='bar', inode=119)]),
       (2, [Finfo(size=2, path='baz', inode=43)])]

    By default, groups are arranged from largest to smallest key value.

    By passing a val_type argument, the groups may be cast into a whatever
    special type is needed, initialized by the tuple of arguments.
    """
    records = sorted(records, key=itemgetter(key), reverse=reverse)
    for idx, vals in groupby(records, itemgetter(key)):
        yield (idx, [val_type(*v) for v in vals])


def get_path_infos(
    dirs: Iterable[str | PathLike[Any]], opts: optparse.Values
) -> Iterator[Finfo]:
    "Yield a sequence of Finfo objects"
    count = 0
    for size, path, inode in scan_files(dirs, opts):
        if opts.min_size <= size <= opts.max_size:
            count += 1
            yield Finfo(size, path, inode)
    if opts.verbose:
        print(f"Looked up  {count:,} file sizes", file=stderr)


def find_duplicates(
    dirs: Iterable[str | PathLike[Any]], opts: optparse.Values
) -> None:
    "Find the duplicate files in the given root directory."
    # None is a *possible* return value for cpu_count(), 
    # but it will not happen on common architectures
    n_cpus = cpu_count() or 2
    # Need process pool
    pool = Pool(processes=int(n_cpus * 0.75))
    distincts = 0
    npaths = 0

    # Loop over the path records
    paths = get_path_infos(dirs, opts)
    for sz, finfos in group_by_key(paths, 0, Finfo):
        # We have accumulated some dups that need to be printed
        if len(finfos) > 1:
            hashes = parallel_hash(finfos, pool=pool)
            for hash, vals in group_by_key(hashes):
                if len(vals) > 1:
                    distincts += 1
                    print("Size:", sz, "| SHA1:", hash)
                    for _, path in vals:
                        npaths += 1
                        if islink(path):
                            ln = "-> " + readlink(path)
                            print(" ", abspath(path), ln)
                        else:
                            print(" ", abspath(path))

    if opts.verbose:
        print(f"Found      {distincts:,} duplication sets", file=stderr)
        print(f"Found      {npaths:,} paths within sets", file=stderr)
        print(f"Calculated {hashes_calculated:,} SHA1 hashes", file=stderr)
        print(f"Short-cut  {hashes_skipped:,} hard links", file=stderr)


if __name__ == "__main__":
    main()
