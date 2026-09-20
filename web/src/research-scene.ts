import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { productDiagrams } from "./product-diagrams";
import { diagramContent } from "./diagram-content";
import type { IllustrationKind } from "./diagram-content";
export type { IllustrationKind } from "./diagram-content";

export function createResearchScene(container: HTMLElement, kind: IllustrationKind) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setClearColor(0xffffff, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.domElement.setAttribute("aria-hidden", "true");
  container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-6.2, 6.2, 3.1, -3.1, .1, 40);
  camera.position.set(0, 0, 20); camera.lookAt(0, 0, 0);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, .06);
  scene.environment = environment.texture; scene.environmentIntensity = .5;
  room.dispose(); pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x9eafc3, 1));
  const key = new THREE.DirectionalLight(0xfff8ee, 2);
  key.position.set(-4, 7, 8); scene.add(key);
  const fill = new THREE.DirectionalLight(0xcbdfff, 1);
  fill.position.set(5, 2, 3); scene.add(fill);
  const animate = productDiagrams[kind](scene);
  let mode = 0, time = 0;
  const labels = container.parentElement?.querySelectorAll<HTMLElement>(".diagram-label");
  const projectLabels = () => {
    diagramContent[kind].labels.forEach((label, i) => {
      const p = new THREE.Vector3(...label.at).project(camera);
      const node = labels?.[i];
      if (node) { node.style.left = `${(p.x + 1) * 50}%`; node.style.top = `${(1 - p.y) * 50}%`; }
    });
  };
  const resize = () => {
    const { width, height } = container.getBoundingClientRect();
    if (!width || !height) return;
    camera.top = 12.4 / (width / height) / 2; camera.bottom = -camera.top;
    camera.updateProjectionMatrix(); renderer.setSize(width, height, false);
    projectLabels(); renderer.render(scene, camera);
  };
  resize();
  return {
    canvas: renderer.domElement, resize,
    setMode(value: number) { mode = value; animate(time, mode); renderer.render(scene, camera); },
    render(value: number) { time = value; animate(time, mode); renderer.render(scene, camera); },
    dispose() {
      const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
      scene.traverse(object => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          (Array.isArray(object.material) ? object.material : [object.material]).forEach(material => {
            materials.add(material);
            Object.values(material).forEach(value => { if (value instanceof THREE.Texture) textures.add(value); });
          });
          if (object instanceof THREE.InstancedMesh) object.dispose();
        }
      });
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose()); textures.forEach(texture => texture.dispose());
      environment.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    },
  };
}
