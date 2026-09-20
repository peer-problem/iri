import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { IllustrationKind } from "./diagram-content";

const C = { blue: "#397fce", pale: "#dceafa", purple: "#9170d7", coral: "#ed876c", green: "#48a990", ink: "#334b63", track: "#cbd5df" };
type Tick = (time: number, mode: number) => void;
const V = (p: number[]) => new THREE.Vector3(p[0], p[1], p[2] ?? 0);
function mat(color: string, opacity = 1) {
  return new THREE.MeshPhysicalMaterial({ color, roughness: .3, metalness: .12, clearcoat: .45, transparent: opacity < 1, opacity });
}
function add(parent: THREE.Object3D, geo: THREE.BufferGeometry, material: THREE.Material, position: number[] = [0, 0, 0]) {
  const m = new THREE.Mesh(geo, material); m.position.copy(V(position)); parent.add(m); return m;
}
function group(parent: THREE.Object3D, x: number, y = 0, z = 0) {
  const g = new THREE.Group(); g.position.set(x, y, z); parent.add(g); return g;
}
function box(parent: THREE.Object3D, w: number, h: number, d: number, material: THREE.Material, pos = [0, 0, 0], radius = .045) {
  return add(parent, new RoundedBoxGeometry(w, h, d, 2, radius), material, pos);
}
function text(parent: THREE.Object3D, value: string, x: number, y: number, width: number, color = C.ink, z = .23) {
  const canvas = document.createElement("canvas"); canvas.width = 768; canvas.height = 160;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = color; ctx.font = "500 76px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(value, 384, 80);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
  return add(parent, new THREE.PlaneGeometry(width, width * 160 / 768), material, [x, y, z]);
}
function route(parent: THREE.Object3D, points: number[][], color = C.track, radius = .015) {
  // Connectors share one front-facing plane, so bevels cannot clip their tips.
  const vertices = points.map(p => new THREE.Vector3(p[0], p[1], 1)).filter((p, i, list) => i === 0 || p.distanceTo(list[i - 1]) > .001);
  const end = vertices[vertices.length - 1].clone();
  const tangent = end.clone().sub(vertices[vertices.length - 2]).normalize();
  const headLength = Math.min(.12, end.distanceTo(vertices[vertices.length - 2]) * .45);
  vertices[vertices.length - 1].addScaledVector(tangent, -headLength);
  const curve = new THREE.CurvePath<THREE.Vector3>();
  let cursor = vertices[0];
  // Straight segments with bounded corner fillets: no spline overshoot,
  // terminal hooks or changes in curvature along a straight connector.
  for (let i = 1; i < vertices.length - 1; i++) {
    const before = vertices[i - 1], corner = vertices[i], after = vertices[i + 1];
    const incoming = corner.clone().sub(before).normalize(), outgoing = after.clone().sub(corner).normalize();
    if (incoming.dot(outgoing) > .999) continue;
    const trim = Math.min(.16, corner.distanceTo(before) * .3, corner.distanceTo(after) * .3);
    const entry = corner.clone().addScaledVector(incoming, -trim), exit = corner.clone().addScaledVector(outgoing, trim);
    if (cursor.distanceTo(entry) > .001) curve.add(new THREE.LineCurve3(cursor, entry));
    curve.add(new THREE.QuadraticBezierCurve3(entry, corner, exit)); cursor = exit;
  }
  curve.add(new THREE.LineCurve3(cursor, vertices[vertices.length - 1]));
  const lineMaterial = new THREE.MeshBasicMaterial({ color, toneMapped: false });
  add(parent, new THREE.TubeGeometry(curve, Math.max(32, Math.ceil(curve.getLength() * 24)), radius, 8, false), lineMaterial);
  const head = new THREE.Shape();
  head.moveTo(0, 0); head.lineTo(-radius * 3, -headLength); head.lineTo(radius * 3, -headLength); head.closePath();
  const arrow = add(parent, new THREE.ShapeGeometry(head), lineMaterial);
  arrow.position.copy(end);
  arrow.rotation.z = Math.atan2(tangent.y, tangent.x) - Math.PI / 2;
  return curve;
}
// Project an actual frame edge, including its small 3D rotation, into the
// diagram plane. Avoid hand-tuned endpoints that leave detached connectors.
function edge(object: THREE.Object3D, x: number, y: number, z = 0): number[] {
  object.updateWorldMatrix(true, false);
  const p = object.localToWorld(new THREE.Vector3(x, y, z));
  return [p.x, p.y];
}
function stream(parent: THREE.Object3D, curve: THREE.Curve<THREE.Vector3>, color: string, count = 5) {
  const material = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: .3, roughness: .25 });
  const geometry = new THREE.SphereGeometry(.048, 12, 8);
  const dots = Array.from({ length: count }, () => add(parent, geometry, material));
  return (time: number, visible = true, reverse = false) => dots.forEach((dot, i) => {
    dot.visible = visible;
    const p = (time * .17 + i / count) % 1;
    dot.position.copy(curve.getPoint(reverse ? 1 - p : p));
  });
}
function matrix(parent: THREE.Object3D, x: number, y: number, cols: number, rows: number, color: string, size = .19) {
  const g = group(parent, x, y);
  const w = cols * size, h = rows * size;
  box(g, w + .16, h + .16, .12, mat(color), [0, 0, -.09]);
  box(g, w + .11, h + .11, .025, mat("#f3f7fc"), [0, 0, -.015]);
  const material = mat(color);
  const cells = new THREE.InstancedMesh(new RoundedBoxGeometry(size * .76, size * .76, .13, 2, .015), material, cols * rows);
  const temp = new THREE.Object3D();
  const base = new THREE.Color(color);
  for (let i = 0; i < cols * rows; i++) {
    temp.position.set((i % cols - (cols - 1) / 2) * size, (Math.floor(i / cols) - (rows - 1) / 2) * size, .055);
    temp.updateMatrix(); cells.setMatrixAt(i, temp.matrix);
    cells.setColorAt(i, base.clone().lerp(new THREE.Color("#ffffff"), .15 + ((i * 7) % 13) / 20));
  }
  g.add(cells);
  g.rotation.set(-.12, -.22, 0);
  return { group: g, cells, base };
}
function port(parent: THREE.Object3D, x: number, y: number, color: string, label?: string) {
  add(parent, new THREE.TorusGeometry(.105, .025, 8, 24), mat(color), [x, y, .2]);
  if (label) text(parent, label, x, y - .31, .6);
}
function panel(parent: THREE.Object3D, x: number, y: number, w: number, h: number, color: string, title: string) {
  const g = group(parent, x, y);
  box(g, w, h, .15, mat(color), [0, 0, -.1]);
  box(g, w - .09, h - .09, .035, mat("#fbfdff"), [0, 0, 0]);
  text(g, title, 0, h / 2 - .26, w * .86, color, .07);
  for (const side of [-1, 1]) {
    for (const yy of [-1, 1]) add(g, new THREE.CylinderGeometry(.025, .025, .012, 10).rotateX(Math.PI / 2), mat("#9aa9b6"), [side * (w / 2 - .12), yy * (h / 2 - .12), .035]);
  }
  g.rotation.y = -.13;
  return g;
}
function waveform(parent: THREE.Object3D, x: number, y: number, color: string, width: number, count = 17) {
  const bars = Array.from({ length: count }, (_, i) => box(parent, width / count * .5, .3 + Math.sin(i * 2.5) ** 2 * .4, .085, mat(color), [x + (i - (count - 1) / 2) * width / count, y, .13]));
  return (t: number, active = true) => bars.forEach((bar, i) => { bar.scale.y = active ? .4 + Math.sin(t * 3 - i * .5) ** 2 * .8 : .15; });
}

