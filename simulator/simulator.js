import * as THREE from "three";

const DEG = Math.PI / 180;
/** Higher = snappier motion; lower = smoother */
const LERP = 0.11;

let targetPan = 0;
let targetTilt = 0;
let curPan = 0;
let curTilt = 0;
const targetColor = new THREE.Color();
const curColor = new THREE.Color(0x3b82f6);
let targetBright = 0.25;
let curBright = 0.25;

const latest = {
  state: "DISENGAGED",
  behavior_name: "withdrawn",
  variant: "",
  pan_angle: 90,
  tilt_angle: 115,
  brightness: 0.25,
};

const conversationUI = {
  question: "",
  answer: "",
  mode: "",
  memory_found: false,
};

function conversationModeLabel(mode, memoryFound) {
  const m = (mode || "").toUpperCase();
  if (m === "MEMORY_LOCATION_QUERY") {
    return memoryFound ? "memory recall" : "no memory found";
  }
  if (m === "MEMORY_LIST_QUERY" || m === "MEMORY_LAST_SEEN_QUERY") {
    return "memory recall";
  }
  if (m === "GENERAL_QUERY") return "general chat";
  if (m === "LIVE_INFO_QUERY") return "live info";
  if (m === "CLARIFICATION_NEEDED") return "clarification";
  return mode ? mode.replace(/_/g, " ").toLowerCase() : "—";
}

function refreshConversationDom() {
  const qEl = document.getElementById("conv-q");
  const aEl = document.getElementById("conv-a");
  const pill = document.getElementById("conv-mode-pill");
  const badge = document.getElementById("conv-memory-badge");
  if (!qEl || !aEl || !pill || !badge) return;

  const hasTurn = Boolean(conversationUI.question || conversationUI.answer);
  qEl.textContent = hasTurn ? conversationUI.question || "—" : "—";
  aEl.textContent = hasTurn ? conversationUI.answer || "—" : "—";

  const mode = conversationUI.mode || "";
  pill.textContent = hasTurn
    ? conversationModeLabel(mode, conversationUI.memory_found)
    : "—";

  const memModes = [
    "MEMORY_LOCATION_QUERY",
    "MEMORY_LIST_QUERY",
    "MEMORY_LAST_SEEN_QUERY",
  ];
  const isMem = memModes.includes((mode || "").toUpperCase());
  badge.classList.remove("hit", "miss", "is-hidden");
  if (!hasTurn || !isMem) {
    badge.classList.add("is-hidden");
    badge.textContent = "";
    return;
  }
  if (conversationUI.memory_found) {
    badge.textContent = "memory hit";
    badge.classList.add("hit");
  } else {
    badge.textContent = "no memory yet";
    badge.classList.add("miss");
  }
}

function colorFromName(name) {
  const c = new THREE.Color();
  switch ((name || "").toLowerCase()) {
    case "green":
      c.setHex(0x22c55e);
      break;
    case "blue":
      c.setHex(0x3b82f6);
      break;
    case "amber":
      c.setHex(0xf59e0b);
      break;
    case "yellow":
      c.setHex(0xecc94b);
      break;
    case "warm_yellow":
      c.setHex(0xf2d26d);
      break;
    case "pale_yellow":
      c.setHex(0xf4eeb1);
      break;
    case "purple":
      c.setHex(0x7c3aed);
      break;
    case "white":
      c.setHex(0xe2e8f0);
      break;
    default:
      c.setHex(0x94a3b8);
  }
  return c;
}

async function fetchBehavior() {
  try {
    const r = await fetch("latest_behavior.json?t=" + Date.now(), {
      cache: "no-store",
    });
    if (!r.ok) return;
    const data = await r.json();

    latest.state = data.state ?? latest.state;
    latest.behavior_name = data.behavior_name ?? latest.behavior_name;
    latest.variant = data.variant ?? "";
    latest.pan_angle = Number(data.pan_angle);
    latest.tilt_angle = Number(data.tilt_angle);
    latest.brightness = Number(data.brightness);

    targetPan = (latest.pan_angle - 90) * DEG;
    targetTilt = (latest.tilt_angle - 90) * DEG;
    targetColor.copy(colorFromName(data.light_color));
    targetBright = Math.max(0, Math.min(1, latest.brightness));

    const stEl = document.getElementById("ov-state");
    const bhEl = document.getElementById("ov-behavior");
    const ovVar = document.getElementById("ov-variant");
    const micEl = document.getElementById("ov-listening");
    if (stEl) stEl.textContent = latest.state;
    if (bhEl) bhEl.textContent = latest.behavior_name;
    if (ovVar) ovVar.textContent = latest.variant || "—";
    if (micEl) {
      const on = Boolean(data.listening);
      micEl.textContent = on ? "listening" : "idle";
    }
  } catch {
    /* ignore transient fetch errors */
  }
}

async function fetchConversation() {
  try {
    const r = await fetch("latest_conversation.json?t=" + Date.now(), {
      cache: "no-store",
    });
    if (!r.ok) return;
    const data = await r.json();
    conversationUI.question = data.question ?? "";
    conversationUI.answer = data.answer ?? "";
    conversationUI.mode = data.mode ?? "";
    conversationUI.memory_found = Boolean(data.memory_found);
    refreshConversationDom();
  } catch {
    /* file may not exist yet */
  }
}

async function pollTwinFiles() {
  await fetchBehavior();
  await fetchConversation();
}

setInterval(pollTwinFiles, 120);
pollTwinFiles();
refreshConversationDom();

const wrap = document.getElementById("canvas-wrap");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
wrap.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xffffff);

