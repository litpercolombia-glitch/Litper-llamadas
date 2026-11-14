"""Mongo falso en memoria (subconjunto de motor) para pruebas unitarias.

Amplía el banco de test_byok_openrouter.py con los operadores que usan las
rutas: $in/$nin/$ne/$gt(e)/$lt(e)/$exists/$or/$and, claves con punto, sort,
skip, limit, count_documents, update_many, delete_many, replace_one,
find_one_and_update, distinct y un aggregate simple ($match/$sort/$limit/$group
con $sum). No pretende ser Mongo: solo lo justo para probar aislamiento.
"""
from types import SimpleNamespace


def _values(doc, key):
    """Valores de `key` (admite 'a.b' y recorre listas, como Mongo)."""
    cur = [doc]
    for part in key.split("."):
        nxt = []
        for c in cur:
            if isinstance(c, list):
                nxt.extend(x.get(part) for x in c if isinstance(x, dict) and part in x)
            elif isinstance(c, dict) and part in c:
                nxt.append(c[part])
        cur = nxt
    return cur


def _cmp(val, op, arg):
    if op == "$in":   return val in arg
    if op == "$nin":  return val not in arg
    if op == "$ne":   return val != arg
    if op == "$eq":   return val == arg
    if val is None:   return False
    if op == "$gte":  return val >= arg
    if op == "$gt":   return val > arg
    if op == "$lte":  return val <= arg
    if op == "$lt":   return val < arg
    raise NotImplementedError(op)


def match(doc, q):
    for k, cond in (q or {}).items():
        if k == "$or":
            if not any(match(doc, sub) for sub in cond): return False
            continue
        if k == "$and":
            if not all(match(doc, sub) for sub in cond): return False
            continue
        vals = _values(doc, k)
        flat = [x for v in vals for x in (v if isinstance(v, list) else [v])] or [None]
        if isinstance(cond, dict) and any(str(o).startswith("$") for o in cond):
            for op, arg in cond.items():
                if op == "$exists":
                    if bool(vals) != bool(arg): return False
                elif op in ("$ne", "$nin"):
                    if not all(_cmp(v, op, arg) for v in flat): return False
                elif not any(_cmp(v, op, arg) for v in flat):
                    return False
        elif not any(v == cond for v in flat) and not (vals and vals[0] == cond):
            return False
    return True


def _project(doc, proj):
    d = {k: v for k, v in doc.items() if k != "_id"}
    if not proj:
        return d
    keep = [k for k, v in proj.items() if v and k != "_id"]
    if keep:
        return {k: d[k] for k in keep if k in d}
    return {k: v for k, v in d.items() if proj.get(k, 1) != 0}


def _sort(docs, spec, direction=1):
    spec = [(spec, direction)] if isinstance(spec, str) else list(spec)
    for key, d in reversed(spec):
        docs.sort(key=lambda x: (x.get(key) is not None, x.get(key) if x.get(key) is not None else 0),
                  reverse=(d == -1))
    return docs


class Cursor:
    def __init__(self, docs): self.docs = docs
    def sort(self, spec, direction=1): _sort(self.docs, spec, direction); return self
    def skip(self, n): self.docs = self.docs[n:]; return self
    def limit(self, n): self.docs = self.docs[:n] if n else self.docs; return self
    async def to_list(self, n=None): return self.docs[:n] if n else self.docs
    def __aiter__(self): self._i = iter(self.docs); return self
    async def __anext__(self):
        try: return next(self._i)
        except StopIteration: raise StopAsyncIteration


class Coll:
    def __init__(self): self.docs = []

    def _find(self, q): return [d for d in self.docs if match(d, q or {})]

    async def find_one(self, q=None, proj=None, sort=None):
        found = self._find(q)
        if sort: _sort(found, sort)
        return _project(found[0], proj) if found else None

    def find(self, q=None, proj=None, sort=None):
        found = [_project(d, proj) for d in self._find(q)]
        if sort: _sort(found, sort)
        return Cursor(found)

    async def insert_one(self, d):
        self.docs.append(dict(d)); return SimpleNamespace(inserted_id=d.get("id"))

    def _apply(self, d, upd, inserting=False):
        for k, v in upd.get("$set", {}).items():
            if "." in k:                      # "a.b" → anidado, como Mongo
                cur = d
                *padres, hoja = k.split(".")
                for part in padres:
                    if not isinstance(cur.get(part), dict):
                        cur[part] = {}
                    cur = cur[part]
                cur[hoja] = v
            else:
                d[k] = v
        if inserting: d.update(upd.get("$setOnInsert", {}))
        for k in upd.get("$unset", {}): d.pop(k, None)
        for k, v in upd.get("$inc", {}).items(): d[k] = d.get(k, 0) + v

    async def update_one(self, q, upd, upsert=False):
        for d in self._find(q):
            self._apply(d, upd)
            return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)
        if upsert:
            d = {k: v for k, v in q.items() if not k.startswith("$") and not isinstance(v, dict)}
            self._apply(d, upd, inserting=True); self.docs.append(d)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=1)
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def update_many(self, q, upd):
        found = self._find(q)
        for d in found: self._apply(d, upd)
        return SimpleNamespace(matched_count=len(found), modified_count=len(found))

    async def replace_one(self, q, doc, upsert=False):
        for i, d in enumerate(self.docs):
            if match(d, q):
                self.docs[i] = dict(doc); return SimpleNamespace(matched_count=1)
        if upsert: self.docs.append(dict(doc))
        return SimpleNamespace(matched_count=0)

    async def find_one_and_update(self, q, upd, return_document=True, projection=None, upsert=False):
        for d in self._find(q):
            self._apply(d, upd); return _project(d, projection)
        return None

    async def delete_one(self, q):
        for d in self._find(q):
            self.docs.remove(d); return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, q):
        found = self._find(q)
        for d in found: self.docs.remove(d)
        return SimpleNamespace(deleted_count=len(found))

    async def count_documents(self, q=None): return len(self._find(q))

    async def distinct(self, key, q=None):
        out = []
        for d in self._find(q):
            for v in _values(d, key):
                if v not in out: out.append(v)
        return out

    def aggregate(self, pipeline):
        docs = [dict(d) for d in self.docs]
        for stage in pipeline:
            (op, arg), = stage.items()
            if op == "$match": docs = [d for d in docs if match(d, arg)]
            elif op == "$sort": _sort(docs, list(arg.items()))
            elif op == "$limit": docs = docs[:arg]
            elif op == "$group":
                groups = {}
                for d in docs:
                    gid = d.get(arg["_id"][1:]) if isinstance(arg["_id"], str) else None
                    g = groups.setdefault(gid, {"_id": gid})
                    for field, expr in arg.items():
                        if field == "_id": continue
                        inc = expr["$sum"]
                        inc = d.get(inc[1:], 0) if isinstance(inc, str) else inc
                        g[field] = g.get(field, 0) + (inc or 0)
                docs = list(groups.values())
            else: raise NotImplementedError(op)
        return Cursor(docs)

    async def create_index(self, *a, **k): return "idx"
    async def drop_index(self, *a, **k): return None


class DB:
    def __init__(self): self.c = {}
    def __getattr__(self, n):
        if n == "c": raise AttributeError
        return self.c.setdefault(n, Coll())
    def __getitem__(self, n): return getattr(self, n)
