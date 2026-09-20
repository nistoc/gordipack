#!/usr/bin/env node
'use strict';
/**
 * Test matrix for turn-status. Every case runs a real hook process.
 * Usage:  node test/run.js
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HOOK = path.join(__dirname, '..', 'hooks', 'status.js');
const MARKER = '.mezosync/marker.db';

function tempProject(configObject, markerPath) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'turn-status-test-'));
  if (configObject !== null && configObject !== undefined) {
    const body = typeof configObject === 'string' ? configObject : JSON.stringify(configObject);
    fs.writeFileSync(path.join(dir, '.turn-status.json'), body, 'utf8');
  }
  if (markerPath) {
    const full = path.join(dir, markerPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, 'marker', 'utf8');
  }
  return dir;
}

/** A source that is a node one-liner: no python, no shell, no network. */
function probe(code, extra) {
  return Object.assign({ name: 'probe', command: process.execPath, args: ['-e', code] }, extra || {});
}

function run(dir, env, payloadExtra) {
  const payload = Object.assign({
    session_id: 'session-abc',
    transcript_path: 'C:/chats/session-abc.jsonl',
    cwd: dir,
    hook_event_name: 'UserPromptSubmit',
    prompt: 'привет'
  }, payloadExtra || {});
  const input = typeof payload === 'string' ? payload : JSON.stringify(payload);
  const res = spawnSync(process.execPath, [HOOK], {
    input: input,
    encoding: 'utf8',
    env: Object.assign({}, process.env, env || {})
  });
  let context = null;
  let broken = false;
  const out = (res.stdout || '').trim();
  if (out) {
    try {
      const parsed = JSON.parse(out);
      const h = parsed.hookSpecificOutput || {};
      context = typeof h.additionalContext === 'string' ? h.additionalContext : null;
      if (h.hookEventName !== 'UserPromptSubmit') broken = true;
    } catch (e) {
      broken = true;
    }
  }
  return { code: res.status, context: context, broken: broken, stdout: res.stdout };
}

function raw(input) {
  const res = spawnSync(process.execPath, [HOOK], { input: input, encoding: 'utf8' });
  return { code: res.status, stdout: (res.stdout || '').trim() };
}

let failures = 0;
let checks = 0;

function check(name, condition, detail) {
  checks++;
  if (!condition) {
    failures++;
    console.log('FAIL  ' + name + (detail ? '  — ' + detail : ''));
  }
}

function expectSilent(name, result) {
  check(name, result.context === null && !result.broken && !result.stdout.trim(),
    'expected no output, got: ' + JSON.stringify(result.stdout));
  check(name + ' (exit code)', result.code === 0, 'exit code ' + result.code);
}

function expectContext(name, result, needle) {
  check(name, result.context !== null && result.context.indexOf(needle) !== -1,
    'expected to contain ' + JSON.stringify(needle) + ', got ' + JSON.stringify(result.context));
  check(name + ' (exit code)', result.code === 0, 'exit code ' + result.code);
}

// ── the contract with the turn ──────────────────────────────────────────────
// A UserPromptSubmit hook that exits non-zero eats the human's turn. Nothing
// below is allowed to do that, whatever it is handed.

for (const [name, input] of [['input that is not JSON', 'this is not json'],
                             ['empty input', ''],
                             ['input that is only spaces', '   '],
                             ['input that is a JSON array', '[1,2,3]']]) {
  const r = raw(input);
  check(name, r.stdout === '', 'expected no output, got ' + JSON.stringify(r.stdout));
  check(name + ' (exit code)', r.code === 0, 'exit code ' + r.code);
}

expectSilent('configuration file is broken JSON',
  run(tempProject('{ this is not json', MARKER)));

// ── when the plugin works at all ────────────────────────────────────────────

expectSilent('no configuration file at all', run(tempProject(null, MARKER)));
expectSilent('no sources configured', run(tempProject({ sources: [] }, MARKER)));

const working = { sources: [probe('process.stdout.write("измерено: 7")')], activateOnly: { markerPath: MARKER } };

expectSilent('switched off by configuration',
  run(tempProject(Object.assign({}, working, { enabled: false }), MARKER)));
expectSilent('switched off by the environment',
  run(tempProject(working, MARKER), { TURN_STATUS_DISABLE: '1' }));
expectSilent('marker file missing from the tree',
  run(tempProject(working, null)));
expectContext('marker file present',
  run(tempProject(working, MARKER)), 'измерено: 7');

// ── what comes out ──────────────────────────────────────────────────────────

expectContext('the source line arrives verbatim',
  run(tempProject({ sources: [probe('process.stdout.write("строка от источника")')] })),
  'строка от источника');

const two = run(tempProject({
  sources: [probe('process.stdout.write("первая")'), probe('process.stdout.write("вторая")')]
}));
check('two sources arrive in the configured order',
  two.context === 'первая\nвторая', JSON.stringify(two.context));

expectSilent('a source that prints nothing keeps the whole hook silent',
  run(tempProject({ sources: [probe('process.stdout.write("")')] })));
expectSilent('a source that prints only spaces is the same as nothing',
  run(tempProject({ sources: [probe('process.stdout.write("   \\n  ")')] })));