function conversation(scene: THREE.Scene): Tick {
  const root = group(scene, 0);
  const input = panel(root, -4.5, .1, 1.9, 1.6, C.blue, "INPUT");
  const wave = waveform(input, 0, -.05, C.blue, 1.4);
  const keyboard = group(input, 0, -.1, .16);
  for (let i = 0; i < 18; i++) box(keyboard, .16, .14, .06, mat(C.blue), [(i % 6 - 2.5) * .22, (Math.floor(i / 6) - 1) * .22, 0]);
  const transcript = panel(root, -1.85, .1, 2.1, 1.6, C.blue, "TRANSCRIPT");
  text(transcript, "왜 비가 와?", 0, -.12, 1.7, C.ink, .08);
  text(transcript, "확인 후 전송", 0, -.48, 1.25, C.blue, .08);
  const model = group(root, 1.25, .05);
  const matrices = [C.green, C.purple, C.green].map((color, i) => {
    const m = matrix(model, 0, (i - 1) * .44, 8, 3, color, .18);
    m.group.position.z = i * .18;
    return m;
  });
  text(model, "IRI v5", 0, 1, 1.1, C.purple, .1);
  [-1, 1].forEach(side => route(model, [[side * .92, -.7, .1], [side * .92, .7, .1]], C.track, .012));
  const speaker = panel(root, 4.5, .1, 1.85, 1.6, C.coral, "VOICE");
  const outputWave = waveform(speaker, 0, -.05, C.coral, 1.35, 13);
  const paths = [
    route(root, [edge(input, .95, 0), edge(transcript, -1.05, 0)], C.blue),
    route(root, [edge(transcript, 1.05, 0), edge(matrices[1].group, -.8, 0)], C.purple),
    route(root, [edge(matrices[1].group, .8, 0), edge(speaker, -.925, 0)], C.coral),
    route(root, [edge(input, -.95, 0), [-5.75, .1], [-5.75, -1.85], [-.05, -1.85], [-.05, -.6], edge(matrices[0].group, -.8, -.21)], C.blue),
  ];
  const streams = paths.map((p, i) => stream(root, p, i === 2 ? C.coral : C.blue, i === 3 ? 4 : 2));
  return (t, mode) => {
    wave(t, mode === 0); keyboard.visible = mode === 1; outputWave(t - 1);
    streams.forEach((s, i) => s(t, i === 0 ? mode === 0 : i === 3 ? mode === 1 : true));
    matrices.forEach((m, i) => { m.group.position.z = i * .18 + Math.sin(t * 1.5 - i) * .025; });
  };
}

