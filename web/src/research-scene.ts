import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export type IllustrationKind = "conversation" | "adapter" | "inspection" | "age" | "memory";

const palette = {
  blue: "#629fce", paleBlue: "#bdd6ec", coral: "#e88d77", cream: "#f5db8a",
  green: "#78b295", lilac: "#a78bce", ink: "#526779", white: "#ffffff",
};

function material(color: string, metalness = 0) {
  return new THREE.MeshPhysicalMaterial({ color, roughness: metalness ? 0.3 : 0.42, metalness, clearcoat: 0.25, clearcoatRoughness: 0.3 });
}

function roundedShape(w: number, h: number, radius: number) {
  const r = Math.min(radius, w / 2, h / 2), x = -w / 2, y = -h / 2;
  const s = new THREE.Shape();
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y);
  s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h);
  s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r);
  s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

function mesh(geometry: THREE.BufferGeometry, mat: THREE.Material, parent: THREE.Object3D, x = 0, y = 0, z = 0) {
  const object = new THREE.Mesh(geometry, mat);
  object.position.set(x, y, z);
  object.castShadow = true;
  object.receiveShadow = true;
  parent.add(object);
  return object;
}

function solid(shape: THREE.Shape, depth: number, mat: THREE.Material, parent: THREE.Object3D, bevel = 0.045) {
  const geometry = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelSegments: 3, steps: 1, bevelSize: bevel, bevelThickness: bevel, curveSegments: 16 });
  geometry.translate(0, 0, -depth / 2);
  return mesh(geometry, mat, parent);
}

function slab(parent: THREE.Object3D, w: number, h: number, depth: number, mat: THREE.Material, radius = 0.1) {
  return solid(roundedShape(w, h, radius), depth, mat, parent, Math.min(0.045, depth * 0.25));
}

