#!/usr/bin/env python
from finddups3 import Pool, Finfo, parallel_hash, ValidationError

pool = Pool(8)

fileGroups = [
    [
        (7157, "finddups.py", 8269401),
        (8022, "finddups2.py", 8269470),
        (7862, "finddups2a.py", 8269464),
        (8050, "finddups3.py", 8269341),
        (8074, "finddups4.py", 8269452),
    ],
    [
        (7157, "finddups.py", 8269401),
        (8022, "finddups2.py", 8269470),
        (7862, "finddups2a.py", None),
        (8050, "finddups3.py", 8269341),
    ],
    [
        (7157, "finddups.py", 8269401),
        (8022, "finddups2.py", 8269470),
        (7862, "finddups2a.py", 8269464),
    ],
]

for ngroup, group in enumerate(fileGroups):
    try:
        files = [Finfo(*tup) for tup in group]
        for hash_info in parallel_hash(files, pool):
            print(hash_info.digest, hash_info.finfo.path)
    except ValidationError as e:
        print(f"Problem detected with file group {ngroup+1}")
        print(e)
    print("-" * 72)