function adapter(scene: THREE.Scene): Tick {
  const root = group(scene, 0);
  const frozen = matrix(root, -1.1, .8, 10, 7, C.blue, .22);
  // The dimensions are illustrative. This represents one adapted linear layer.
  const a = matrix(root, -2.1, -.8, 8, 2, C.purple, .21);
  const b = matrix(root, .5, -.8, 2, 7, C.coral, .17);
  const input = matrix(root, -4.8, 0, 1, 6, C.blue, .17);
  const output = matrix(root, 4.8, 0, 1, 6, C.green, .17);
  const junction = group(root, 3, 0);
  add(junction, new THREE.TorusGeometry(.24, .034, 12, 40), mat(C.green));
  box(junction, .22, .045, .045, mat(C.green)); box(junction, .045, .22, .045, mat(C.green));
  // Freeze symbol on the base matrix, not on the adapter.
  const lock = group(root, -.1, 1.47, .4);
  box(lock, .2, .16, .07, mat(C.ink));
  const arc = new THREE.EllipseCurve(0, .09, .066, .08, 0, Math.PI, false, 0);
  const lockCurve = new THREE.CatmullRomCurve3(arc.getPoints(14).map(p => new THREE.Vector3(p.x, p.y, 0)));
  add(lock, new THREE.TubeGeometry(lockCurve, 20, .014, 6, false), mat(C.ink));
  const paths = [
    route(root, [edge(input.group, .165, 0), [-3.9, 0], [-3.9, .8], edge(frozen.group, -1.18, 0)], C.blue),
    route(root, [edge(frozen.group, 1.18, 0), [1.9, .8], [2.76, 0]], C.blue),
    route(root, [[-3.9, 0], [-3.9, -.8], edge(a.group, -.92, 0)], C.purple),
    route(root, [edge(a.group, .92, 0), edge(b.group, -.25, 0)], C.purple),
    route(root, [edge(b.group, .25, 0), [1.7, -.8], [2.76, 0]], C.coral),
    route(root, [[3.274, 0], edge(output.group, -.165, 0)], C.green),
  ];
  const flows = paths.map((p, i) => stream(root, p, i < 2 ? C.blue : i < 4 ? C.purple : C.coral, 3));
  const lossStart = edge(output.group, 0, -.59);
  const lossEnd = edge(a.group, -.92, -.16);
  const loss = route(root, [lossStart, [lossStart[0], -.76], [5.55, -.76], [5.55, -2.2], [-3.5, -2.2], [-3.5, lossEnd[1]], lossEnd], C.coral);
  const lossBEnd = edge(b.group, .25, -.48);
  const lossB = route(root, [[1.45, -2.2], [1.45, lossBEnd[1]], lossBEnd], C.coral);
  const back = [stream(root, loss, C.coral, 8), stream(root, lossB, C.coral, 2)];
  let lastFrame = -1;
  return (t, mode) => {
    flows.forEach(flow => flow(t, true)); back.forEach(flow => flow(t, mode === 1));
    const frame = Math.floor(t * 3);
    if (frame !== lastFrame || mode === 0) {
      [a, b].forEach(m => {
        for (let i = 0; i < m.cells.count; i++) {
          const value = mode === 1 ? ((i * 7 + frame * 3) % 13) / 16 : ((i * 7) % 13) / 20;
          m.cells.setColorAt(i, m.base.clone().lerp(new THREE.Color("#fff"), .12 + value));
        }
        m.cells.instanceColor!.needsUpdate = true;
      });
      lastFrame = frame;
    }
    frozen.group.position.y = .8;
  };
}

