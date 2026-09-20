# turn-status

A `UserPromptSubmit` hook that runs a command you configure and puts its short answer into
the turn. A number the turn brings, instead of a rule the agent has to remember.

([по-русски](README.ru.md))

## The problem

Some facts an agent needs are cheap to measure and expensive to *remember to measure*: how
many messages are waiting in the team's queue, how long since anyone read them, whether the
build is red, how much of the budget is left.

Written as a rule — "check the queue regularly" — they are forgotten precisely when they
matter, because the moment to check is the moment you are busy with something else. No amount
of willingness fixes this: the cost of remembering is paid continuously, and the cost of
forgetting shows up once, later, as work done against a state that had already changed.

Measured on the way in, the same fact costs one process and needs no discipline at all.

## What it does

Before each turn, it runs every configured source, cleans the output, and hands it to the
model as `additionalContext`. When nothing is configured, when no source has anything to say,
or when anything at all goes wrong, it stays silent and the turn proceeds untouched.

It never blocks. A `UserPromptSubmit` hook that exits non-zero eats the human's turn, and a
broken status line has no such right — so the hook exits 0 always, and the worst it can do is
say nothing.

## Configuration

A `.turn-status.json` in the project root (parent directories are searched too):

```json
{
  "enabled": true,
  "maxChars": 1200,
  "oneLine": true,
  "separator": "\n",
  "cutMark": " ...[cut]",
  "activateOnly": { "markerPath": ".mezosync/mezosync.db" },
  "sources": [
    {
      "name": "queue",
      "command": "python",
      "args": ["tools/unread-notes.py", "--session-id", "{sessionId}"],
      "timeoutMs": 4000,
      "maxChars": 400,
      "prefix": "",
      "onFailure": "loud",
      "failMessage": "The queue count did not arrive ({output}). Until it does, count by hand."
    }
  ]
}
```

| Key | Meaning | Default |
|---|---|---|
| `enabled` | off switch for the whole plugin | `true` |
| `sources` | what to measure; empty means the plugin does nothing | `[]` |
| `maxChars` | ceiling for the whole block, paid every turn | `1200` |
| `oneLine` | fold each source's output into one line | `true` |
| `separator` | between sources | `"\n"` |
| `cutMark` | what a cut looks like — make it visible | `" ...[cut]"` |
| `activateOnly.markerPath` | only work inside a tree containing this file | `null` |

Per source: `name`, `command`, `args`, `timeoutMs` (3000), `maxChars` (500), `prefix`,
`onFailure` (`silent` | `loud`), `failMessage`, `enabled`.

`{sessionId}`, `{cwd}`, `{projectDir}` and `{transcriptPath}` are substituted into `command`
and into each argument. The substitution goes into the argument array and the command runs
without a shell, so spaces and quotes in a value are safe. An unknown placeholder is left
as it is, so a typo shows up in the output instead of silently becoming an empty string.

**The prompt is never substituted.** The human's text does not belong in a command line.

The configuration names a command to run, so treat the file as a script you execute rather
than as data. `TURN_STATUS_DISABLE=1` switches everything off.

## Nothing is cached

A cached measurement is a confident lie: it will say thirteen when there are twenty, and it
will be believed exactly because it came from a machine rather than from memory. There is no
cache and no way to turn one on. If a source is too expensive to run on every turn, it is the
wrong source for this plugin — measure it elsewhere and have the source read the result.

## What it does not do

- It does not check that the answer is true, only that the source answered. A source that
  prints a wrong number will have its wrong number delivered faithfully.
- It does not fire on messages that arrive from other agents or tools, only on turns that
  begin with a prompt.
- It does not retry. A source that fails this turn is simply missing from this turn.
- A silent turn and a working-but-quiet source look the same from inside the conversation.
  Check from outside (below) rather than concluding from silence.

## Checking it from outside

A plugin that is switched off cannot tell you it is switched off. Make the source begin its
line with a fixed word, then look for that word in the session transcripts: the hook's output
arrives there as a `hook_additional_context` attachment on the human's turn, so a plain search
over the transcript files answers "is it arriving at all" without asking the agent about itself.

And to see exactly what would reach a turn, without installing anything:

```
echo {"session_id":"x","cwd":"<project>","hook_event_name":"UserPromptSubmit","prompt":"x"} | node hooks/status.js
```

## Tests

```
node test/run.js
```

53 checks, no dependencies: the contract with the turn (nothing ever exits non-zero), the
switches, the shape of the output, the substitution, every kind of source failure, and a test
that proves the source really runs twice in two turns.

## License

Apache-2.0.
