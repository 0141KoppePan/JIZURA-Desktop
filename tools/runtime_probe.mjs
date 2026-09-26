/** Probe the packaged WebView2 page through a temporary local DevTools port. */

import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import process from "node:process";


const root = path.resolve(import.meta.dirname, "..");
const executable = path.resolve(process.argv[2] ?? path.join(root, "dist", "JIZURA-Desktop.exe"));
const manifest = JSON.parse(await readFile(path.join(root, "assets", "fonts", "manifest.json"), "utf8"));

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

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function targets(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/list`);
  if (!response.ok) throw new Error(`DevTools target list returned ${response.status}`);
  return response.json();
}

async function waitForTarget(port) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const list = await targets(port);
      const target = list.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
      if (target) return target;
    } catch (_) {
      // WebView2 has not opened the debugging endpoint yet.
    }
    await sleep(200);
  }
  throw new Error("WebView2 DevTools endpoint did not become ready")
}

async function waitForPageReady(socket) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const evaluated = await command(socket, "Runtime.evaluate", {
        expression: "document.readyState === 'complete' && typeof J === 'object' && typeof Mp4Muxer === 'object'",
        returnByValue: true,
      });
      if (evaluated.result?.value === true) return;
    } catch (_) {
      // Navigation can temporarily replace the execution context.
    }
    await sleep(200);
  }
  throw new Error("JIZURA page did not finish initialising");
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

const probeFaces = manifest.families.flatMap((family) =>
  family.faces.flatMap((face) => {
    const weights = String(face.weight).split(" ");
    const selected = weights.length === 2 ? weights : [weights[0]];
    return selected.map((weight) => ({ family: family.name, weight }));
  }),
);

const port = await freePort();
const buildDirectory = path.join(root, "build");
await mkdir(buildDirectory, { recursive: true });
const probeData = await mkdtemp(path.join(buildDirectory, "runtime-probe-"));
const child = spawn(executable, [], {
  windowsHide: true,
  stdio: "ignore",
  env: {
    ...process.env,
    LOCALAPPDATA: probeData,
    JIZURA_WEBVIEW2_DEBUG_PORT: String(port),
  },
});

let socket;
try {
  const target = await waitForTarget(port);
  socket = await connect(target.webSocketDebuggerUrl);
  await command(socket, "Runtime.enable");
  await waitForPageReady(socket);

  const expression = `
    (async () => {
      const faces = ${JSON.stringify(probeFaces)};
      const loaded = [];
      for (const face of faces) {
        const descriptor = face.weight + ' 24px "' + face.family.replaceAll('"', '\\\"') + '"';
        try {
          const result = await document.fonts.load(descriptor, 'A');
          loaded.push({ ...face, count: result.length });
        } catch (error) {
          loaded.push({ ...face, count: 0, error: String(error) });
        }
      }
      await document.fonts.ready;
      const codecProbe = await (async () => {
        const width = 320, height = 180, frameRate = 30;
        const video = await J.pickVideoCodec(width, height, frameRate, 500000);
        const audio = await J.pickAudioCodec(48000, 2);
        if (!video || !audio) return { ok: false, error: 'required codec was not selected' };

        const target = new Mp4Muxer.ArrayBufferTarget();
        const muxer = new Mp4Muxer.Muxer({
          target,
          video: { codec: video.mux, width, height, frameRate },
          audio: { codec: audio.mux, numberOfChannels: 2, sampleRate: audio.sr },
          fastStart: false,
          firstTimestampBehavior: 'offset',
        });
        let encoderError = null;
        let videoChunks = 0;
        let audioChunks = 0;
        const videoEncoder = new VideoEncoder({
          output: (chunk, metadata) => { videoChunks++; muxer.addVideoChunk(chunk, metadata); },
          error: (error) => { encoderError = error; },
        });
        videoEncoder.configure(video.cfg);
        const canvas = document.createElement('canvas');
        canvas.width = width; canvas.height = height;
        const context = canvas.getContext('2d', { alpha: false });
        for (let index = 0; index < 6; index++) {
          context.fillStyle = index % 2 ? '#ffffff' : '#101018';
          context.fillRect(0, 0, width, height);
          const frame = new VideoFrame(canvas, { timestamp: Math.round(index * 1e6 / frameRate), duration: Math.round(1e6 / frameRate) });
          videoEncoder.encode(frame, { keyFrame: index === 0 });
          frame.close();
        }
        await videoEncoder.flush();
        videoEncoder.close();

        const audioEncoder = new AudioEncoder({
          output: (chunk, metadata) => { audioChunks++; muxer.addAudioChunk(chunk, metadata); },
          error: (error) => { encoderError = error; },
        });
        audioEncoder.configure({ codec: audio.codec, sampleRate: audio.sr, numberOfChannels: 2, bitrate: 128000 });
        const audioFrames = 4800;
        const audioData = new AudioData({
          format: 'f32-planar', sampleRate: audio.sr, numberOfFrames: audioFrames, numberOfChannels: 2,
          timestamp: 0, data: new Float32Array(audioFrames * 2),
        });
        audioEncoder.encode(audioData);
        audioData.close();
        await audioEncoder.flush();
        audioEncoder.close();
        if (encoderError) throw encoderError;

        muxer.finalize();
        const bytes = new Uint8Array(target.buffer);
        const signature = String.fromCharCode(...bytes.slice(4, 8));
        return {
          ok: signature === 'ftyp' && videoChunks > 0 && audioChunks > 0,
          bytes: bytes.length,
          signature,
          videoCodec: video.codec,
          audioCodec: audio.codec,
          videoChunks,
          audioChunks,
        };
      })();
      return {
        url: location.href,
        origin: location.origin,
        title: document.title,
        fontStatus: document.fonts.status,
        loaded,
        features: {
          videoEncoder: typeof VideoEncoder === 'function',
          audioEncoder: typeof AudioEncoder === 'function',
          showSaveFilePicker: typeof showSaveFilePicker === 'function',
        },
        codecProbe,
        resources: performance.getEntriesByType('resource').map((entry) => entry.name),
      };
    })()
  `;
  const evaluated = await command(socket, "Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (evaluated.exceptionDetails) {
    throw new Error(evaluated.exceptionDetails.exception?.description ?? "runtime probe evaluation failed");
  }
  const result = evaluated.result.value;
  const missing = result.loaded.filter((face) => face.count < 1);
  const externalFonts = result.resources.filter((url) => /fonts\.(googleapis|gstatic)\.com/i.test(url));
  const summary = {
    url: result.url,
    origin: result.origin,
    title: result.title,
    fontStatus: result.fontStatus,
    fontFacesChecked: result.loaded.length,
    missingFontFaces: missing,
    features: result.features,
    codecProbe: result.codecProbe,
    externalFontRequests: externalFonts,
  };
  console.log(JSON.stringify(summary, null, 2));

  if (missing.length || externalFonts.length || result.fontStatus !== "loaded") process.exitCode = 1;
  if (!result.features.videoEncoder || !result.features.audioEncoder) process.exitCode = 1;
  if (!result.codecProbe.ok) process.exitCode = 1;
} finally {
  if (socket) socket.close();
  if (child.exitCode === null && !child.killed) {
    child.kill();
    await Promise.race([once(child, "exit"), sleep(3000)]);
  }
  await sleep(500);
  await rm(probeData, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
}
