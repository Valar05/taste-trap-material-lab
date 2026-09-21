import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.querySelector('#viewport');
const status = document.querySelector('#status');
const statusText = status.querySelector('span:last-child');
const firstPersonButton = document.querySelector('#firstPerson');
const thirdPersonButton = document.querySelector('#thirdPerson');
const resetButton = document.querySelector('#resetView');
const turntableButton = document.querySelector('#turntable');
const poseSelect = document.querySelector('#pose');
const viewLabel = document.querySelector('#viewLabel');
const errorPanel = document.querySelector('#error');
const errorDetail = document.querySelector('#errorDetail');
const retryButton = document.querySelector('#retry');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080b0e);
scene.fog = new THREE.Fog(0x080b0e, 6.5, 18);

const camera = new THREE.PerspectiveCamera(45, 1, 0.035, 100);
camera.position.set(0, 2.2, 6.2);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.065;
controls.enablePan = true;
controls.screenSpacePanning = true;
controls.touches.ONE = THREE.TOUCH.ROTATE;
controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
controls.minDistance = 0.35;
controls.maxDistance = 12;
controls.target.set(0, 1.05, 0);

scene.add(new THREE.HemisphereLight(0xd7e9f2, 0x241c16, 1.75));
const key = new THREE.DirectionalLight(0xffe7c3, 3.0);
key.position.set(3.6, 6.5, 4.0);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
scene.add(key);
const rim = new THREE.DirectionalLight(0x6aa7c8, 1.35);
rim.position.set(-4, 3.5, -4.5);
scene.add(rim);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(5.4, 80),
  new THREE.MeshStandardMaterial({ color: 0x1a2024, roughness: 0.82, metalness: 0.22 })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.012;
floor.receiveShadow = true;
scene.add(floor);

const grid = new THREE.GridHelper(8, 16, 0x9c7139, 0x303a40);
grid.position.y = 0.002;
grid.material.opacity = 0.42;
grid.material.transparent = true;
scene.add(grid);

const loader = new GLTFLoader();
const textureLoader = new THREE.TextureLoader();
const clock = new THREE.Clock();

let model = null;
let mixer = null;
let clips = [];
let cameraBone = null;
let viewMode = 'thirdPerson';
let orbitHome = null;
let turntable = false;

function setStatus(message, state = '') {
  statusText.textContent = message;
  status.classList.toggle('ready', state === 'ready');
  status.classList.toggle('error', state === 'error');
}

function findNamed(root, names) {
  const wanted = names.map((name) => name.toLowerCase());
  let result = null;
  root.traverse((node) => {
    if (!result && wanted.includes(String(node.name || '').toLowerCase())) result = node;
  });
  return result;
}

function loadTexture(url, color = false) {
  return new Promise((resolve, reject) => {
    textureLoader.load(url, (texture) => {
      texture.flipY = false;
      texture.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
      resolve(texture);
    }, undefined, reject);
  });
}

async function applyDonorTextures(root) {
  const [base, normal, roughness, metallic] = await Promise.all([
    loadTexture('./assets/fps-arms-basecolor.png', true),
    loadTexture('./assets/fps-arms-normal.png'),
    loadTexture('./assets/fps-arms-roughness.png'),
    loadTexture('./assets/fps-arms-metallic.png')
  ]);

  root.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = true;
    node.receiveShadow = true;
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    const updated = materials.map((source) => {
      const material = source?.clone?.() || new THREE.MeshStandardMaterial();
      material.map = base;
      material.normalMap = normal;
      material.normalScale = new THREE.Vector2(0.72, 0.72);
      material.roughnessMap = roughness;
      material.metalnessMap = metallic;
      material.roughness = 1;
      material.metalness = 1;
      material.envMapIntensity = 0.8;
      material.needsUpdate = true;
      return material;
    });
    node.material = Array.isArray(node.material) ? updated : updated[0];
  });
}

function groundAndFrame(root) {
  // Pose Lab stores this as a percentage: 100 means the authored 1× scale.
  root.scale.setScalar(1);
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  if (Number.isFinite(box.min.y)) root.position.y -= box.min.y;
  root.updateMatrixWorld(true);

  const groundedBox = new THREE.Box3().setFromObject(root);
  const sphere = groundedBox.getBoundingSphere(new THREE.Sphere());
  const center = sphere.center.clone();
  const radius = Math.max(0.35, sphere.radius);
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov * 0.46));
  orbitHome = {
    target: center.clone(),
    position: center.clone().add(new THREE.Vector3(radius * 0.35, radius * 0.18, distance * 0.92)),
    minDistance: Math.max(0.25, radius * 0.28),
    maxDistance: Math.max(4, radius * 7)
  };
  resetOrbit();
}

function resetOrbit() {
  if (!orbitHome) return;
  camera.fov = 45;
  camera.near = 0.035;
  camera.far = 100;
  camera.position.copy(orbitHome.position);
  controls.target.copy(orbitHome.target);
  controls.minDistance = orbitHome.minDistance;
  controls.maxDistance = orbitHome.maxDistance;
  camera.updateProjectionMatrix();
  controls.update();
}