const camera = new THREE.PerspectiveCamera(
  42,
  window.innerWidth / window.innerHeight,
  0.1,
  100
);
camera.position.set(1.15, 0.82, 1.32);
camera.lookAt(0, 0.42, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.52));

const sun = new THREE.DirectionalLight(0xffffff, 0.82);
sun.position.set(-2.2, 4.2, 3.2);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.near = 0.5;
sun.shadow.camera.far = 24;
sun.shadow.camera.left = -4;
sun.shadow.camera.right = 4;
sun.shadow.camera.top = 4;
sun.shadow.camera.bottom = -4;
scene.add(sun);

const groundMat = new THREE.MeshStandardMaterial({
  color: 0xf1f5f9,
  roughness: 0.94,
  metalness: 0,
});
const ground = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), groundMat);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const matBody = new THREE.MeshStandardMaterial({
  color: 0xf8fafc,
  roughness: 0.34,
  metalness: 0.12,
});

const base = new THREE.Mesh(
  new THREE.CylinderGeometry(0.22, 0.26, 0.12, 48),
  matBody
);
base.position.y = 0.06;
base.castShadow = true;
scene.add(base);

const arm = new THREE.Mesh(
  new THREE.CylinderGeometry(0.044, 0.048, 0.54, 28),
  matBody
);
arm.position.y = 0.345;
arm.castShadow = true;
scene.add(arm);

const panGroup = new THREE.Group();
panGroup.position.y = 0.615;
scene.add(panGroup);

const panJoint = new THREE.Mesh(new THREE.SphereGeometry(0.068, 28, 28), matBody);
panJoint.castShadow = true;
panGroup.add(panJoint);

const tiltGroup = new THREE.Group();
panGroup.add(tiltGroup);

const tiltJoint = new THREE.Mesh(
  new THREE.CylinderGeometry(0.048, 0.048, 0.1, 20),
  matBody
);
tiltJoint.rotation.z = Math.PI / 2;
tiltJoint.castShadow = true;
tiltGroup.add(tiltJoint);

const head = new THREE.Mesh(
  new THREE.BoxGeometry(0.21, 0.17, 0.25),
  matBody
);
head.position.set(0, 0, 0.135);
head.castShadow = true;
tiltGroup.add(head);

const glowGeo = new THREE.CircleGeometry(0.052, 56);
const glowMat = new THREE.MeshStandardMaterial({
  color: 0x3b82f6,
  emissive: 0x3b82f6,
  emissiveIntensity: 0.75,
  roughness: 0.35,
  metalness: 0,
});
const glow = new THREE.Mesh(glowGeo, glowMat);
glow.position.set(0, 0, 0.128);
tiltGroup.add(glow);

const lampLight = new THREE.PointLight(0x3b82f6, 1.5, 4, 2);
lampLight.position.set(0, 0, 0.24);
lampLight.castShadow = false;
tiltGroup.add(lampLight);

function animate() {
  requestAnimationFrame(animate);

  curPan += (targetPan - curPan) * LERP;
  curTilt += (targetTilt - curTilt) * LERP;
  curColor.lerp(targetColor, LERP);
  curBright += (targetBright - curBright) * LERP;

  const st = (latest.state || "").toUpperCase();
  const bn = (latest.behavior_name || "").toLowerCase();
  const va = (latest.variant || "").toLowerCase();
  const wt = performance.now() * 0.001;

  let panExtra = 0;
  let tiltExtra = 0;
  let brightMod = 1;

  if (bn === "attention_seek") {
    if (va === "curious_wiggle") {
      panExtra = Math.sin(wt * 3.3) * (5 * DEG);
      brightMod = 1 + 0.07 * Math.sin(wt * 4.4);
    } else if (va === "soft_pulse") {
      brightMod = 1 + 0.12 * Math.sin(wt * 2.4);
    } else if (va === "peek_up") {
      tiltExtra = Math.sin(wt * 2.2) * (5 * DEG) - 3 * DEG;
      brightMod = 1 + 0.08 * Math.sin(wt * 3);
    } else if (va === "side_glance") {
      panExtra = Math.sin(wt * 1.7) * (6 * DEG);
      brightMod = 1 + 0.05 * Math.sin(wt * 2.8);
    } else if (va === "tiny_nod") {
      tiltExtra = Math.sin(wt * 3.8) * (4 * DEG);
      brightMod = 1 + 0.06 * Math.sin(wt * 4);
    }
  }

  if (st === "COOLDOWN" || bn === "cooldown") {
    panExtra = 0;
    tiltExtra = 0;
    brightMod = 0.94;
    brightMod *= 1 + 0.035 * Math.sin(wt * 1.35);
  }

  let answeringPulse = 1;
  if (bn === "answering") {
    answeringPulse = 1 + 0.11 * Math.sin(wt * 5.4);
    tiltExtra += Math.sin(wt * 4.1) * (2.8 * DEG);
  }

  if (st === "ENGAGED" && bn === "attentive") {
    brightMod *= 1 + 0.042 * Math.sin(wt * 1.85);
  }

  if (st === "DISENGAGED" && bn === "withdrawn") {
    brightMod *= 1 + 0.028 * Math.sin(wt * 1.12);
  }

  panGroup.rotation.y = curPan + panExtra;
  tiltGroup.rotation.x = curTilt + tiltExtra;

  glowMat.color.copy(curColor);
  glowMat.emissive.copy(curColor);

  const pulseCombined = answeringPulse * brightMod;

  glowMat.emissiveIntensity = (0.28 + curBright * 1.15) * pulseCombined;

  lampLight.color.copy(curColor);
  lampLight.intensity = (0.35 + curBright * 2.1) * pulseCombined;

  renderer.render(scene, camera);
}
animate();

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
