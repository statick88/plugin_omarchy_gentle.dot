#!/usr/bin/env node
/* Private stdin/stdout bridge for the T16 read-only pairing seam. */
import fs from "node:fs";
import path from "node:path";

const MAX_LINE = 16 * 1024;
const MAX_TOKEN = 4096;
const MAX_FRAME = 128 * 1024;
const CONNECT_TIMEOUT = 1500;
const HISTORY_TIMEOUT = 65_000;
let socket;
let token = "";
let connected = false;
let modelLabel;
let pendingHistory;

const emit = (value) => process.stdout.write(`${JSON.stringify(value)}\n`);
const refused = () => emit({ type: "error", message: "Request refused." });
const unavailable = () => emit({ type: "error", message: "Connection unavailable." });
const clean = (value) => typeof value === "string" ? value.replaceAll(token, "[redacted]").slice(0, 16384) : "";

function endpoint(value) {
  if (typeof value !== "string" || value.length > 256) return false;
  const match = /^ws:\/\/(127\.0\.0\.1|\[::1\]):([0-9]+)\/ws$/.exec(value);
  return match !== null && Number(match[2]) > 0 && Number(match[2]) <= 65535;
}

function historyTimeout(value) {
  return value === undefined ? HISTORY_TIMEOUT :
    Number.isInteger(value) && value > 0 && value <= HISTORY_TIMEOUT ? value : undefined;
}

function readToken(file) {
  if (typeof file !== "string" || !path.isAbsolute(file) || path.basename(file) !== "token") throw Error("refused");
  const parent = path.dirname(file);
  const dir = fs.lstatSync(parent);
  const parentMode = dir.mode & 0o777;
  if (!dir.isDirectory() || dir.isSymbolicLink() || dir.uid !== process.getuid() || ![0o700, 0o711].includes(parentMode)) throw Error("refused");
  const listed = fs.lstatSync(file);
  if (!listed.isFile() || listed.isSymbolicLink() || listed.uid !== process.getuid() || (listed.mode & 0o077) !== 0 || listed.size < 1 || listed.size > MAX_TOKEN) throw Error("refused");
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  try {
    const current = fs.fstatSync(fd);
    if (!current.isFile() || current.uid !== process.getuid() || (current.mode & 0o077) !== 0 || current.size < 1 || current.size > MAX_TOKEN || current.ino !== listed.ino || current.dev !== listed.dev) throw Error("refused");
    const bytes = fs.readFileSync(fd);
    const value = bytes.toString("utf8").trim();
    bytes.fill(0);
    if (!value || value.length > MAX_TOKEN) throw Error("refused");
    return value;
  } finally { fs.closeSync(fd); }
}

function disconnect(report = true) {
  if (socket) { try { socket.close(); } catch {} }
  socket = undefined;
  connected = false;
  pendingHistory = undefined;
  token = "";
  modelLabel = undefined;
  if (report) emit({ type: "status", state: "disconnected" });
}

function messages(raw) {
  if (!Array.isArray(raw) || raw.length > 100) return [];
  return raw.flatMap((item) => {
    if (!item || typeof item !== "object" || typeof item.id !== "string" || !["user", "assistant"].includes(item.role)) return [];
    if (typeof item.text !== "string") return [];
    return item.text.length <= 16384 ? [{ id: clean(item.id), role: item.role, text: clean(item.text) }] : [];
  });
}

async function connect(input) {
  if (!input || input.consent !== true || !endpoint(input.url) || typeof input.tokenFile !== "string") return refused();
  let capability;
  try { capability = readToken(input.tokenFile); } catch { return refused(); }
  if (typeof WebSocket !== "function") return unavailable();
  disconnect(false);
  token = capability;
  await new Promise((done) => {
    let settled = false;
    const finish = (ok) => { if (!settled) { settled = true; clearTimeout(timer); done(ok); } };
    const timer = setTimeout(() => finish(false), CONNECT_TIMEOUT);
    let ws;
    try { ws = socket = new WebSocket(input.url); } catch { finish(false); return; }
    ws.addEventListener("open", () => ws.send(JSON.stringify({ type: "hello", token, protocol: 1 })));
    ws.addEventListener("message", (event) => {
      if (typeof event.data !== "string" || event.data.length > MAX_FRAME) return;
      let eventValue;
      try { eventValue = JSON.parse(event.data); } catch { return; }
      if (eventValue?.type === "ready") { modelLabel = typeof eventValue.model === "string" ? clean(eventValue.model) : undefined; connected = true; finish(true); }
      else if (eventValue?.type === "history" && pendingHistory) {
        const resolve = pendingHistory; pendingHistory = undefined;
        resolve({ ok: true, history: messages(eventValue.messages) });
      } else if (eventValue?.type === "error" && pendingHistory) {
        const resolve = pendingHistory; pendingHistory = undefined;
        resolve({ ok: false });
      }
    });
    ws.addEventListener("close", () => {
      if (socket === ws && connected) {
        socket = undefined;
        connected = false;
        const resolve = pendingHistory; pendingHistory = undefined;
        resolve?.({ ok: false });
        token = "";
        modelLabel = undefined;
        emit({ type: "status", state: "disconnected" });
      }
      finish(false);
    });
    ws.addEventListener("error", () => finish(false));
  }).then((ok) => {
    if (ok) emit({ type: "status", state: "connected", ...(modelLabel ? { modelLabel } : {}) });
    else { disconnect(false); unavailable(); }
  });
}

async function history(input) {
  const timeout = historyTimeout(input.timeoutMs);
  if (!timeout) return refused();
  if (!connected || !socket || socket.readyState !== WebSocket.OPEN) return emit({ type: "error", message: "Not connected." });
  const outcome = await new Promise((done) => {
    const finish = (value) => { clearTimeout(timer); done(value); };
    const timer = setTimeout(() => { pendingHistory = undefined; finish({ ok: false }); }, timeout);
    pendingHistory = (value) => finish(value);
    try { socket.send(JSON.stringify({ type: "get_history" })); } catch { pendingHistory = undefined; finish({ ok: false }); }
  });
  if (outcome.ok) emit({ type: "history", history: outcome.history });
  else { disconnect(false); unavailable(); }
}

async function command(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return refused();
  if (value.command === "connect") return connect(value);
  if (value.command === "disconnect") return disconnect();
  if (value.command === "history") return history(value);
  refused();
}

if (process.argv[2] === "--help") {
  process.stdout.write("Usage: backend_bridge.mjs < JSONL\nCommands: connect (consent, url, tokenFile), history, disconnect.\n");
} else if (process.argv.length !== 2) {
  process.exitCode = 2;
} else {
  let buffered = "";
  let queue = Promise.resolve();
  const enqueue = (line) => {
    queue = queue.then(async () => {
      if (line.length > MAX_LINE) return refused();
      try { await command(JSON.parse(line)); } catch { refused(); }
    });
  };
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    buffered += chunk;
    while (buffered.includes("\n")) {
      const at = buffered.indexOf("\n"); const line = buffered.slice(0, at); buffered = buffered.slice(at + 1);
      enqueue(line);
    }
    if (buffered.length > MAX_LINE) { buffered = ""; enqueue("{"); }
  });
  process.stdin.on("end", () => { void queue.finally(() => disconnect(false)); });
  process.on("SIGINT", () => { disconnect(false); process.exit(); });
}
