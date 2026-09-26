/** Exercise real JIZURA UI save/download and persistence paths in WebView2. */

import { spawn } from "node:child_process";
import { once } from "node:events";
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, stat } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { inflateSync } from "node:zlib";


const root = path.resolve(import.meta.dirname, "..");
const executable = path.resolve(process.argv[2] ?? path.join(root, "dist", "JIZURA-Desktop.exe"));
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url);
    socket.addEventListener("open", () => resolve(socket), { once: true });
    socket.addEventListener("error", () => reject(new Error("DevTools WebSocket connection failed")), { once: true });
  });
}

function command(socket, method, params = {}) {
  const id = command.nextId++;
  return new Promise((resolve, reject) => {
    const listener = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      socket.removeEventListener("message", listener);
      if (message.error) reject(new Error(`${method}: ${message.error.message}`));
      else resolve(message.result);
    };
    socket.addEventListener("message", listener);
    socket.send(JSON.stringify({ id, method, params }));
  });
}
command.nextId = 1;

async function evaluate(socket, expression) {
  const result = await command(socket, "Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description ?? "evaluation failed");
  }
  return result.result.value;
}

async function waitFor(socket, expression, label, timeout = 60000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      if (await evaluate(socket, expression)) return;
    } catch (_) {
      // Navigation can replace the execution context.
    }
    await sleep(200);
  }
  throw new Error(`timed out waiting for ${label}`);
}

async function waitForTarget(port) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const list = await response.json();
      const target = list.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
      if (target) return target;
    } catch (_) {
      // WebView2 has not opened its diagnostic endpoint.
    }
    await sleep(200);
  }
  throw new Error("WebView2 DevTools endpoint did not become ready");
}

async function launch(exe, localAppData, downloadDirectory, { offline = false } = {}) {
  const port = await freePort();
  const child = spawn(exe, [], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      LOCALAPPDATA: localAppData,
      JIZURA_WEBVIEW2_DEBUG_PORT: String(port),
      JIZURA_WEBVIEW2_BLOCK_NETWORK: offline ? "1" : "",
    },
  });
  const target = await waitForTarget(port);
  const socket = await connect(target.webSocketDebuggerUrl);
  await command(socket, "Runtime.enable");
  await command(socket, "Browser.setDownloadBehavior", {
    behavior: "allow",
    downloadPath: downloadDirectory,
    eventsEnabled: true,
  });
  await waitFor(
    socket,
    "document.readyState === 'complete' && typeof J === 'object' && document.getElementById('btnSave') !== null",
    "JIZURA UI",
  );
  if (offline) {
    await command(socket, "Network.enable");
    await command(socket, "Network.emulateNetworkConditions", {
      offline: true,
      latency: 0,
      downloadThroughput: 0,
      uploadThroughput: 0,
    });
  }
  return { child, socket };
}

async function close(session) {
  if (!session) return;
  session.socket.close();
  if (session.child.exitCode === null && !session.child.killed) {
    session.child.kill();
    await Promise.race([once(session.child, "exit"), sleep(3000)]);
  }
  await sleep(500);
}

async function filesWithExtension(directory, extension) {
  const names = await readdir(directory);
  return names.filter((name) => name.toLowerCase().endsWith(extension) && !name.endsWith(".crdownload"));
}

async function waitForNewFile(directory, extension, oldNames, timeout = 180000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const current = await filesWithExtension(directory, extension);
    const found = current.find((name) => !oldNames.has(name));
    if (found) {
      const fullPath = path.join(directory, found);
      const first = (await stat(fullPath)).size;
      await sleep(400);
      if ((await stat(fullPath)).size === first && first > 0) return fullPath;
    }
    await sleep(250);
  }
  throw new Error(`download did not finish: ${extension}`);
}

async function clickAndDownload(session, directory, buttonId, extension) {
  const oldNames = new Set(await filesWithExtension(directory, extension));
  await evaluate(session.socket, `document.getElementById(${JSON.stringify(buttonId)}).click(); true`);
  const file = await waitForNewFile(directory, extension, oldNames);
  await waitFor(
    session.socket,
    `!document.getElementById(${JSON.stringify(buttonId)}).disabled`,
    `${buttonId} completion`,
    180000,
  );
  const error = await evaluate(
    session.socket,
    `[...document.querySelectorAll('.exp-text')].map(x => x.textContent).find(x => x.startsWith('エラー:')) || ''`,
  );
  if (error) throw new Error(error);
  return file;
}

