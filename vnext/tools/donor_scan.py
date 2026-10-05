#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""donor_scan — движок поиска имён контура-донора в .py-файлах пакета.

Вынут из замера этапа Э2 (scan_names.py): разбор файла по ВИДАМ строк через tokenize + ast,
признание печатников (функций, печатающих свой параметр) и поиск образцов. Отличие от замера:
ВСЁ, что относится к донору — имена ролей, пути, репозитории, соседи, порты, образцы, — здесь
не живёт. Оно читается из файла donor-names.json рядом с проверкой. В коде движка нет ни
одного имени донора: смена донора — правка данных, а не кода.

ВИДЫ СТРОК (kind), от «сильного» к «слабому»; на одной строке одно имя даёт одну запись,
вид берётся самый сильный:
  code      — всё, что не попало в виды ниже (условия, пути, значения по умолчанию);
  shown     — строковый литерал, уходящий человеку: аргумент print(...), sys.stdout/stderr.write,
              sys.exit(...), help=... (и description/epilog/usage у ArgumentParser), аргументы
              функций-печатников. В shown попадают только литералы «текстовых» позиций
              аргумента (склейка, f-строка, %, .format, .join, условие-значение);
  docstring — строка документации модуля, класса, функции;
  comment   — комментарий после «#».

ФОРМАТ donor-names.json (ключи, начинающиеся с «_», — пояснения для человека, движок их не читает):
  {"format_version": 1,
   "lists":  {"<список>": ["слово", ...]},
   "groups": {"<группа>": [<правило>, ...]}}
Правило — объект. Тип задаётся ключом "type":
  regex (по умолчанию): "regex" — образец; подстановки {LB} (левая граница слова, допускает
      экранирование \\n \\t \\r \\b перед именем), {RB} (правая граница слова), {SEP} (слэш или
      обратный слэш). Имя находки: "name" (фиксированное) либо "name_from_group" (номер группы
      образца; "lower": true — строчными; "prefix": приставка к имени). "ignore_case";
      "claims_span": true — найденное место «занято», правила с "avoid_claimed": true его не
      повторяют; "context_filter": имя встроенной проверки окружения (сейчас одна:
      "dash_dot_slash_quote"); "only_in_strings": true — искать только внутри строковых литералов.
  words: "list" — слова из "lists" целиком (граница слова слева и справа); "ignore_case", "lower".
  whole_literal: "list" — строковый литерал, ЦЕЛИКОМ равный слову списка без учёта регистра;
      имя находки — литерал как написан; "skip_exact": true (по умолчанию) — точное написание из
      списка не считать (его ловит правило words), считать только иные регистры.