function updateFirstPersonCamera() {
  if (viewMode !== 'firstPerson' || !cameraBone || !model) return;
  model.updateMatrixWorld(true);
  const worldPosition = new THREE.Vector3();
  const worldQuaternion = new THREE.Quaternion();
  const worldScale = new THREE.Vector3();
  cameraBone.matrixWorld.decompose(worldPosition, worldQuaternion, worldScale);
  const forward = new THREE.Vector3(0, 0, 1);
  camera.position.copy(worldPosition);
  camera.up.set(0, 1, 0);
  camera.lookAt(worldPosition.clone().add(forward.multiplyScalar(1.35)));
  camera.fov = 105;
  camera.near = 0.035;
  camera.far = 100;
  camera.updateProjectionMatrix();
}

function setView(mode) {
  viewMode = mode === 'firstPerson' && cameraBone ? 'firstPerson' : 'thirdPerson';
  const isFirst = viewMode === 'firstPerson';
  controls.enabled = !isFirst;
  firstPersonButton.classList.toggle('active', isFirst);
  thirdPersonButton.classList.toggle('active', !isFirst);
  viewLabel.textContent = isFirst ? 'FIRST PERSON' : 'THIRD PERSON';
  if (isFirst) updateFirstPersonCamera();
  else resetOrbit();
}

function choosePose(name) {
  if (!mixer) return;
  mixer.stopAllAction();
  if (name === '__rest__') {
    mixer.setTime(0);
    return;
  }
  const clip = clips.find((candidate) => candidate.name === name);
  if (!clip) return;
  const action = mixer.clipAction(clip);
  action.reset();
  action.setLoop(THREE.LoopOnce, 0);
  action.clampWhenFinished = true;
  action.play();
  mixer.update(0);
}

function populatePoses() {
  const preferredNames = ['FistReady', 'FistReadied', 'KnifeReady', 'KnifeReadied', 'OneHandReady', 'OneHandReadied', 'WandReady', 'WandReadied'];
  const preferred = preferredNames
    .map((name) => clips.find((clip) => clip.name === name))
    .filter(Boolean);
  poseSelect.replaceChildren();
  const rest = new Option('Model pose', '__rest__');
  poseSelect.add(rest);
  for (const clip of preferred) poseSelect.add(new Option(clip.name.replace(/([a-z])([A-Z])/g, '$1 $2'), clip.name));
  poseSelect.disabled = false;
  const initial = preferred.find((clip) => /FistReadied|FistReady/.test(clip.name)) || preferred[0];
  poseSelect.value = initial?.name || '__rest__';
  choosePose(poseSelect.value);
}

function hideNonArmHelpers(root) {
  const hidden = new Set(['plane', 'placeholderweapon']);
  root.traverse((node) => {
    if (hidden.has(String(node.name || '').toLowerCase())) node.visible = false;
  });
}

function loadModel() {
  errorPanel.hidden = true;
  setStatus('Loading arms');
  loader.load('./assets/FPSPlayer.glb', async (gltf) => {
    try {
      model = gltf.scene;
      clips = gltf.animations || [];
      hideNonArmHelpers(model);
      await applyDonorTextures(model);
      scene.add(model);
      groundAndFrame(model);
      cameraBone = findNamed(model, ['Camera']);
      mixer = clips.length ? new THREE.AnimationMixer(model) : null;
      populatePoses();
      firstPersonButton.disabled = !cameraBone;
      setStatus(cameraBone ? 'Arms ready' : 'Arms ready · no camera bone', 'ready');
      setView('thirdPerson');
    } catch (error) {
      showError(error);
    }
  }, (event) => {
    if (event.total) setStatus(`Loading arms · ${Math.round((event.loaded / event.total) * 100)}%`);
  }, showError);
}

function showError(error) {
  console.error(error);
  setStatus('Load failed', 'error');
  errorDetail.textContent = error?.message || 'The viewer could not read the model or its textures.';
  errorPanel.hidden = false;
}

function resize() {
  const width = Math.max(1, canvas.clientWidth);
  const height = Math.max(1, canvas.clientHeight);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

firstPersonButton.addEventListener('click', () => setView('firstPerson'));
thirdPersonButton.addEventListener('click', () => setView('thirdPerson'));
resetButton.addEventListener('click', () => viewMode === 'firstPerson' ? updateFirstPersonCamera() : resetOrbit());
turntableButton.addEventListener('click', () => {
  turntable = !turntable;
  turntableButton.setAttribute('aria-pressed', String(turntable));
  controls.autoRotate = turntable;
  controls.autoRotateSpeed = 1.25;
});
poseSelect.addEventListener('change', () => choosePose(poseSelect.value));
retryButton.addEventListener('click', () => window.location.reload());
window.addEventListener('resize', resize);

resize();
loadModel();

renderer.setAnimationLoop(() => {
  const delta = Math.min(clock.getDelta(), 0.05);
  if (mixer) mixer.update(delta);
  if (viewMode === 'firstPerson') updateFirstPersonCamera();
  else controls.update();
  renderer.render(scene, camera);
});