function inspection(scene: THREE.Scene): Tick {
  const root = group(scene, 0);
  const xs = [-4.3, -1.35, 1.55, 4.45];
  const names = ["INPUT CHECK", "IRI v5", "OUTPUT CHECK", "TTS"];
  const colors = [C.green, C.purple, C.green, C.coral];
  const towers = xs.map((x, i) => {
    const g = panel(root, x, .2, 1.82, 1.55, colors[i], names[i]);
    if (i === 1) matrix(g, 0, -.13, 6, 3, C.purple, .18).group.position.z = .2;
    else if (i === 3) waveform(g, 0, -.1, C.coral, 1.2, 13);
    else {
      text(g, "allow / block", 0, -.06, 1.48, C.ink, .08);
      for (let j = 0; j < 5; j++) box(g, .15, .12, .045, mat(C.green), [-.49 + j * .245, -.4, .07]);
    }
    return g;
  });
  const routes = xs.slice(0, 3).map((_, i) => route(root, [edge(towers[i], .91, 0), edge(towers[i + 1], -.91, 0)], colors[i]));
  const flows = routes.map((p, i) => stream(root, p, colors[i], 3));
  const policy = panel(root, -3.15, -1.15, 1.7, .6, "#8495a4", "POLICY RESPONSE");
  policy.rotation.y = 0;
  const blockedIn = stream(root, route(root, [edge(towers[0], 0, -.775), [-4.3, -1.15], edge(policy, -.85, 0)], C.coral), C.coral, 2);
  const blockedOut = stream(root, route(root, [edge(towers[2], 0, -.775), [1.55, -.85], [-1.95, -.85], [-1.95, -1.15], edge(policy, .85, 0)], C.coral), C.coral, 5);
  const reroute = group(root, 1.4, -1.3, -.1);
  const phases = [-1, 0, 1].map((x, i) => panel(reroute, x, 0, .72, .55, C.blue, ["IN", "GEN", "OUT"][i]));
  phases.forEach(p => { p.rotation.y = 0; });
  const fallback = stream(root, route(root, [edge(towers[0], -.91, 0), [-5.65, .2], [-5.65, -2.45], [-.3, -2.45], [-.3, -1.3], edge(phases[0], -.36, 0)], C.blue), C.blue, 8);
  const fallbackSteps = [0, 1].map(i => stream(root, route(root, [edge(phases[i], .36, 0), edge(phases[i + 1], -.36, 0)], C.blue), C.blue, 1));
  const fallbackExit = stream(root, route(root, [edge(phases[2], .36, 0), [4.45, -1.3], edge(towers[3], 0, -.775)], C.blue), C.blue, 3);
  return (t, mode) => {
    flows.forEach((flow, i) => flow(t, mode === 0 || (mode === 2 && i < 2)));
    blockedIn(t, mode === 1); blockedOut(t, mode === 2);
    fallback(t, mode === 3); fallbackExit(t, mode === 3); fallbackSteps.forEach(s => s(t, mode === 3));
    towers.forEach((g, i) => { g.position.z = mode === 3 || (mode === 1 && i > 0) ? -.08 : .025 * Math.sin(t * 2 - i); });
  };
}

