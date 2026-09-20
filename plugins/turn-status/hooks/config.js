'use strict';
/**
 * Shared configuration loading for turn-status.
 *
 * A project tunes the plugin with a .turn-status.json file in its root (the
 * plugin also looks in parent directories). Everything is optional, and with
 * nothing configured the plugin does nothing at all.
 *
 * The configuration names a command to run, so treat the file as a script you
 * execute rather than as data: TURN_STATUS_DISABLE=1 switches everything off.
 */

const fs = require('fs');
const path = require('path');

const CONFIG_NAME = '.turn-status.json';

const DEFAULTS = {
  enabled: true,

  // What to measure. Each entry:
  //   { name, command, args, timeoutMs, maxChars, prefix, onFailure, failMessage, enabled }
  // Empty by default: a plugin with nothing to measure must stay silent.
  sources: [],

  // Ceiling for the whole block that goes into the turn. It is paid on every turn.
  maxChars: 1200,

  // A measurement is one line. Set to false when a source has to keep its shape.
  oneLine: true,

  separator: '\n',

  // What a cut looks like. It has to be visible: when the tail of the line is a
  // command to run, a silently cut command is dead and still looks alive.
  cutMark: ' ...[cut]',

  // When set, the plugin only works inside a tree that contains this file.
  activateOnly: null
};

function findUp(startDir, relPath, levels) {
  let dir = startDir;
  for (let i = 0; i < (levels || 12); i++) {
    if (!dir) break;
    const candidate = path.join(dir, relPath);
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch (e) { /* unreadable directory — keep walking up */ }
    const parent = path.dirname(dir);
    if (!parent || parent === dir) break;
    dir = parent;
  }
  return null;
}

function loadConfig(projectDir) {
  const cfg = JSON.parse(JSON.stringify(DEFAULTS));
  const found = projectDir ? findUp(projectDir, CONFIG_NAME) : null;
  if (found) {
    try {
      const raw = JSON.parse(fs.readFileSync(found, 'utf8'));
      for (const key of Object.keys(DEFAULTS)) {
        if (raw[key] !== undefined) cfg[key] = raw[key];
      }
    } catch (e) { /* a broken configuration must never break the turn */ }
  }
  if (process.env.TURN_STATUS_DISABLE === '1') cfg.enabled = false;
  if (!Array.isArray(cfg.sources)) cfg.sources = [];
  if (!(cfg.maxChars > 0)) cfg.maxChars = DEFAULTS.maxChars;
  if (typeof cfg.separator !== 'string') cfg.separator = DEFAULTS.separator;
  if (typeof cfg.cutMark !== 'string') cfg.cutMark = DEFAULTS.cutMark;
  return cfg;
}

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch (e) {
    return '';
  }
}

function projectDirOf(input) {
  return process.env.CLAUDE_PROJECT_DIR ||
    (input && typeof input.cwd === 'string' ? input.cwd : '') ||
    process.cwd();
}

function active(cfg, projectDir) {
  if (cfg.enabled === false) return false;
  if (cfg.activateOnly && cfg.activateOnly.markerPath) {
    if (!findUp(projectDir, cfg.activateOnly.markerPath)) return false;
  }
  return true;
}

module.exports = { CONFIG_NAME, DEFAULTS, findUp, loadConfig, readStdin, projectDirOf, active };