const folded = run(tempProject({ sources: [probe('process.stdout.write("одна\\nдве\\nтри")')] }));
check('multi-line output is folded into one line',
  folded.context && folded.context.indexOf('\n') === -1 && folded.context.indexOf('одна две три') !== -1,
  JSON.stringify(folded.context));

const kept = run(tempProject({
  oneLine: false,
  sources: [probe('process.stdout.write("одна\\nдве")')]
}));
check('oneLine false keeps the shape', kept.context === 'одна\nдве', JSON.stringify(kept.context));

const cutSource = run(tempProject({
  cutMark: ' ...[cut]',
  sources: [probe('process.stdout.write("я".repeat(200))', { maxChars: 40 })]
}));
check('output longer than the source ceiling is cut',
  cutSource.context && cutSource.context.length <= 40 && /\.\.\.\[cut\]$/.test(cutSource.context),
  JSON.stringify(cutSource.context));

const cutBlock = run(tempProject({
  maxChars: 30,
  sources: [probe('process.stdout.write("а".repeat(40))'), probe('process.stdout.write("б".repeat(40))')]
}));
check('the whole block is cut at its own ceiling',
  cutBlock.context && cutBlock.context.length <= 30 && /\[cut\]$/.test(cutBlock.context),
  JSON.stringify(cutBlock.context));

const dirty = run(tempProject({
  sources: [probe('process.stdout.write("\\u001b[31mкрасным\\u001b[0m\\u0007 текстом")')]
}));
check('colour and control characters are stripped',
  dirty.context === 'красным текстом', JSON.stringify(dirty.context));

expectContext('a prefix is put in front of the source output',
  run(tempProject({ sources: [probe('process.stdout.write("7")', { prefix: 'очередь: ' })] })),
  'очередь: 7');

// ── what the source is told about the turn ──────────────────────────────────

const argvCode = 'process.stdout.write(process.argv.length - 1 + ":" + process.argv.slice(1).join("|"))';

expectContext('the session identifier reaches the source',
  run(tempProject({
    sources: [Object.assign(probe(argvCode), { args: ['-e', argvCode, '{sessionId}'] })]
  })), 'session-abc');

expectContext('the transcript path reaches the source',
  run(tempProject({
    sources: [Object.assign(probe(argvCode), { args: ['-e', argvCode, '{transcriptPath}'] })]
  })), 'session-abc.jsonl');

expectContext('an unknown placeholder is left alone, so a typo is visible',
  run(tempProject({
    sources: [Object.assign(probe(argvCode), { args: ['-e', argvCode, '{nope}'] })]
  })), '{nope}');

const spaced = run(tempProject({
  sources: [Object.assign(probe(argvCode), { args: ['-e', argvCode, 'два слова здесь'] })]
}));
check('a value with spaces arrives as one argument, not three',
  spaced.context && spaced.context.indexOf('1:два слова здесь') !== -1, JSON.stringify(spaced.context));

// ── when the source fails ───────────────────────────────────────────────────

expectSilent('a source that exits non-zero is silent by default',
  run(tempProject({ sources: [probe('process.stderr.write("boom"); process.exit(3)')] })));

expectContext('a loud failure says which source and what it said',
  run(tempProject({
    sources: [probe('process.stderr.write("нет базы"); process.exit(3)', {
      name: 'очередь', onFailure: 'loud', failMessage: 'ОТКАЗ {name}: {output}'
    })]
  })), 'ОТКАЗ очередь: нет базы');

expectSilent('a command that does not exist does not crash the hook',
  run(tempProject({ sources: [{ name: 'gone', command: 'turn-status-no-such-command-xyz', args: [] }] })));

expectSilent('a source slower than its timeout is dropped',
  run(tempProject({
    sources: [probe('Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 600); process.stdout.write("поздно")',
      { timeoutMs: 80 })]
  })));

const survivor = run(tempProject({
  sources: [
    probe('process.exit(1)'),
    probe('process.stdout.write("вторая всё равно измерена")')
  ]
}));
check('one failing source does not silence the next one',
  survivor.context === 'вторая всё равно измерена', JSON.stringify(survivor.context));

// ── nothing is cached ───────────────────────────────────────────────────────
// The whole point: a number that is stale is a confident lie, and it is believed
// precisely because a machine said it.

const cacheDir = tempProject(null, MARKER);
const tally = path.join(cacheDir, 'runs.txt').split('\\').join('/');
fs.writeFileSync(path.join(cacheDir, '.turn-status.json'), JSON.stringify({
  sources: [probe('require("fs").appendFileSync("' + tally + '", "x"); process.stdout.write("измерено")')]
}), 'utf8');
run(cacheDir);
run(cacheDir);
const runs = fs.readFileSync(path.join(cacheDir, 'runs.txt'), 'utf8');
check('the source really runs on every turn (nothing is cached)',
  runs === 'xx', 'expected two runs, file holds ' + JSON.stringify(runs));

// ── result ──────────────────────────────────────────────────────────────────

if (failures) {
  console.log('\n' + failures + ' of ' + checks + ' checks failed');
  process.exit(1);
}
console.log('all ' + checks + ' checks pass');
