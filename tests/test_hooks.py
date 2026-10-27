# -*- coding: utf-8 -*-
"""hooks/*.json: на вход — JSON, как его даёт Claude Code; на выходе — ответ hook и код.

Оба hook написаны на PowerShell ("shell": "powershell"). Их команды запускаются здесь так
же, как их запускает Claude Code: отдельный процесс PowerShell, JSON события — в stdin.
Без PowerShell на машине такие тесты пропускаются; в CI PowerShell есть и на Linux (pwsh),
и на Windows (powershell.exe и pwsh) — там они и выполняются.

Проверяются только ASCII-части ответа: Windows PowerShell 5.1 пишет в канал в кодировке
консоли, и кириллица там может прийти знаками вопроса — это свойство среды, а не hook.
"""

import base64
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REPO_ROOT, Result, clean_env, run_python

HOOKS_DIR = REPO_ROOT / "hooks"
HOOK_FILES = sorted(HOOKS_DIR.glob("*.json"))
KNOWN_EVENTS = {"PreToolUse", "PostToolUse", "UserPromptSubmit", "Notification", "Stop",
                "SubagentStop", "PreCompact", "SessionStart", "SessionEnd"}

POWERSHELLS = [exe for exe in ("pwsh", "powershell") if shutil.which(exe)]
needs_powershell = pytest.mark.skipif(not POWERSHELLS, reason="PowerShell не установлен")
powershell_param = pytest.mark.parametrize(
    "ps", POWERSHELLS or ["pwsh"], ids=lambda exe: exe)


def hook_command(file_name, event):
    data = json.loads((HOOKS_DIR / file_name).read_text(encoding="utf-8"))
    entries = data["hooks"][event]
    commands = [h for entry in entries for h in entry["hooks"]]
    assert len(commands) == 1, f"{file_name}/{event}: ожидалась одна команда"
    return commands[0]