Группа без правил и список без слов допустимы: их правила молчат.
"""
import ast
import bisect
import collections
import io
import json
import re
import tokenize
import warnings
from typing import NamedTuple

KIND_ORDER = ("code", "shown", "docstring", "comment")
KIND_RANK = {k: i for i, k in enumerate(KIND_ORDER)}   # меньше = «сильнее»

LB = r"(?:(?<!\w)|(?<=\\[nrtb]))"      # левая граница слова (или экранирование \n \t \r \b)
RB = r"(?!\w)"                         # правая граница слова
SEP = r"[\\/]"
PLACEHOLDERS = (("{LB}", LB), ("{RB}", RB), ("{SEP}", SEP))

RULE_TYPES = ("regex", "words", "whole_literal")
RULE_KEYS = {
    "regex": {"type", "regex", "name", "name_from_group", "lower", "prefix", "ignore_case", "claims_span",
              "avoid_claimed", "context_filter", "only_in_strings"},
    "words": {"type", "list", "ignore_case", "lower", "claims_span", "avoid_claimed", "only_in_strings"},
    "whole_literal": {"type", "list", "skip_exact"},
}


class NamesError(Exception):
    """Файл имён донора отсутствует или составлен неверно: слова — в тексте исключения."""


class Hit(NamedTuple):
    file: str
    line: int
    group: str
    name: str
    kind: str
    text: str        # строка файла без крайних пробелов (ключ исключений), табуляция → пробел


# ---------------------------------------------------------------- проверки окружения
def ctx_dash_dot_slash_quote(text, a, b):
    """Короткое слово считается именем только рядом с «-», «.», «/» или в кавычках."""
    prev = text[a - 1] if a > 0 else ""
    nxt = text[b] if b < len(text) else ""
    nxt2 = text[b + 1] if b + 1 < len(text) else ""
    if prev and prev in "-./":
        return True
    if nxt in ("-", "/"):
        return True
    if nxt == "." and (nxt2.isalnum() or nxt2 == "_"):
        return True
    if prev and nxt and prev in "'\"`" and nxt in "'\"`":
        return True
    return False


CONTEXT_FILTERS = {"dash_dot_slash_quote": ctx_dash_dot_slash_quote}


# ---------------------------------------------------------------- правила и загрузка данных
class Rule:
    def __init__(self, group, spec, where, lists):
        self.group = group
        self.kind = spec.get("type", "regex")
        self.where = where
        if self.kind not in RULE_TYPES:
            raise NamesError("%s: неизвестный тип правила «%s» (допустимы: %s)" % (where, self.kind, ", ".join(RULE_TYPES)))
        for key in spec:
            if key not in RULE_KEYS[self.kind] and not key.startswith("_"):
                raise NamesError("%s: неизвестный ключ «%s» у правила типа %s" % (where, key, self.kind))
        self.claims_span = bool(spec.get("claims_span", False))
        self.avoid_claimed = bool(spec.get("avoid_claimed", False))
        self.only_in_strings = bool(spec.get("only_in_strings", False))
        self.lower = bool(spec.get("lower", False))
        self.prefix = spec.get("prefix", "")
        self.name = spec.get("name")
        self.name_group = spec.get("name_from_group")
        self.filter = None
        self.rx = None
        self.words = {}
        self.skip_exact = bool(spec.get("skip_exact", True))
        flags = re.I if spec.get("ignore_case") else 0
        if self.kind == "regex":
            if not isinstance(spec.get("regex"), str):
                raise NamesError("%s: у правила regex нет образца" % where)
            if (self.name is None) == (self.name_group is None):
                raise NamesError("%s: нужен ровно один из ключей name / name_from_group" % where)
            pattern = spec["regex"]
            for token, value in PLACEHOLDERS:
                pattern = pattern.replace(token, value)
            self.rx = self._compile(pattern, flags)
            fname = spec.get("context_filter")
            if fname is not None:
                if fname not in CONTEXT_FILTERS:
                    raise NamesError("%s: неизвестная проверка окружения «%s»" % (where, fname))
                self.filter = CONTEXT_FILTERS[fname]
        else:
            lname = spec.get("list")
            if lname not in lists:
                raise NamesError("%s: нет списка «%s» в разделе lists" % (where, lname))
            words = lists[lname]
            if self.kind == "words":
                if words:
                    ordered = sorted(words, key=len, reverse=True)
                    self.rx = self._compile(LB + "(" + "|".join(re.escape(w) for w in ordered) + ")" + RB, flags)
                self.name_group = 1
            else:
                self.words = {w.casefold(): w for w in words}
                self.exact = set(words)

    def _compile(self, pattern, flags):
        try:
            return re.compile(pattern, flags)
        except re.error as e:
            raise NamesError("%s: образец не компилируется: %s" % (self.where, e))

    def name_of(self, m):
        if self.name is not None:
            return self.name
        g = m.group(self.name_group)
        return self.prefix + (g.lower() if self.lower else g)

    def matches(self, text, literals):
        """-> [(начало, конец, имя)] по тексту файла; literals — [(начало, конец, значение)] строковых литералов."""
        out = []
        if self.kind == "whole_literal":
            for a, b, value in literals:
                if value.casefold() in self.words and not (self.skip_exact and value in self.exact):
                    out.append((a, b, value))
            return out
        if self.rx is None:
            return out
        if self.only_in_strings:
            for a, b, _value in literals:
                for m in self.rx.finditer(text[a:b]):
                    s, e = a + m.start(), a + m.end()
                    if self.filter is None or self.filter(text, s, e):
                        out.append((s, e, self.name_of(m)))
            return out
        for m in self.rx.finditer(text):
            if self.filter is None or self.filter(text, m.start(), m.end()):
                out.append((m.start(), m.end(), self.name_of(m)))
        return out


class Names:
    def __init__(self, groups, lists):
        self.groups = groups      # {группа: [Rule]}
        self.lists = lists
        self.rules = [r for rules in groups.values() for r in rules]


def parse_names(data, where):
    if not isinstance(data, dict):
        raise NamesError("%s: корень файла имён должен быть объектом" % where)
    lists = data.get("lists", {})
    groups_raw = data.get("groups", {})
    if not isinstance(lists, dict) or not isinstance(groups_raw, dict):
        raise NamesError("%s: lists и groups должны быть объектами" % where)
    lists = {k: v for k, v in lists.items() if not k.startswith("_")}      # «_…» — пояснения человеку
    for key, words in lists.items():
        if not isinstance(words, list) or not all(isinstance(w, str) and w for w in words):
            raise NamesError("%s: список «%s» должен быть списком непустых строк" % (where, key))
    groups = collections.OrderedDict()
    for gname, rules in groups_raw.items():
        if gname.startswith("_"):
            continue
        if not isinstance(rules, list):
            raise NamesError("%s: группа «%s» должна быть списком правил" % (where, gname))
        compiled = []
        for i, spec in enumerate(rules, start=1):
            if not isinstance(spec, dict):
                raise NamesError("%s: группа «%s», правило %d — не объект" % (where, gname, i))
            compiled.append(Rule(gname, spec, "%s: группа «%s», правило %d" % (where, gname, i), lists))
        groups[gname] = compiled
    return Names(groups, lists)


def load_names(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            raw = fh.read()
    except OSError:
        raise NamesError("нет файла имён донора: %s" % path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise NamesError("файл имён донора не читается как JSON: %s: %s" % (path, e))
    return parse_names(data, str(path))


# ---------------------------------------------------------------- чтение файлов
def read_text(raw):
    t = raw.decode("utf-8", errors="replace")
    if t.startswith("﻿"):
        t = t[1:]
    return t.replace("\r\n", "\n")


def line_starts_of(text):
    ls = [0]
    for m in re.finditer("\n", text):
        ls.append(m.end())
    return ls


def normalize_line(line):
    """Ключ строки для перечня исключений: без крайних пробелов, табуляция и возврат каретки → пробел."""
    return line.replace("\t", " ").replace("\r", " ").strip()


# ---------------------------------------------------------------- интервалы
def merge_intervals(iv):
    iv = sorted(iv)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


class Intervals:
    def __init__(self, iv):
        self.iv = merge_intervals(iv)
        self.starts = [a for a, _ in self.iv]

    def has(self, off):
        i = bisect.bisect_right(self.starts, off) - 1
        return i >= 0 and off < self.iv[i][1]


def overlaps(spans, a, b):
    for s, e in spans:
        if a < e and s < b:
            return True
    return False


# ---------------------------------------------------------------- Python: печатники и текстовые позиции
STR_METHODS = {"format", "join", "strip", "lstrip", "rstrip", "replace", "upper", "lower", "title", "capitalize",
               "ljust", "rjust", "center", "zfill", "casefold", "swapcase", "removeprefix", "removesuffix",
               "format_map", "expandtabs"}
PASS_FUNCS = {"str", "repr", "ascii", "dedent", "indent", "fill", "wrap", "shorten"}
STD_SINKS = {"print", "sys.stdout.write", "sys.stderr.write", "stdout.write", "stderr.write", "sys.exit", "exit"}
ARGPARSE_CTORS = {"ArgumentParser", "add_parser", "add_argument_group", "add_mutually_exclusive_group"}
ARGPARSE_TEXT_KW = {"description", "epilog", "usage"}


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def text_leaves(expr):
    """Узлы выражения, текст которых попадёт в вывод: строковые константы и имена."""
    out = []

    def go(n):
        if isinstance(n, ast.Constant):
            if isinstance(n.value, str):
                out.append(n)
        elif isinstance(n, ast.Name):
            out.append(n)
        elif isinstance(n, ast.JoinedStr):
            for v in n.values:
                if isinstance(v, ast.Constant):
                    go(v)
                elif isinstance(v, ast.FormattedValue):
                    go(v.value)
        elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mod)):
            go(n.left)
            go(n.right)
        elif isinstance(n, ast.IfExp):
            go(n.body)
            go(n.orelse)
        elif isinstance(n, ast.BoolOp):
            for v in n.values:
                go(v)
        elif isinstance(n, (ast.Tuple, ast.List, ast.Set)):
            for v in n.elts:
                go(v)
        elif isinstance(n, ast.Starred):
            go(n.value)
        elif isinstance(n, ast.Subscript):
            go(n.value)
        elif isinstance(n, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            go(n.elt)
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in STR_METHODS:
                go(f.value)
                if f.attr in ("format", "join", "format_map"):
                    for a in n.args:
                        go(a)
                    for k in n.keywords:
                        go(k.value)
            elif (isinstance(f, ast.Name) and f.id in PASS_FUNCS) or (isinstance(f, ast.Attribute) and f.attr in PASS_FUNCS):
                for a in n.args:
                    go(a)

    go(expr)
    return out


class FuncInfo:
    def __init__(self, path, name, node, is_method):
        self.path = path
        self.name = name
        self.node = node
        self.is_method = is_method
        a = node.args
        self.pos = [x.arg for x in a.posonlyargs + a.args]
        self.vararg = a.vararg.arg if a.vararg else None
        self.allparams = set(self.pos) | {x.arg for x in a.kwonlyargs}
        if a.vararg:
            self.allparams.add(a.vararg.arg)
        if a.kwarg:
            self.allparams.add(a.kwarg.arg)
        self.printed = set()


class ModInfo:
    def __init__(self, path, tree):
        self.path = path
        self.stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        self.tree = tree
        self.funcs = []
        self.local_defs = collections.defaultdict(list)
        self.imp_names = {}
        self.imp_mods = {}
        method_ids = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                for b in n.body:
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_ids.add(id(b))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fi = FuncInfo(path, n.name, n, id(n) in method_ids)
                self.funcs.append(fi)
                self.local_defs[n.name].append(fi)
            elif isinstance(n, ast.ImportFrom):
                stem = (n.module or "").split(".")[-1]
                for al in n.names:
                    if n.module is None or n.level:
                        self.imp_mods[al.asname or al.name] = al.name
                    self.imp_names[al.asname or al.name] = (stem, al.name)
            elif isinstance(n, ast.Import):
                for al in n.names:
                    self.imp_mods[al.asname or al.name.split(".")[0]] = al.name.split(".")[-1]


class Registry:
    def __init__(self):
        self.mods = {}
        self.by_stem = collections.defaultdict(list)

    def add(self, path, tree):
        m = ModInfo(path, tree)
        self.mods[path] = m
        self.by_stem[m.stem].append(m)

    def resolve(self, mod, call):
        """-> [(FuncInfo, shift)] кандидаты, на которые может указывать вызов."""
        f = call.func
        res = []
        if isinstance(f, ast.Name):
            cands = list(mod.local_defs.get(f.id, ()))
            if not cands and f.id in mod.imp_names:
                stem, orig = mod.imp_names[f.id]
                for m in self.by_stem.get(stem, ()):
                    cands += m.local_defs.get(orig, ())
            res = [(c, 0) for c in cands if not c.is_method]
        elif isinstance(f, ast.Attribute):
            base = f.value
            if isinstance(base, ast.Name) and base.id in mod.imp_mods:
                for m in self.by_stem.get(mod.imp_mods[base.id], ()):
                    res += [(c, 0) for c in m.local_defs.get(f.attr, ()) if not c.is_method]
            else:
                res = [(c, 1) for c in mod.local_defs.get(f.attr, ()) if c.is_method]
        return res

    def shown_exprs(self, mod, call):
        """Выражения-аргументы вызова, строки которых уходят человеку."""
        name = dotted(call.func)
        last = name.rsplit(".", 1)[-1] if name else ""
        out = []
        if name == "print":
            out += list(call.args)
        elif name in STD_SINKS:
            out += call.args[:1]
        for k in call.keywords:
            if k.arg == "help":
                out.append(k.value)
            elif k.arg in ARGPARSE_TEXT_KW and last in ARGPARSE_CTORS:
                out.append(k.value)
        for fi, shift in self.resolve(mod, call):
            if not fi.printed:
                continue
            for i, a in enumerate(call.args):
                j = i + shift
                pname = fi.pos[j] if j < len(fi.pos) else fi.vararg
                if pname and pname in fi.printed:
                    out.append(a)
            for k in call.keywords:
                if k.arg and k.arg in fi.printed:
                    out.append(k.value)
        return out

    def solve_printers(self):
        changed = True
        rounds = 0
        while changed and rounds < 12:
            changed = False
            rounds += 1
            for mod in self.mods.values():
                for fi in mod.funcs:
                    for call in ast.walk(fi.node):
                        if not isinstance(call, ast.Call):
                            continue
                        for e in self.shown_exprs(mod, call):
                            for leaf in text_leaves(e):
                                if isinstance(leaf, ast.Name) and leaf.id in fi.allparams and leaf.id not in fi.printed:
                                    fi.printed.add(leaf.id)
                                    changed = True
        return rounds


class PyFile:
    """Интервалы комментариев, docstring и «показываемых» литералов одного .py-файла."""

    def __init__(self, path, text, reg):
        self.path = path
        self.reg = reg
        self.problems = []
        self.lines = text.split("\n")
        self.ls = line_starts_of(text)
        self.lines_b = [None] * len(self.lines)
        self._literals = None
        comments, docs, shown = [], [], []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    comments.append((self.off(tok.start[0], tok.start[1]), self.off(tok.end[0], tok.end[1])))
        except (tokenize.TokenError, SyntaxError, IndentationError) as e:
            self.problems.append("tokenize: %s" % e)
        mod = reg.mods.get(path)
        if mod is not None:
            for node in ast.walk(mod.tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    b = node.body
                    if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                            and isinstance(b[0].value.value, str):
                        docs.append(self.node_span(b[0].value))
                if isinstance(node, ast.Call):
                    for e in reg.shown_exprs(mod, node):
                        for leaf in text_leaves(e):
                            if isinstance(leaf, ast.Constant):
                                shown.append(self.node_span(leaf))
        else:
            self.problems.append("ast: не разобран")
        self.c, self.d, self.s = Intervals(comments), Intervals(docs), Intervals(shown)

    def off(self, row, col):
        return self.ls[row - 1] + col

    def bcol(self, row, bcol):
        s = self.lines[row - 1]
        if self.lines_b[row - 1] is None:
            self.lines_b[row - 1] = s.encode("utf-8")
        b = self.lines_b[row - 1]
        if len(b) == len(s):
            return bcol
        return len(b[:bcol].decode("utf-8", "replace"))

    def node_span(self, n):
        return (self.off(n.lineno, self.bcol(n.lineno, n.col_offset)),
                self.off(n.end_lineno, self.bcol(n.end_lineno, n.end_col_offset)))

    def kind_at(self, off):
        if self.c.has(off):
            return "comment"
        if self.d.has(off):
            return "docstring"
        if self.s.has(off):
            return "shown"
        return "code"

    def string_literals(self):
        """[(начало, конец, значение)] всех строковых литералов файла — по порядку в тексте."""
        if self._literals is None:
            out = []
            mod = self.reg.mods.get(self.path)
            if mod is not None:
                for n in ast.walk(mod.tree):
                    if isinstance(n, ast.Constant) and isinstance(n.value, str):
                        a, b = self.node_span(n)
                        out.append((a, b, n.value))
            out.sort(key=lambda t: (t[0], t[1]))
            self._literals = out
        return self._literals


def parse_py(text):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(text)


# ---------------------------------------------------------------- прогон
class Scanner:
    """Разбирает ВСЕ .py-файлы набора (печатники определяются между файлами) и ищет имена в нужных."""

    def __init__(self, texts, names):
        self.texts = texts
        self.names = names
        self.reg = Registry()
        self.parse_failed = []         # [(путь, причина)]
        for path, text in texts.items():
            if not path.lower().endswith(".py"):
                continue
            try:
                self.reg.add(path, parse_py(text))
            except (SyntaxError, ValueError) as e:
                self.parse_failed.append((path, str(e)))
        self.rounds = self.reg.solve_printers()

    def scan(self, path):
        """-> (список Hit, список замечаний о разборе файла). Файл не разобран — (None, [причина])."""
        text = self.texts[path]
        if path not in self.reg.mods:
            reason = next((r for p, r in self.parse_failed if p == path), "не разобран")
            return None, ["ast: %s" % reason]
        pf = PyFile(path, text, self.reg)
        lines = text.split("\n")
        ls = line_starts_of(text)
        literals = pf.string_literals()
        raw = []
        claimed = []
        for rule in self.names.rules:
            if rule.claims_span:
                for a, b, name in rule.matches(text, literals):
                    raw.append((a, rule.group, name))
                    claimed.append((a, b))
        for rule in self.names.rules:
            if rule.claims_span:
                continue
            for a, b, name in rule.matches(text, literals):
                if rule.avoid_claimed and overlaps(claimed, a, b):
                    continue
                raw.append((a, rule.group, name))
        best = {}
        for a, group, name in raw:
            line = bisect.bisect_right(ls, a)
            kind = pf.kind_at(a)
            key = (line, group, name)
            cur = best.get(key)
            if cur is None or KIND_RANK[kind] < KIND_RANK[cur]:
                best[key] = kind
        hits = [Hit(path, line, group, name, kind, normalize_line(lines[line - 1]))
                for (line, group, name), kind in best.items()]
        hits.sort(key=lambda h: (h.line, h.group, h.name))
        return hits, pf.problems
