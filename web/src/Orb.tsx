import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import * as THREE from "three";
import type { AudioSignalRef } from "./audio-level";
import { smoothLevel } from "./audio-level";
import { createMorphScene } from "./morph-scene";
import { orbHelpers } from "./shaders";

const vertexShader = `
  uniform float uTime;
  uniform float uLevel;
  uniform float uTalking;
  uniform float uPull;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec3 vView;
  ${orbHelpers}
  vec3 deform(vec3 p) {
    float t = uTime * mix(0.65, 1.05, uTalking);
    float broad = snoise3(p * 1.2 + vec3(t * 0.43, -t * 0.3, t * 0.27));
    float detail = snoise3(p * 2.0 + vec3(-t * 0.25, t * 0.35, 0.0));
    float wave = broad * 0.9 + detail * 0.1;
    float radius = 1.0 + uLevel * 0.09 + wave * uLevel * mix(0.30, 0.28, uTalking);
    vec3 direction = normalize(p);
    float pull = pow(max(dot(direction, normalize(vec3(1.0, 0.2, 0.0))), 0.0), 18.0) * uPull;
    return direction * (clamp(radius, 0.80, 1.18) + pull);
  }
  void main() {
    vec3 displaced = deform(position);
    vec3 axis = abs(normal.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 tangent = normalize(cross(axis, normal));
    vec3 bitangent = normalize(cross(normal, tangent));
    float epsilon = 0.003;
    vec3 alongT = deform(normalize(position + tangent * epsilon)) - displaced;
    vec3 alongB = deform(normalize(position + bitangent * epsilon)) - displaced;
    vec3 displacedNormal = normalize(cross(alongT, alongB));
    vPosition = displaced;
    vNormal = normalize(normalMatrix * displacedNormal);
    vec4 viewPosition = modelViewMatrix * vec4(displaced, 1.0);
    vView = -viewPosition.xyz;
    gl_Position = projectionMatrix * viewPosition;
  }
`;

const fragmentShader = `
  uniform float uTime;
  uniform float uHover;
  uniform float uHue;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec3 vView;
  ${orbHelpers}
  void main() {
    vec3 n = normalize(vNormal);
    vec3 view = normalize(vView);
    float facing = max(dot(n, view), 0.0);
    float rim = pow(1.0 - facing, 2.2);
    vec3 p = vPosition;
    float t = uTime * 0.32;
    p += uHover * 0.094 * sin(p.yzx * 10.0 + uTime);
    float noise = snoise3(p * 1.65 + vec3(0.0, t, t * 0.6));
    float fine = snoise3(p * 3.2 + vec3(t * 0.4, -t * 0.6, 0.0));
    float angle = atan(p.y, p.x);
    vec3 c1 = adjustHue(vec3(0.611765, 0.262745, 0.996078), uHue);
    vec3 c2 = adjustHue(vec3(0.298039, 0.760784, 0.913725), uHue);
    vec3 c3 = adjustHue(vec3(0.062745, 0.078431, 0.600000), uHue);
    float flow = 0.5 + 0.5 * sin(angle + noise * 2.5 - t * 1.5);
    vec3 color = mix(c1, c2, flow);
    color = mix(color, c3, 0.12 * (0.5 + fine * 0.5));
    float fold = pow(0.5 + 0.5 * sin(p.y * 4.5 + p.x * 2.0 + noise * 3.0 - t), 5.0);
    float veil = fold * (1.0 - facing) * 0.42;
    float shoulder = pow(1.0 - facing, 0.65);
    float density = 0.035 + shoulder * 0.12 + rim * 0.55 + veil;
    float highlight = pow(max(dot(reflect(-normalize(vec3(-0.6, 0.9, 1.8)), n), view), 0.0), 65.0);
    color = mix(color, vec3(1.0), 0.12 + highlight * 0.82);
    float edge = smoothstep(0.0, 0.07, facing);
    gl_FragColor = vec4(color, clamp(density + highlight * 0.24, 0.0, 0.85) * edge);
  }
`;