def run_hook(ps, command, payload, cwd, home, env_extra=None):
    """Запустить команду hook в PowerShell; payload (dict или str) — в stdin."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    # -EncodedCommand снимает вопрос экранирования кавычек командной строки Windows:
    # проверяется сам сценарий hook, а не то, как его процитировал вызывающий.
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    argv = [shutil.which(ps), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    env = clean_env(home, env_extra)
    p = subprocess.run(argv, cwd=str(cwd), input=stdin.encode("utf-8"),
                       capture_output=True, env=env, timeout=120)
    return Result(p.returncode, p.stdout.decode("utf-8", "replace"),
                  p.stderr.decode("utf-8", "replace"), argv[:4] + ["<команда hook>"])


def parse_output(res, event):
    """stdout hook → additionalContext; заодно проверка формы ответа Claude Code."""
    out = res.stdout.strip()
    assert out, "hook ничего не напечатал\n" + res.explain()
    data = json.loads(out)
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == event
    assert isinstance(hso["additionalContext"], str) and hso["additionalContext"]
    return hso["additionalContext"]


def event_payload(event, cwd, **extra):
    base = {
        "session_id": "00000000-0000-0000-0000-000000000000",
        "transcript_path": str(cwd / "transcript.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": event,
    }
    if event == "UserPromptSubmit":
        base["prompt"] = "привет"
    if event == "PreToolUse":
        base.update({"tool_name": "Bash", "tool_input": {"command": "ls"},
                     "tool_use_id": "toolu_test"})
    base.update(extra)
    return base


# ── Форма файлов hooks/ (без PowerShell) ─────────────────────────────────────────


@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda p: p.name)
def test_hook_file_is_valid_settings_fragment(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["hooks"]) <= KNOWN_EVENTS
    for event, entries in data["hooks"].items():
        assert entries, f"{event}: пустой список"
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                assert hook.get("shell") == "powershell"
                assert hook["command"].strip()


def test_plugin_hooks_json_points_to_existing_script():
    plugin = REPO_ROOT / "plugins" / "turn-status"
    data = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                for arg in hook.get("args", []):
                    if "${CLAUDE_PLUGIN_ROOT}" in arg:
                        rel = arg.replace("${CLAUDE_PLUGIN_ROOT}/", "")
                        assert (plugin / rel).is_file(), f"нет файла {rel}"


# ── time-injection.json ──────────────────────────────────────────────────────────

UTC_RE = re.compile(r"CURRENT_UTC_TIME=(\d{4}-\d\d-\d\d \d\d:\d\d) UTC")
LOCAL_RE = re.compile(r"CURRENT_LOCAL_TIME=(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ?(\S+)\.")


def _minutes_apart(a, b):
    return abs((a - b).total_seconds()) / 60


@needs_powershell
@powershell_param
def test_time_injection_prompt_gives_current_utc(ps, tmp_path):
    hook = hook_command("time-injection.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], event_payload("UserPromptSubmit", tmp_path),
                   tmp_path, tmp_path / "home")
    assert res.returncode == 0, res.explain()
    ctx = parse_output(res, "UserPromptSubmit")
    m = UTC_RE.search(ctx)
    assert m, ctx
    stamp = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    assert _minutes_apart(stamp, datetime.now(timezone.utc)) <= 3, ctx
    assert LOCAL_RE.search(ctx), ctx
    assert re.search(r"\d\d:\d\d UTC \(\d\d:\d\d ", ctx), "нет готовой метки «HH:mm UTC (HH:mm …)»"


@needs_powershell
@pytest.mark.skipif(sys.platform == "win32",
                    reason="часовой пояс процесса через TZ задаётся только вне Windows")
@powershell_param
def test_time_injection_utc_is_not_local_time(ps, tmp_path):
    """В поясе +09:00 метка UTC отстаёт от местной на 9 часов — UTC считает машина."""
    hook = hook_command("time-injection.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], event_payload("UserPromptSubmit", tmp_path),
                   tmp_path, tmp_path / "home", env_extra={"TZ": "Asia/Tokyo"})
    assert res.returncode == 0, res.explain()
    ctx = parse_output(res, "UserPromptSubmit")
    utc = datetime.strptime(UTC_RE.search(ctx).group(1), "%Y-%m-%d %H:%M")
    local_m = LOCAL_RE.search(ctx)
    local = datetime.strptime(local_m.group(1), "%Y-%m-%d %H:%M:%S")
    assert local_m.group(2) == "+09:00", ctx
    assert _minutes_apart(local - timedelta(hours=9), utc) <= 1, ctx


@needs_powershell
@powershell_param
def test_time_injection_step_time(ps, tmp_path):
    hook = hook_command("time-injection.json", "PreToolUse")
    res = run_hook(ps, hook["command"], event_payload("PreToolUse", tmp_path),
                   tmp_path, tmp_path / "home")
    assert res.returncode == 0, res.explain()
    ctx = parse_output(res, "PreToolUse")
    assert re.fullmatch(r"STEP_TIME=\d\d:\d\d:\d\d", ctx), ctx


@needs_powershell
@powershell_param
def test_time_injection_ignores_broken_input(ps, tmp_path):
    """Hook времени не читает stdin: битый JSON не мешает ему ответить."""
    hook = hook_command("time-injection.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], "{это не json", tmp_path, tmp_path / "home")
    assert res.returncode == 0, res.explain()
    assert UTC_RE.search(parse_output(res, "UserPromptSubmit"))


# ── owner-reply-reminder.json ────────────────────────────────────────────────────


def _fake_circuit(root):
    """Признак контура для hook — файл .mezosync/mezosync.db (содержимое не читается)."""
    (root / ".mezosync").mkdir(parents=True)
    (root / ".mezosync" / "mezosync.db").write_bytes(b"")
    return root


@needs_powershell
@powershell_param
def test_owner_reply_inside_circuit_points_to_its_rule(ps, tmp_path):
    container = _fake_circuit(tmp_path / "proj")
    cwd = container / "src" / "deep"
    cwd.mkdir(parents=True)
    hook = hook_command("owner-reply-reminder.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], event_payload("UserPromptSubmit", cwd),
                   tmp_path, tmp_path / "home")
    assert res.returncode == 0, res.explain()
    ctx = parse_output(res, "UserPromptSubmit")
    set_rule = str(container).replace("\\", "/") + "/.mezosync/scripts/set-rule.py"
    assert set_rule + " --key owner-reply-format --show" in ctx, ctx
    assert ctx.startswith("GORDI"), ctx


@needs_powershell
@powershell_param
def test_owner_reply_outside_circuit_is_silent(ps, tmp_path):
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    hook = hook_command("owner-reply-reminder.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], event_payload("UserPromptSubmit", cwd),
                   tmp_path, tmp_path / "home")
    assert res.returncode == 0, res.explain()
    assert res.stdout.strip() == "", res.explain()


@needs_powershell
@powershell_param
@pytest.mark.parametrize("bad", ["", "{это не json", '{"cwd": 42}'],
                         ids=["empty", "broken-json", "cwd-not-a-path"])
def test_owner_reply_bad_input_does_not_block(ps, tmp_path, bad):
    """Плохой вход: ни ответа, ни кода 2 (код 2 в Claude Code блокирует ход)."""
    hook = hook_command("owner-reply-reminder.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], bad, tmp_path, tmp_path / "home")
    assert res.returncode != 2, res.explain()
    assert "hookSpecificOutput" not in res.stdout, res.explain()


@needs_powershell
@powershell_param
def test_owner_reply_command_runs_on_fresh_circuit(ps, circuit):
    """Команда из напоминания исполнима в свежем контуре и показывает живое правило."""
    hook = hook_command("owner-reply-reminder.json", "UserPromptSubmit")
    res = run_hook(ps, hook["command"], event_payload("UserPromptSubmit", circuit.root),
                   circuit.root, circuit.home)
    ctx = parse_output(res, "UserPromptSubmit")
    m = re.search(r"python (\S+set-rule\.py) --key (\S+) --show", ctx)
    assert m, ctx
    shown = run_python(m.group(1), "--key", m.group(2), "--show", cwd=circuit.root,
                       env=circuit.env())
    assert shown.returncode == 0, shown.explain()
    assert "owner-reply-format" in shown.out, shown.explain()
