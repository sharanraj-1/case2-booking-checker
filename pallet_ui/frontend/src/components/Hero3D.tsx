// Floating glass cargo cubes around a glowing core; the group leans toward the cursor.
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const CUBES: { p: [number, number, number]; s: number; speed: number }[] = [
  { p: [0, 0, 0], s: 1.25, speed: 0.25 },
  { p: [-1.9, 0.9, -0.6], s: 0.62, speed: 0.6 },
  { p: [1.95, -0.65, -0.3], s: 0.7, speed: 0.45 },
  { p: [1.2, 1.45, -1.2], s: 0.42, speed: 0.8 },
  { p: [-1.35, -1.35, 0.4], s: 0.46, speed: 0.7 },
  { p: [0.15, -1.85, -1.1], s: 0.32, speed: 0.95 },
];

function roundedBox(size: number) {
  const g = new THREE.BoxGeometry(size, size, size, 6, 6, 6);
  const pos = g.attributes.position;
  const v = new THREE.Vector3();
  const r = size * 0.16, h = size / 2 - r;
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    const c = new THREE.Vector3(Math.max(-h, Math.min(h, v.x)), Math.max(-h, Math.min(h, v.y)), Math.max(-h, Math.min(h, v.z)));
    const d = v.clone().sub(c).normalize().multiplyScalar(r);
    pos.setXYZ(i, c.x + d.x, c.y + d.y, c.z + d.z);
  }
  g.computeVertexNormals();
  return g;
}

function Cube({ p, s, speed, mat, edge }: { p: [number, number, number]; s: number; speed: number; mat: THREE.Material; edge: THREE.Material }) {
  const ref = useRef<THREE.Mesh>(null);
  const geo = useMemo(() => roundedBox(s), [s]);
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(s * 0.97, s * 0.97, s * 0.97)), [s]);
  const seed = useMemo(() => Math.random() * 10, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * speed + seed;
    if (!ref.current) return;
    ref.current.rotation.x = t * 0.5;
    ref.current.rotation.y = t * 0.7;
    ref.current.position.y = p[1] + Math.sin(t) * 0.12;
  });
  return (
    <mesh ref={ref} geometry={geo} material={mat} position={p}>
      <lineSegments geometry={edges} material={edge} />
    </mesh>
  );
}

function Scene() {
  const group = useRef<THREE.Group>(null);
  // Frosted glass without an environment map: translucent, glossy, iridescent, with bright edges.
  const glass = useMemo(() => new THREE.MeshPhysicalMaterial({
    color: "#dcd6ff", metalness: 0.1, roughness: 0.12, transparent: true, opacity: 0.2, depthWrite: false,
    side: THREE.DoubleSide, iridescence: 1, iridescenceIOR: 1.35, clearcoat: 1, clearcoatRoughness: 0.04,
    sheen: 1, sheenColor: new THREE.Color("#67e8f9"), specularIntensity: 1,
  }), []);
  const edge = useMemo(() => new THREE.LineBasicMaterial({ color: "#e0e7ff", transparent: true, opacity: 0.55 }), []);
  const core = useMemo(() => new THREE.MeshStandardMaterial({ color: "#0b0d12", emissive: "#8b5cf6", emissiveIntensity: 1.6 }), []);
  useFrame(({ pointer, clock }) => {
    if (!group.current) return;
    const t = clock.getElapsedTime();
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, pointer.x * 0.55 + t * 0.06, 0.05);
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, -pointer.y * 0.35, 0.05);
  });
  return (
    <group ref={group}>
      <mesh material={core}><icosahedronGeometry args={[0.32, 2]} /></mesh>
      {CUBES.map((c, i) => <Cube key={i} {...c} mat={glass} edge={edge} />)}
      <mesh rotation={[Math.PI / 2.6, 0, 0]}>
        <torusGeometry args={[2.35, 0.012, 16, 160]} />
        <meshBasicMaterial color="#67e8f9" transparent opacity={0.35} />
      </mesh>
    </group>
  );
}

export default function Hero3D() {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 0, 6.2], fov: 42 }} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      eventSource={document.getElementById("root") ?? undefined} eventPrefix="client">
      <ambientLight intensity={0.35} />
      <pointLight position={[4, 3, 4]} intensity={60} color="#8b5cf6" />
      <pointLight position={[-4, -2, 3]} intensity={50} color="#22d3ee" />
      <pointLight position={[0, 4, -3]} intensity={40} color="#f43f5e" />
      <directionalLight position={[0, 0, 5]} intensity={0.9} />
      <Scene />
    </Canvas>
  );
}