function age(scene: THREE.Scene): Tick {
  const root = group(scene, 0);
  const condition = panel(root, -3.1, 0, 2.5, 1.7, C.purple, "AGE CONDITION");
  const ages = [text(condition, "4~6세", 0, -.1, 1.7, C.purple, .08), text(condition, "7~10세", 0, -.1, 1.7, C.blue, .08)];
  const paths = [route(root, [[-1.8, 0], [-.8, 0], [.8, .6]], C.coral), route(root, [[-1.8, 0], [-.8, 0], [.8, -.5]], C.blue)];
  const streams = paths.map((p, i) => stream(root, p, i ? C.blue : C.coral));
  const rows = [0, 1].map(i => {
    const g = group(root, 2.65, i ? -.5 : .6);
    const color = i ? C.blue : C.coral;
    box(g, 3.4, .72, .1, mat(color, .15));
    const words = i ? ["원인", "과정", "결과", "예시"] : ["쉬운 말", "짧은 문장"];
    words.forEach((word, j) => {
      const x = (j - (words.length - 1) / 2) * (i ? .78 : 1.45);
      box(g, i ? .7 : 1.3, .45, .12, mat(color), [x, 0, .1]);
      text(g, word, x, 0, i ? .66 : 1.1, "#ffffff", .18);
    });
    return g;
  });
  return (t, mode) => { ages.forEach((a, i) => { a.visible = mode === i; }); streams.forEach((s, i) => s(t, mode === i)); rows.forEach((r, i) => { r.position.z = mode === i ? .15 : -.15; r.scale.setScalar(mode === i ? 1 : .93); }); };
}

function memory(scene: THREE.Scene): Tick {
  const root = group(scene, 0);
  const colors = [C.blue, C.purple, C.coral, C.green, C.blue, C.purple];
  const cells = colors.map((color, i) => {
    const g = panel(root, -2.8 + i * 1.12, .2, .9, 1.2, color, `TURN ${i + 1}`);
    text(g, "Q", -.17, -.06, .36, color, .1); text(g, "A", .17, -.26, .36, color, .1);
    return g;
  });
  const rail = route(root, [[4.5, -.65], [0, -.65], [-4.5, -.65]], C.track);
  const flow = stream(root, rail, C.purple, 7);
  const old = panel(root, -4.3, .2, .7, 1, "#aeb7c1", "OLD");
  const fresh = panel(root, 4.3, .2, .7, 1, C.coral, "NEW");
  return (t, mode) => {
    flow(t, mode === 0);
    cells.forEach((cell, i) => { cell.scale.y = mode === 1 ? .08 : 1; cell.position.z = mode === 0 ? Math.max(0, Math.sin(t * .8 - i * .55)) * .14 : -.2; });
    old.position.x = -4.3 - (t * .15 % .7); old.visible = mode === 0;
    fresh.position.x = 4.3 - (t * .15 % .5); fresh.visible = mode === 0;
  };
}

export const productDiagrams: Record<IllustrationKind, (scene: THREE.Scene) => Tick> = { conversation, adapter, inspection, age, memory };
