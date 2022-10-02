# Things to Demo

- `. ./setup`

## (1) Without explicit typing
- `time ./finddups.py -l ~/miniconda3/ | less`
- `finddups.py` general functionality
- `./finddups.py -vl /tmp/clean | wc`
- `mypy finddups.py`
- `pytype finddups.py` (Google)
  - Inference not gradual typing
  - Do not warn on "OK-at-runtime" code
- `pyright finddups.py` (Microsoft)
  - Generally aggressive in diagnosis
  - Misreport on 30 of `.strip()`
  - Good catch on 176 of possible `None`

## (2) Adding type annotations

- `compare finddups.py finddups2.py`
- Show the equivalence of the modification
  - `./finddups2.py -vl /tmp/clean | wc`
- `mypy finddups2.py`
- `pytype finddups2.py`
- `pyright finddups2.py`
- Correct the type complaints
  - `compare finddups2.py finddups2a.py`
  - `mypy finddups2a.py`
  - `pytype finddups2a.py`
  - `pyright finddups2a.py`

## (3) Runtime typing

- `compare finddups2.py finddups3.py`
  - @pydantic.dataclass not BaseModel 
- Show the equivalence of the modification
  - `./finddups3.py -vl ../clean | wc`
- `mypy finddups3.py`
- `pytype finddups3.py`
- `pyright finddups3.py`
- Introduce a typing error in `finddups4.py`
  - `compare finddups3.py finddups4.py`
  - `mypy finddups4.py`
  - `pytype finddups4.py`
    - confused by classes within pydantic
  - `pyright finddups4.py` 
    - plays poorly with dataclass
  - Not hit at runtime:
    - `./finddups4.py -vl ../cleaning | wc`

## (4) Third-party runtime typing

- Show `runtime_checks.py`
- Run `runtime_checks.py`
- Typing error is clearer and more remediable than traceback
- Mild type coercion in models;

```python
>>> from typing import AnyStr
>>> from pydantic import BaseModel
>>> class Finfo(BaseModel):
...     size: int
...     path: AnyStr
...     inode: int
>>> finfo = Finfo(path='/some/path', size=3.1415, inode=12345678)
>>> finfo
Finfo(path=b'/path/to/here', size=3, inode=12345678)
>>> finfo.json()
'{"path": "/path/to/here", "size": 3, "inode": 12345678}'
```

## (5) Fast-API: Pydantic as a microservice

- Launch server: `uvicorn main:app --reload`
- `cp servers/hello.py main.py`
- `curl -s http://localhost:8000 | jq`
- `cp servers/hello-path.py main.py`
- `curl -s http://localhost:8000/item/1234 | jq`
- `curl -s http://localhost:8000/item/not-an-int | jq`
- `cp servers/post-model.py main.py`
- POST some data:

```bash
curl -s -X POST http://localhost:8000/finfo \
-H 'Content-Type: application/json' \
-d '{"path":"/some/path","size":100,"inode":99999}' | jq
```

- POST some not-quite-right data to coerce:

```bash
curl -s -X POST http://localhost:8000/finfo \
-H 'Content-Type: application/json' \
-d '{"path":"/some/path","size":3.14,"inode":99999}' | jq
```

- POST some very-wrong data:

```bash
curl -s -X POST http://localhost:8000/finfo \
-H 'Content-Type: application/json' \
-d '{"path":"/some/path","size":null,"inode":99999}' | jq
```

## (6) Typer: Pydantic command-line parsing

- `compare finddups3.py finddups-typer.py`
- `mypy finddups-typer.py`
- `./finddups.py --help`
- `./findups-typer.py --help`
- `./finddups.py -m not-an-int ../cleaning-data`
- `./finddups-typer.py -m not-an-int ../cleaning-data`
- `./finddups-typer.py -l | wc` (same as other versions)
- `./finddups-typer.py --<tab>`
