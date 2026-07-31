import * as THREE from "three";
import { OrbitControls } from "/vendor/three/examples/jsm/controls/OrbitControls.js";

const radians = (degrees = 0) => degrees * Math.PI / 180;

function metal(color) {
  return new THREE.MeshStandardMaterial({
    color,
    metalness: 0.72,
    roughness: 0.24,
    envMapIntensity: 0.8,
  });
}

function extrudedRing(outer, inner, depth, color, teeth = 0) {
  const shape = new THREE.Shape();
  if (teeth) {
    for (let i = 0; i < teeth * 4; i++) {
      const angle = i * Math.PI * 2 / (teeth * 4);
      const radius = i % 4 < 2 ? outer : outer * .86;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      i ? shape.lineTo(x, y) : shape.moveTo(x, y);
    }
    shape.closePath();
  } else {
    shape.absarc(0, 0, outer, 0, Math.PI * 2);
  }
  if (inner > 0) {
    const hole = new THREE.Path();
    hole.absarc(0, 0, inner, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelSegments: 3,
    bevelSize: Math.min(depth * .08, outer * .025),
    bevelThickness: Math.min(depth * .08, outer * .025),
    curveSegments: Math.max(48, teeth * 4),
  });
  geometry.center();
  geometry.computeVertexNormals();
  return new THREE.Mesh(geometry, metal(color));
}

function cylinder(item) {
  const geometry = new THREE.CylinderGeometry(item.r, item.r, item.depth, 64, 1, false);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, metal(item.color));
  mesh.rotation.z = radians(item.rotate?.[1] || 0);
  return mesh;
}

function buildPart(item) {
  let object;
  if (item.type === "mesh") {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(item.positions, 3));
    geometry.setIndex(item.indices);
    geometry.computeVertexNormals();
    object = new THREE.Mesh(geometry, metal(item.color));
  } else if (item.type === "tube") object = extrudedRing(item.r, item.inner || 0, item.depth, item.color);
  else if (item.type === "gear") object = extrudedRing(item.r, item.inner || 0, item.depth, item.color, item.teeth);
  else if (item.type === "sphere") {
    object = new THREE.Mesh(new THREE.SphereGeometry(item.r, 64, 36), metal(item.color));
    if (item.scale) object.scale.set(...item.scale);
  } else if (item.type === "torus") {
    object = new THREE.Mesh(new THREE.TorusGeometry(item.r, item.tube, 24, 96), metal(item.color));
  } else if (item.type === "helix") {
    const turns = Math.max(3, item.depth / Math.max(1, item.pitch));
    const pointCount = Math.min(1000, Math.ceil(turns * 36));
    const points = Array.from({ length: pointCount }, (_, i) => {
      const t = i / (pointCount - 1);
      const angle = t * turns * Math.PI * 2;
      return new THREE.Vector3((t - .5) * item.depth, Math.cos(angle) * item.r, Math.sin(angle) * item.r);
    });
    object = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), points.length, Math.max(.8, item.r * .055), 8, false), metal(item.color));
  } else object = cylinder(item);
  if (item.at) object.position.set(...item.at);
  if (item.rotate && item.type !== "cylinder") object.rotation.set(...item.rotate.map(radians));
  object.castShadow = true;
  object.receiveShadow = true;
  return object;
}

export class CadModelViewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#f4f6f8");
    this.camera = new THREE.PerspectiveCamera(34, 1, .1, 10000);
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = .07;
    this.controls.addEventListener("change", () => this.render());
    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.addStage();
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.animate();
  }
  addStage() {
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667085, 2.2));
    const key = new THREE.DirectionalLight(0xffffff, 4.2);
    key.position.set(-180, 220, 280); key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xb980d0, 2.1);
    rim.position.set(260, -80, 120); this.scene.add(rim);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), new THREE.ShadowMaterial({ color: 0x263142, opacity: .16 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -130; ground.receiveShadow = true; this.scene.add(ground);
    const grid = new THREE.GridHelper(900, 30, 0xc7ccd4, 0xdfe3e8);
    grid.position.y = -129; this.scene.add(grid);
  }
  setModel(model) {
    this.group.clear();
    model.forEach(item => this.group.add(buildPart(item)));
    const box = new THREE.Box3().setFromObject(this.group);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    this.group.position.sub(center);
    const span = Math.max(size.x, size.y, size.z, 1);
    this.camera.position.set(span * 1.35, span * .95, span * 1.6);
    this.camera.near = span / 100; this.camera.far = span * 100; this.camera.updateProjectionMatrix();
    this.controls.target.set(0, 0, 0); this.controls.minDistance = span * .65; this.controls.maxDistance = span * 5; this.controls.update();
    this.render();
  }
  resize() {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    this.renderer.setSize(rect.width, rect.height, false);
    this.camera.aspect = rect.width / rect.height;
    this.camera.updateProjectionMatrix();
    this.render();
  }
  render() { this.renderer.render(this.scene, this.camera); }
  animate() {
    this.controls.update();
    this.render();
    requestAnimationFrame(() => this.animate());
  }
}