function line(parent: THREE.Object3D, points: number[][], mat: THREE.Material, radius = 0.025) {
  const curve = new THREE.CatmullRomCurve3(points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
  return mesh(new THREE.TubeGeometry(curve, 40, radius, 8, false), mat, parent);
}

function pill(parent: THREE.Object3D, w: number, h: number, mat: THREE.Material, x: number, y: number, z: number) {
  const result = slab(parent, w, h, 0.045, mat, Math.min(w, h) / 2);
  result.position.set(x, y, z);
  return result;
}

function group(parent: THREE.Object3D, x = 0, y = 0, z = 0) {
  const result = new THREE.Group();
  result.position.set(x, y, z);
  parent.add(result);
  return result;
}

function badge(parent: THREE.Object3D, x: number, y: number, z: number) {
  const result = group(parent, x, y, z);
  const disk = mesh(new THREE.CylinderGeometry(0.27, 0.27, 0.12, 48), material(palette.green), result);
  disk.rotation.x = Math.PI / 2;
  line(result, [[-.12, 0, .085], [-.025, -.085, .085], [.14, .12, .085]], material(palette.white), .026);
  return result;
}

function paper(parent: THREE.Object3D, x: number, color = palette.cream) {
  const result = group(parent, x, .05);
  const back = slab(result, 1.55, 1.98, .035, material("#f0e9d6"), .04);
  back.position.set(.09, -.06, -.14);
  back.rotation.z = -.045;
  slab(result, 1.55, 1.98, .07, material(color), .04);
  const fold = new THREE.Shape();
  fold.moveTo(.46, .98); fold.lineTo(.76, .68); fold.lineTo(.46, .68); fold.closePath();
  const foldedCorner = solid(fold, .025, material("#fff7d9"), result, .008);
  foldedCorner.position.z = .055;
  const registration = material("#d8bd76");
  for (let i = 0; i < 3; i++) pill(result, .026, .026, registration, -.57 + i * .072, -.77, .06);
  const gold = material("#c1a354");
  pill(result, .85, .065, gold, -.13, .62, .07);
  [1.08, .92, 1.04, .65].forEach((w, i) => pill(result, w, .032, gold, (w - 1.08) / 2, .26 - i * .24, .075));
  result.rotation.set(-.04, -.18, -.04);
  return result;
}

function bubble(parent: THREE.Object3D, x: number, y: number, color: string, scale = 1) {
  const result = group(parent, x, y);
  const s = roundedShape(1.8, 1.23, .26);
  // The tail is part of the solid, with the same rounded bevel as its body.
  const tail = new THREE.Shape();
  tail.moveTo(-.48, -.56); tail.lineTo(-.48, -.98); tail.lineTo(.02, -.56); tail.closePath();
  solid(s, .3, material(color), result, .07);
  solid(tail, .3, material(color), result, .035);
  result.scale.setScalar(scale);
  return result;
}

function connector(parent: THREE.Object3D, from: number, to: number) {
  const mat = material("#d4dce5");
  for (let x = from; x < to; x += .16) mesh(new THREE.SphereGeometry(.017, 8, 6), mat, parent, x, 0, -.2);
}

function conversation(scene: THREE.Scene) {
  const root = group(scene);
  const mic = group(root, -3.45, -.04);
  const silver = material("#9daebe", .72);
  const grille = material("#355774", .1);
  const base = mesh(new THREE.CylinderGeometry(.52, .58, .105, 48), silver, mic, 0, -1.02);
  base.scale.z = .68;
  mesh(new THREE.CylinderGeometry(.045, .055, .38, 20), silver, mic, 0, -.8);
  line(mic, [[-.55,.18,0],[-.55,-.34,0],[-.39,-.57,0],[0,-.66,0],[.39,-.57,0],[.55,-.34,0],[.55,.18,0]], silver, .041);
  const head = group(mic, 0, .35);
  mesh(new THREE.CapsuleGeometry(.38, .57, 10, 32), material(palette.blue, .15), head);
  for (let i = 0; i < 8; i++) pill(head, .43, .025, grille, 0, .36 - i * .102, .376);
  const perforations = new THREE.InstancedMesh(new THREE.SphereGeometry(.009, 6, 4), grille, 54);
  const dot = new THREE.Object3D();
  for (let i = 0; i < 54; i++) {
    dot.position.set(-.19 + (i % 9) * .0475, .31 - Math.floor(i / 9) * .102, .385);
    dot.updateMatrix(); perforations.setMatrixAt(i, dot.matrix);
  }
  head.add(perforations);
  [-1, 1].forEach(side => {
    const pivot = mesh(new THREE.CylinderGeometry(.095, .095, .16, 24), silver, mic, side * .47, .02);
    pivot.rotation.z = Math.PI / 2;
  });
  mic.rotation.y = -.32;
  const page = paper(root, -.05);
  badge(page, .66, -.76, .2);
  const speech = bubble(root, 3.35, .21, palette.coral);
  speech.rotation.set(.02, -.27, .035);
  const bars = [.28, .58, .43, .78, .32].map((h, i) => pill(speech, .082, h, material("#fffaf2"), -.48 + .24 * i, .015, .245));
  connector(root, -2.45, -1.05); connector(root, 1.08, 2.25);
  return (t: number) => {
    head.rotation.z = Math.sin(t * .7) * .025;
    page.rotation.y = -.18 + Math.sin(t * .55) * .045;
    speech.position.y = .21 + Math.sin(t * .8) * .035;
    bars.forEach((bar, i) => { bar.scale.y = .78 + Math.sin(t * 2.5 + i * 1.3) * .22; });
  };
}

function adapter(scene: THREE.Scene) {
  const root = group(scene, -.4, .02);
  root.scale.setScalar(.8);
  root.rotation.set(.28, -.47, 0);
  const plates = ["#6c9fcf", "#8bb5dc", "#b3d1ea"].map((color, i) => {
    const p = slab(root, 2.7, 1.75, .18, material(color, .18), .13);
    p.rotation.x = -Math.PI / 2;
    p.position.y = -.6 + i * .37;
    return p;
  });
  const chip = group(root, 0, .94);
  const traceMat = material("#7b9cb8", .35);
  for (let i = 0; i < 4; i++) {
    line(root, [[-1.02 + i * .22,.26,.54],[-1.02 + i * .22,.26,.18],[-.65 + i * .22,.26,-.18]], traceMat, .012);
  }
  const tile = slab(chip, 1.65, 1.14, .16, material(palette.lilac, .16), .13);
  tile.rotation.x = -Math.PI / 2;
  const die = slab(chip, .72, .6, .06, material("#e6d8f5", .25), .06);
  die.rotation.x = -Math.PI / 2;
  die.position.y = .14;
  const pins = material("#d9c7a0", .65);
  for (let i = 0; i < 6; i++) {
    [-1, 1].forEach(side => {
      const pin = mesh(new THREE.BoxGeometry(.08, .05, .16), pins, chip, -.57 + i * .225, -.02, side * .63);
      pin.castShadow = false;
    });
  }
  return (t: number) => { chip.position.y = .94 + Math.sin(t * .9) * .095; plates[2].position.y = .14 + Math.sin(t * .9 - .3) * .02; };
}

function inspection(scene: THREE.Scene) {
  const root = group(scene);
  const input = paper(root, -2.9, "#e2edf8");
  input.scale.setScalar(.72);
  const output = paper(root, 2.9);
  output.scale.setScalar(.72);
  badge(output, .65, -.77, .2);
  const guard = group(root, 0, .04);
  const shape = new THREE.Shape();
  shape.moveTo(0, 1); shape.quadraticCurveTo(.5, .7, .84, .72);
  shape.lineTo(.8, -.1); shape.bezierCurveTo(.76, -.6, .3, -.92, 0, -1.08);
  shape.bezierCurveTo(-.3, -.92, -.76, -.6, -.8, -.1); shape.lineTo(-.84, .72); shape.quadraticCurveTo(-.5, .7, 0, 1);
  solid(shape, .22, material(palette.green, .15), guard, .065);
  const inner = solid(shape, .04, material("#b8d8c3"), guard, .025);
  inner.scale.set(.8, .8, 1); inner.position.z = .18;
  const lens = group(guard, .02, .06, .3);
  mesh(new THREE.TorusGeometry(.3, .036, 12, 48), material("#f9fcf9", .35), lens);
  line(lens, [[.2,-.2,0],[.44,-.48,0]], material("#f9fcf9", .35), .047);
  guard.rotation.y = -.2;
  connector(root, -2.08, -1.06); connector(root, 1.04, 2.03);
  return (t: number) => { lens.position.x = .02 + Math.sin(t * .8) * .045; lens.position.y = .06 + Math.cos(t * .8) * .045; };
}

function book(parent: THREE.Object3D, x: number, color: string, scale: number) {
  const g = group(parent, x, -.2);
  const pages = slab(g, 1.3, 1.67, .23, material("#fffcf2"), .035);
  pages.position.z = .02;
  [-1, 1].forEach(side => {
    const cover = slab(g, 1.43, 1.8, .055, material(color), .06);
    cover.position.z = side * .16;
  });
  const spine = slab(g, .13, 1.81, .35, material(color), .035);
  spine.position.x = -.7;
  const pageEdges = material("#d7cdb8");
  for (let i = 0; i < 5; i++) {
    line(g, [[.655,-.77,-.08 + i * .04],[.655,.77,-.08 + i * .04]], pageEdges, .006);
  }
  line(g, [[-.53,-.79,.205],[-.53,.78,.205]], material(color), .013);
  const bookmark = slab(g, .15, .32, .015, material("#d9c390"), .015);
  bookmark.position.set(.37, -.87, .08);
  pill(g, .73, .045, material("#ffffff"), .04, .35, .225);
  pill(g, .47, .03, material("#ffffff"), -.09, .18, .225);
  g.rotation.set(-.08, -.28, -.09);
  g.scale.setScalar(scale);
  return g;
}

function age(scene: THREE.Scene) {
  const root = group(scene);
  book(root, -1.65, palette.coral, .88);
  book(root, 1.65, palette.blue, 1.02);
  const bubbles = [-1.65, 1.65].map((x, i) => {
    const b = bubble(root, x + .56, .76, i ? palette.lilac : palette.cream, .46);
    b.position.z = .5;
    const ink = material(i ? "#786493" : "#b8a25c");
    for (let n = 0; n < (i ? 3 : 2); n++) pill(b, 1.03 - n * .15, .045, ink, -.02, .23 - n * .21, .24);
    return b;
  });
  return (t: number) => { bubbles.forEach((b, i) => { b.position.y = .76 + Math.sin(t * .8 + i) * .045; }); };
}

function memory(scene: THREE.Scene) {
  const root = group(scene);
  const colors = [palette.blue, palette.cream, palette.coral, palette.green, palette.lilac, palette.paleBlue];
  const cards = colors.map((color, i) => {
    const g = group(root, -2.15 + i * .42, -.07 + i * .06, -i * .055);
    slab(g, .86, 1.32, .12, material(color), .09);
    pill(g, .4, .035, material("#ffffff"), 0, .28, .1);
    pill(g, .32, .03, material("#ffffff"), -.04, .1, .1);
    g.rotation.set(-.06, -.38, -.1);
    return g;
  });
  const clock = group(root, 1.7, .06);
  const body = mesh(new THREE.CylinderGeometry(.73, .73, .22, 64), material("#e6ded2", .2), clock);
  body.rotation.x = Math.PI / 2;
  const face = mesh(new THREE.CylinderGeometry(.64, .64, .04, 64), material("#fffdf9"), clock, 0, 0, .14);
  face.rotation.x = Math.PI / 2;
  const dark = material(palette.ink);
  for (let i = 0; i < 12; i++) {
    const angle = i * Math.PI / 6;
    const mark = pill(clock, .022, .08, dark, Math.sin(angle) * .53, Math.cos(angle) * .53, .18);
    mark.rotation.z = -angle;
  }
  const hands = group(clock, 0, 0, .22);
  line(hands, [[0,.37,0],[0,0,0],[.24,-.15,0]], dark, .023);
  mesh(new THREE.SphereGeometry(.04, 16, 12), material(palette.coral), clock, 0, 0, .25);
  clock.rotation.y = -.12;
  return (t: number) => { cards.forEach((card, i) => { card.position.y = -.07 + i * .06 + Math.sin(t * .7 + i * .4) * .028; }); };
}

const builders = { conversation, adapter, inspection, age, memory };

function contactShadows(scene: THREE.Scene, kind: IllustrationKind) {
  const canvas = document.createElement("canvas");
  canvas.width = 128; canvas.height = 128;
  const context = canvas.getContext("2d")!;
  const fade = context.createRadialGradient(64, 64, 1, 64, 64, 64);
  fade.addColorStop(0, "rgba(66, 78, 96, 0.22)");
  fade.addColorStop(.35, "rgba(66, 78, 96, 0.13)");
  fade.addColorStop(1, "rgba(66, 78, 96, 0)");
  context.fillStyle = fade; context.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  const shadows = kind === "conversation" ? [[-3.45, 1.7], [0, 2.1], [3.35, 2.1]]
    : kind === "inspection" ? [[-2.9, 1.7], [0, 2], [2.9, 1.7]]
    : kind === "age" ? [[-1.65, 1.9], [1.65, 2.1]]
    : kind === "memory" ? [[-1.1, 3.3], [1.7, 1.9]] : [[0, 3.9]];
  const mat = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
  shadows.forEach(([x, width]) => {
    const shadow = mesh(new THREE.PlaneGeometry(width, 1.4), mat, scene, x, -1.13, 0);
    shadow.rotation.x = -Math.PI / 2;
    shadow.castShadow = false;
  });
  return texture;
}

export function createResearchScene(container: HTMLElement, kind: IllustrationKind) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setClearColor(0xffffff, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .95;
  renderer.domElement.setAttribute("aria-hidden", "true");
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-5.3, 5.3, 1.65, -1.65, .1, 40);
  camera.position.set(0, 2.7, 14);
  camera.lookAt(0, 0, 0);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, .06);
  scene.environment = environment.texture;
  scene.environmentIntensity = .45;
  room.dispose();
  pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff, 0xa6b5c4, .85));
  const key = new THREE.DirectionalLight(0xfff5e9, 2.5);
  key.position.set(-4, 7, 6);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xc9e0ff, .7);
  fill.position.set(5, 2, -3);
  scene.add(fill);
  const contactTexture = contactShadows(scene, kind);
  const animate = builders[kind](scene);
  const resize = () => {
    const { width, height } = container.getBoundingClientRect();
    if (!width || !height) return;
    const span = kind === "conversation" || kind === "inspection" ? 10.6 : kind === "adapter" ? 7.3 : 6.5;
    camera.left = -span / 2; camera.right = span / 2;
    camera.top = span / (width / height) / 2; camera.bottom = -camera.top;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.render(scene, camera);
  };
  resize();
  return {
    canvas: renderer.domElement,
    resize,
    render(time: number) { animate(time); renderer.render(scene, camera); },
    dispose() {
      const geometries = new Set<THREE.BufferGeometry>();
      const materials = new Set<THREE.Material>();
      scene.traverse(object => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          (Array.isArray(object.material) ? object.material : [object.material]).forEach(mat => materials.add(mat));
        }
      });
      geometries.forEach(geometry => geometry.dispose());
      materials.forEach(mat => mat.dispose());
      contactTexture.dispose();
      environment.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