export function Orb({
  signal,
  selection,
  onActivate,
  label,
  hint,
  announce = false,
  recording,
  disabled,
}: {
  signal: AudioSignalRef;
  selection: RefObject<number>;
  onActivate: () => void;
  label: string;
  hint: string;
  announce?: boolean;
  recording: boolean;
  disabled: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const container = host.current;
    if (!container) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
    } catch {
      setFailed(true);
      return;
    }

    renderer.setClearColor(0xffffff, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25));
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 20);
    camera.position.z = 4.4;
    const uniforms = {
      uTime: { value: 0 },
      uHover: { value: 0 },
      uHue: { value: 301 },
      uLevel: { value: 0 },
      uTalking: { value: 0 },
      uPull: { value: 0 },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms,
      transparent: true,
      depthWrite: false,
    });
    const hitSphere = new THREE.Sphere(new THREE.Vector3(), 1);
    const hitPoint = new THREE.Vector3();
    const morph = createMorphScene(scene, material, camera);
    morph.ready.catch(() => setFailed(true));
    let lastSelection = 0;

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      container.style.setProperty("--orb-diameter", `${Math.min(height * 0.8, width / 2.65)}px`);
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.position.z = Math.max(
        4.4,
        2.65 / (Math.tan(THREE.MathUtils.degToRad(16)) * camera.aspect),
      );
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let targetHover = 0;
    let frame = 0;
    let previous = 0;
    let elapsed = 0;
    const pointer = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();

    const onMove = (event: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      targetHover = raycaster.ray.intersectSphere(hitSphere, hitPoint) ? 1 : 0;
      const distance = -raycaster.ray.origin.z / raycaster.ray.direction.z;
      morph.pointer(
        raycaster.ray.origin.x + raycaster.ray.direction.x * distance,
        raycaster.ray.origin.y + raycaster.ray.direction.y * distance,
      );
    };
    const onLeave = () => {
      targetHover = 0;
      morph.leave();
    };
    const render = (now: number) => {
      const motionDt = previous ? Math.min((now - previous) / 1000, 0.25) : 0;
      const dt = Math.min(motionDt, 0.05);
      previous = now;
      if (!reduced.matches) elapsed += dt;
      uniforms.uTime.value = elapsed;
      if (selection.current !== lastSelection) {
        lastSelection = selection.current;
        morph.select(
          (lastSelection - 1) % 4 === 3 ? -1 : (lastSelection - 1) % 4,
        );
      }
      container.dataset.morphState = morph.update(
        motionDt,
        elapsed,
        reduced.matches,
      );
      const state = signal.current.state;
      const thinking = state === "thinking" && !reduced.matches;
      const measured = reduced.matches ? 0 : signal.current.read();
      const activity = thinking
        ? 0.075 + Math.sin(elapsed * 2.2) * 0.025
        : measured;
      uniforms.uLevel.value = smoothLevel(uniforms.uLevel.value, activity, dt);
      const talkingTarget = state === "talking" ? 1 : thinking ? 0.42 : 0;
      uniforms.uTalking.value +=
        (talkingTarget - uniforms.uTalking.value) * (1 - Math.exp(-dt * 4));
      uniforms.uHover.value +=
        ((reduced.matches ? 0 : targetHover) - uniforms.uHover.value) *
        (1 - Math.exp(-dt * 7));
      renderer.render(scene, camera);
      if (!document.hidden) frame = requestAnimationFrame(render);
    };
    const resume = () => {
      cancelAnimationFrame(frame);
      previous = 0;
      if (!document.hidden) frame = requestAnimationFrame(render);
    };
    const contextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
      setFailed(true);
    };

    container.addEventListener("pointermove", onMove);
    container.addEventListener("pointerleave", onLeave);
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    document.addEventListener("visibilitychange", resume);
    reduced.addEventListener("change", resume);
    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      container.removeEventListener("pointermove", onMove);
      container.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", resume);
      reduced.removeEventListener("change", resume);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      morph.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [selection, signal]);

  return (
    <div
      ref={host}
      className={`orb${failed ? " orb-fallback" : ""}`}
    >
      <p className="orb-invitation" role={announce ? "status" : undefined}>
        <span key={hint} className="orb-invitation-text">
          {hint}
        </span>
      </p>
      <button
        type="button"
        className="orb-trigger"
        onClick={onActivate}
        aria-label={label}
        aria-pressed={recording}
        disabled={disabled}
      />
    </div>
  );
}