function firstStoredZipEntry(zip) {
  if (zip.readUInt32LE(0) !== 0x04034b50) throw new Error("ZIP local header is missing");
  const method = zip.readUInt16LE(8);
  const compressedSize = zip.readUInt32LE(18);
  const nameLength = zip.readUInt16LE(26);
  const extraLength = zip.readUInt16LE(28);
  const start = 30 + nameLength + extraLength;
  const compressed = zip.subarray(start, start + compressedSize);
  const data = method === 0 ? compressed : method === 8 ? inflateSync(compressed) : null;
  if (!data) throw new Error(`unsupported ZIP compression method: ${method}`);
  return { name: zip.subarray(30, 30 + nameLength).toString("utf8"), data };
}

function inspectPng(buffer) {
  if (buffer.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") throw new Error("PNG signature is missing");
  let offset = 8;
  let width = 0, height = 0, bitDepth = 0, colorType = 0;
  const idat = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString("ascii");
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === "IHDR") {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      bitDepth = data[8]; colorType = data[9];
    } else if (type === "IDAT") idat.push(data);
    else if (type === "IEND") break;
    offset += 12 + length;
  }
  if (bitDepth !== 8 || colorType !== 6) throw new Error(`expected 8-bit RGBA PNG, got depth=${bitDepth} type=${colorType}`);
  const raw = inflateSync(Buffer.concat(idat));
  const bytesPerPixel = 4, stride = width * bytesPerPixel;
  let input = 0;
  let previous = Buffer.alloc(stride);
  let hasTransparentPixel = false;
  const paeth = (a, b, c) => {
    const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
    return pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
  };
  for (let y = 0; y < height; y++) {
    const filter = raw[input++];
    const row = Buffer.alloc(stride);
    for (let x = 0; x < stride; x++) {
      const encoded = raw[input++];
      const left = x >= bytesPerPixel ? row[x - bytesPerPixel] : 0;
      const up = previous[x];
      const upperLeft = x >= bytesPerPixel ? previous[x - bytesPerPixel] : 0;
      const predictor = filter === 0 ? 0 : filter === 1 ? left : filter === 2 ? up
        : filter === 3 ? Math.floor((left + up) / 2) : filter === 4 ? paeth(left, up, upperLeft) : NaN;
      if (!Number.isFinite(predictor)) throw new Error(`unsupported PNG filter: ${filter}`);
      row[x] = (encoded + predictor) & 0xff;
    }
    for (let x = 3; x < stride; x += 4) if (row[x] < 255) hasTransparentPixel = true;
    previous = row;
  }
  return { width, height, colorType: "RGBA", hasTransparentPixel };
}

await mkdir(path.join(root, "build"), { recursive: true });
const work = await mkdtemp(path.join(root, "build", "ui-file-probe-"));
const profile = path.join(work, "profile");
const downloads = path.join(work, "downloads");
const moved = path.join(work, "moved", "JIZURA-Desktop.exe");
const offlineProfile = path.join(work, "offline-profile");
const offlineDownloads = path.join(work, "offline-downloads");
await mkdir(downloads, { recursive: true });
await mkdir(path.dirname(moved), { recursive: true });
await mkdir(offlineDownloads, { recursive: true });

let session;
let summary = { work };
try {
  session = await launch(executable, profile, downloads);
  await evaluate(session.socket, `
    (async () => {
      for (const id of ['termsDlg', 'resetDlg']) {
        const dialog = document.getElementById(id);
        if (dialog && dialog.open && dialog.close) dialog.close();
      }
      const fire = (id, value, type) => {
        const element = document.getElementById(id);
        element.value = value;
        element.dispatchEvent(new Event(type, { bubbles: true }));
      };
      fire('songTitle', 'JIZURA probe', 'input');
      fire('songArtist', 'Codex', 'input');
      fire('lyrics', '[00:00.00]保存と復元の確認', 'input');
      fire('outRes', '720', 'change');
      fire('outFps', '24', 'change');
      const rate = 48000, frames = rate;
      const wav = new ArrayBuffer(44 + frames * 2);
      const view = new DataView(wav);
      const text = (offset, value) => [...value].forEach((ch, index) => view.setUint8(offset + index, ch.charCodeAt(0)));
      text(0, 'RIFF'); view.setUint32(4, 36 + frames * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
      view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
      view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      text(36, 'data'); view.setUint32(40, frames * 2, true);
      for (let i = 0; i < frames; i++) view.setInt16(44 + i * 2, Math.sin(i * 2 * Math.PI * 440 / rate) * 5000, true);
      const audio = new File([wav], 'probe.wav', { type: 'audio/wav' });
      const audioTransfer = new DataTransfer(); audioTransfer.items.add(audio);
      document.getElementById('audioFile').files = audioTransfer.files;
      document.getElementById('audioFile').dispatchEvent(new Event('change', { bubbles: true }));

      const fontResponse = await fetch('/assets/fonts/files/dotgothic16/DotGothic16-Regular.ttf');
      const font = new File([await fontResponse.blob()], 'ProbeFont.ttf', { type: 'font/ttf' });
      const fontTransfer = new DataTransfer(); fontTransfer.items.add(font);
      document.getElementById('fontFile').files = fontTransfer.files;
      document.getElementById('fontFile').dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()
  `);
  await waitFor(session.socket, "document.getElementById('audioName').textContent.includes('probe.wav')", "audio analysis");
  await waitFor(
    session.socket,
    "JSON.parse(localStorage.getItem('jizura.project.v1') || '{}').userFonts?.length > 0",
    "uploaded font persistence",
  );

  const jsonPath = await clickAndDownload(session, downloads, "btnSave", ".json");
  const projectText = await readFile(jsonPath, "utf8");
  const project = JSON.parse(projectText);
  if (project.title !== "JIZURA probe" || !project.userFonts?.length) throw new Error("saved project JSON is incomplete");

  await evaluate(session.socket, `
    (() => {
      const title = document.getElementById('songTitle');
      title.value = 'changed before reload'; title.dispatchEvent(new Event('input', { bubbles: true }));
      const file = new File([${JSON.stringify(projectText)}], 'reloaded.jizura.json', { type: 'application/json' });
      const transfer = new DataTransfer(); transfer.items.add(file);
      const input = document.getElementById('fileProject'); input.files = transfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()
  `);
  await waitFor(session.socket, "document.getElementById('songTitle').value === 'JIZURA probe'", "project JSON reload");

  const mp4Path = await clickAndDownload(session, downloads, "btnMP4", ".mp4");
  const mp4 = await readFile(mp4Path);
  if (mp4.subarray(4, 8).toString("ascii") !== "ftyp") throw new Error("saved MP4 lacks an ftyp signature");
  const hasAudioTrack = mp4.includes(Buffer.from("soun")) && mp4.includes(Buffer.from("mp4a"));
  if (!hasAudioTrack) throw new Error("saved MP4 lacks its AAC audio track");
  const playback = await evaluate(session.socket, `
    (async () => {
      const bytes = Uint8Array.from(atob(${JSON.stringify(mp4.toString("base64"))}), c => c.charCodeAt(0));
      const video = document.createElement('video');
      video.muted = true; video.src = URL.createObjectURL(new Blob([bytes], { type: 'video/mp4' }));
      await new Promise((resolve, reject) => { video.onloadedmetadata = resolve; video.onerror = () => reject(video.error); });
      await video.play(); await new Promise(resolve => setTimeout(resolve, 200)); video.pause();
      const result = { duration: video.duration, videoWidth: video.videoWidth, videoHeight: video.videoHeight };
      URL.revokeObjectURL(video.src); return result;
    })()
  `);
  if (!(playback.duration > 0) || playback.videoWidth < 1) throw new Error("saved MP4 did not play in WebView2");

  const beforeCancel = new Set(await filesWithExtension(downloads, ".zip"));
  await evaluate(session.socket, `
    (() => {
      document.getElementById('btnPNG').click();
      setTimeout(() => document.querySelector('.exp-cancel').click(), 25);
      return true;
    })()
  `);
  await waitFor(session.socket, "!document.getElementById('btnPNG').disabled", "export cancellation");
  await sleep(500);
  const afterCancel = await filesWithExtension(downloads, ".zip");
  if (afterCancel.some((name) => !beforeCancel.has(name))) throw new Error("cancelled export unexpectedly saved a ZIP");

  const pngPath = await clickAndDownload(session, downloads, "btnPNG", ".zip");
  const alphaPath = await clickAndDownload(session, downloads, "btnPNGA", ".zip");
  const pngEntry = firstStoredZipEntry(await readFile(pngPath));
  const alphaEntry = firstStoredZipEntry(await readFile(alphaPath));
  const pngInspection = inspectPng(pngEntry.data);
  const alphaInspection = inspectPng(alphaEntry.data);
  if (!alphaInspection.hasTransparentPixel) throw new Error("transparent PNG export has no transparent pixels");
  const state = await evaluate(session.socket, `({
    title: document.getElementById('songTitle').value,
    audio: document.getElementById('audioName').textContent,
    storedTitle: JSON.parse(localStorage.getItem('jizura.project.v1')).title,
    userFonts: JSON.parse(localStorage.getItem('jizura.project.v1')).userFonts.length,
  })`);
  await close(session); session = null;

  session = await launch(executable, profile, downloads);
  await waitFor(session.socket, "document.getElementById('songTitle').value === 'JIZURA probe'", "restart project restore");
  await waitFor(session.socket, "document.getElementById('audioName').textContent.includes('probe.wav')", "restart audio restore");
  await waitFor(
    session.socket,
    "(() => { const p = JSON.parse(localStorage.getItem('jizura.project.v1')); return p.fonts?.display && J.missingUserFonts([p.fonts.display]).length === 0; })()",
    "restart uploaded font restore",
  );
  const restarted = await evaluate(session.socket, `({
    title: document.getElementById('songTitle').value,
    audio: document.getElementById('audioName').textContent,
    userFonts: JSON.parse(localStorage.getItem('jizura.project.v1')).userFonts.length,
    resolution: document.getElementById('outRes').value,
    uploadedFontAvailable: J.missingUserFonts([JSON.parse(localStorage.getItem('jizura.project.v1')).fonts.display]).length === 0,
  })`);
  await close(session); session = null;

  await copyFile(executable, moved);
  session = await launch(moved, profile, downloads);
  await waitFor(session.socket, "document.getElementById('songTitle').value === 'JIZURA probe'", "moved executable restore");
  const movedRestore = await evaluate(session.socket, "document.getElementById('songTitle').value");
  await close(session); session = null;

  session = await launch(moved, offlineProfile, offlineDownloads, { offline: true });
  await evaluate(session.socket, `
    (() => {
      const title = document.getElementById('songTitle');
      title.value = 'offline first launch'; title.dispatchEvent(new Event('input', { bubbles: true }));
      const lyrics = document.getElementById('lyrics');
      lyrics.value = '[00:00.00]offline'; lyrics.dispatchEvent(new Event('input', { bubbles: true }));
      const resolution = document.getElementById('outRes');
      resolution.value = '720'; resolution.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()
  `);
  const offlineJson = await clickAndDownload(session, offlineDownloads, "btnSave", ".json");
  const offlinePng = await clickAndDownload(session, offlineDownloads, "btnPNG", ".zip");
  const offlineState = await evaluate(session.socket, `({
    title: document.getElementById('songTitle').value,
    externalResources: performance.getEntriesByType('resource').map(x => x.name).filter(x => !x.startsWith('http://wails.localhost')),
  })`);
  await close(session); session = null;

  summary = {
    jsonPath,
    mp4Path,
    pngPath,
    alphaPath,
    offlineJson,
    offlinePng,
    sizes: {
      json: (await stat(jsonPath)).size,
      mp4: (await stat(mp4Path)).size,
      pngZip: (await stat(pngPath)).size,
      alphaZip: (await stat(alphaPath)).size,
    },
    playback,
    hasAudioTrack,
    exportCancellation: true,
    pngInspection: { entry: pngEntry.name, ...pngInspection },
    alphaInspection: { entry: alphaEntry.name, ...alphaInspection },
    state,
    restarted,
    movedRestore,
    offlineState,
    directFilePickerAutomated: false,
  };
  console.log(JSON.stringify(summary, null, 2));
} finally {
  await close(session);
  // Only the probe-owned temporary LOCALAPPDATA and copied executable are removed.
  await rm(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
}
