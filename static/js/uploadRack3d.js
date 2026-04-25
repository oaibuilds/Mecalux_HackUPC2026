/* static/js/uploadRack3d.js
   Clean 3D animated input rack for upload screen
*/

let UPLOAD_RACK_3D = {
  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  container: null,
  animationId: null,
  resizeHandler: null,
  boxes: [],
  initialized: false
};

function destroyUploadRack3D() {
  if (UPLOAD_RACK_3D.animationId) {
    cancelAnimationFrame(UPLOAD_RACK_3D.animationId);
  }

  if (UPLOAD_RACK_3D.controls) {
    UPLOAD_RACK_3D.controls.dispose();
  }

  if (UPLOAD_RACK_3D.scene) {
    UPLOAD_RACK_3D.scene.traverse(obj => {
      if (obj.geometry) obj.geometry.dispose();

      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach(m => {
            if (m.map) m.map.dispose();
            m.dispose();
          });
        } else {
          if (obj.material.map) obj.material.map.dispose();
          obj.material.dispose();
        }
      }
    });
  }

  if (UPLOAD_RACK_3D.renderer) {
    UPLOAD_RACK_3D.renderer.dispose();
    try {
      UPLOAD_RACK_3D.renderer.forceContextLoss();
    } catch (e) {}
  }

  if (UPLOAD_RACK_3D.resizeHandler) {
    window.removeEventListener("resize", UPLOAD_RACK_3D.resizeHandler);
  }

  if (UPLOAD_RACK_3D.container) {
    UPLOAD_RACK_3D.container.innerHTML = "";
  }

  UPLOAD_RACK_3D = {
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    container: null,
    animationId: null,
    resizeHandler: null,
    boxes: [],
    initialized: false
  };
}

function clampUpload(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function roundRectUpload(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function createUploadMaterials() {
  return {
    floor: new THREE.MeshStandardMaterial({
      color: 0x0b1424,
      roughness: 0.92,
      metalness: 0.18
    }),

    floorGlow: new THREE.MeshBasicMaterial({
      color: 0x244ca3,
      transparent: true,
      opacity: 0.08
    }),

    post: new THREE.MeshStandardMaterial({
      color: 0x2459cf,
      roughness: 0.34,
      metalness: 0.62,
      emissive: 0x102a6f,
      emissiveIntensity: 0.25
    }),

    beam: new THREE.MeshStandardMaterial({
      color: 0xe98a3c,
      roughness: 0.38,
      metalness: 0.42,
      emissive: 0x5a2c10,
      emissiveIntensity: 0.16
    }),

    brace: new THREE.MeshStandardMaterial({
      color: 0xb8c7e6,
      roughness: 0.42,
      metalness: 0.62
    }),

    shelf: new THREE.MeshStandardMaterial({
      color: 0xd8b982,
      roughness: 0.70,
      metalness: 0.18,
      transparent: true,
      opacity: 0.34,
      side: THREE.DoubleSide
    }),

    box: new THREE.MeshStandardMaterial({
      color: 0x79a4ff,
      roughness: 0.42,
      metalness: 0.22,
      emissive: 0x143985,
      emissiveIntensity: 0.18
    }),

    boxTop: new THREE.MeshStandardMaterial({
      color: 0x9cf3ff,
      roughness: 0.36,
      metalness: 0.20,
      emissive: 0x1f6d89,
      emissiveIntensity: 0.16
    }),

    boxSide: new THREE.MeshStandardMaterial({
      color: 0x3f78d9,
      roughness: 0.48,
      metalness: 0.18
    }),

    labelDark: new THREE.MeshBasicMaterial({
      color: 0x07111d,
      transparent: true,
      opacity: 0.88
    }),

    line: new THREE.LineBasicMaterial({
      color: 0x6d95ff,
      transparent: true,
      opacity: 0.25
    })
  };
}

function cylinderBetweenUpload(a, b, radius, material) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const len = dir.length();

  const geo = new THREE.CylinderGeometry(radius, radius, len, 10);
  const mesh = new THREE.Mesh(geo, material);

  mesh.position.copy(new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5));

  mesh.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    dir.clone().normalize()
  );

  return mesh;
}

function makeUploadLabelSprite(title, subtitle) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 180;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const bg = ctx.createLinearGradient(0, 0, 512, 180);
  bg.addColorStop(0, "rgba(40,70,165,0.95)");
  bg.addColorStop(1, "rgba(70,190,230,0.92)");

  roundRectUpload(ctx, 18, 24, 476, 132, 34);
  ctx.fillStyle = bg;
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.42)";
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.fillStyle = "#ffffff";
  ctx.font = "900 34px Outfit, Arial";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(title, 54, 78);

  ctx.fillStyle = "rgba(255,255,255,0.68)";
  ctx.font = "700 22px JetBrains Mono, monospace";
  ctx.fillText(subtitle, 54, 118);

  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;

  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    depthWrite: false,
    depthTest: true
  });

  const sprite = new THREE.Sprite(mat);

  // Important: small label, not huge.
  sprite.scale.set(1.95, 0.68, 1);

  return sprite;
}

function addUploadFloor(scene, mats) {
  const floor = new THREE.Mesh(
    new THREE.BoxGeometry(8.8, 0.05, 5.8),
    mats.floor
  );

  floor.position.y = -0.04;
  floor.receiveShadow = true;
  scene.add(floor);

  const glow = new THREE.Mesh(
    new THREE.PlaneGeometry(7.8, 4.9),
    mats.floorGlow
  );

  glow.rotation.x = -Math.PI / 2;
  glow.position.y = 0.012;
  scene.add(glow);

  const grid = new THREE.GridHelper(8.8, 22, 0x365da8, 0x20304d);
  grid.material.transparent = true;
  grid.material.opacity = 0.22;
  grid.position.y = 0.018;
  scene.add(grid);
}

function addUploadRackStructure(scene, mats) {
  const rack = new THREE.Group();

  const width = 5.3;
  const depth = 2.05;
  const height = 4.75;

  const postW = 0.15;
  const beamH = 0.12;

  const xL = -width / 2;
  const xR = width / 2;
  const zF = depth / 2;
  const zB = -depth / 2;

  // Lower to upper shelf levels.
  const levelYs = [0.72, 1.66, 2.60, 3.54];

  const postGeo = new THREE.BoxGeometry(postW, height, postW);

  [
    [xL, height / 2, zF],
    [xR, height / 2, zF],
    [xL, height / 2, zB],
    [xR, height / 2, zB]
  ].forEach(([x, y, z]) => {
    const post = new THREE.Mesh(postGeo, mats.post);
    post.position.set(x, y, z);
    post.castShadow = true;
    post.receiveShadow = true;
    rack.add(post);
  });

  const beamGeoW = new THREE.BoxGeometry(width + 0.36, beamH, beamH);
  const beamGeoD = new THREE.BoxGeometry(beamH, beamH, depth + 0.32);

  levelYs.forEach(y => {
    [zF, zB].forEach(z => {
      const beam = new THREE.Mesh(beamGeoW, mats.beam);
      beam.position.set(0, y, z);
      beam.castShadow = true;
      beam.receiveShadow = true;
      rack.add(beam);
    });

    [xL, xR].forEach(x => {
      const beam = new THREE.Mesh(beamGeoD, mats.beam);
      beam.position.set(x, y, 0);
      beam.castShadow = true;
      beam.receiveShadow = true;
      rack.add(beam);
    });

    const shelf = new THREE.Mesh(
      new THREE.BoxGeometry(width * 0.86, 0.035, depth * 0.74),
      mats.shelf
    );

    shelf.position.set(0, y - 0.10, 0);
    shelf.receiveShadow = true;
    rack.add(shelf);
  });

  // Top beams.
  [zF, zB].forEach(z => {
    const beam = new THREE.Mesh(beamGeoW, mats.beam);
    beam.position.set(0, height - 0.12, z);
    beam.castShadow = true;
    rack.add(beam);
  });

  [xL, xR].forEach(x => {
    const beam = new THREE.Mesh(beamGeoD, mats.beam);
    beam.position.set(x, height - 0.12, 0);
    beam.castShadow = true;
    rack.add(beam);
  });

  // Back braces only, so they do not cover the boxes too much.
  [
    [new THREE.Vector3(xL, 0.42, zB), new THREE.Vector3(xR, 3.75, zB)],
    [new THREE.Vector3(xR, 0.42, zB), new THREE.Vector3(xL, 3.75, zB)]
  ].forEach(pair => {
    const brace = cylinderBetweenUpload(pair[0], pair[1], 0.025, mats.brace);
    brace.castShadow = true;
    rack.add(brace);
  });

  // Side braces.
  [
    [new THREE.Vector3(xL, 0.42, zF), new THREE.Vector3(xL, 3.75, zB)],
    [new THREE.Vector3(xR, 0.42, zF), new THREE.Vector3(xR, 3.75, zB)]
  ].forEach(pair => {
    const brace = cylinderBetweenUpload(pair[0], pair[1], 0.022, mats.brace);
    brace.castShadow = true;
    rack.add(brace);
  });

  rack.position.y = 0.03;

  scene.add(rack);

  return {
    rack,
    levelYs,
    width,
    depth,
    height
  };
}

function createInputRackBox(step, index, mats) {
  const group = new THREE.Group();

  // Smaller boxes. This is what fixes the visual overlap.
  const w = 2.95;
  const h = 0.42;
  const d = 0.78;

  const body = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    mats.box
  );

  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  const top = new THREE.Mesh(
    new THREE.BoxGeometry(w, 0.045, d),
    mats.boxTop
  );

  top.position.y = h / 2 + 0.026;
  group.add(top);

  const side = new THREE.Mesh(
    new THREE.BoxGeometry(0.055, h, d),
    mats.boxSide
  );

  side.position.x = w / 2 + 0.028;
  group.add(side);

  const label = makeUploadLabelSprite(step.name, step.file);

  // Put label slightly in front and above the box, not crossing the rack.
  label.position.set(0, h / 2 + 0.43, d / 2 + 0.16);
  group.add(label);

  group.userData.finalPosition = new THREE.Vector3(0, 0, 0);
  group.userData.startPosition = new THREE.Vector3(6.4, 3.2, 3.2);
  group.userData.progress = 0;
  group.userData.targetProgress = 0;
  group.userData.index = index;

  group.visible = false;

  return group;
}

function updateUploadRackBoxes(files, steps) {
  if (!UPLOAD_RACK_3D.boxes) return;

  steps.forEach((step, i) => {
    const loaded = files[step.k] !== null;
    const box = UPLOAD_RACK_3D.boxes[i];

    if (!box) return;

    box.userData.targetProgress = loaded ? 1 : 0;

    if (loaded) {
      box.visible = true;
    }
  });
}

function renderUploadRack3D(containerId, files, steps) {
  const container = document.getElementById(containerId);
  if (!container) return;

  destroyUploadRack3D();

  const width = container.clientWidth || 720;
  const height = container.clientHeight || 520;

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true
  });

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);
  renderer.setClearColor(0x000000, 0);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  container.innerHTML = "";
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x07111d, 0.032);

  const camera = new THREE.PerspectiveCamera(
    39,
    width / Math.max(1, height),
    0.1,
    100
  );

  // Camera farther and more centered.
  camera.position.set(6.9, 4.5, 6.3);
  camera.lookAt(0, 2.25, 0);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.055;
  controls.enablePan = false;
  controls.enableZoom = true;
  controls.minDistance = 7.5;
  controls.maxDistance = 14.5;
  controls.minPolarAngle = 0.48;
  controls.maxPolarAngle = 1.30;
  controls.target.set(0, 2.2, 0);

  const ambient = new THREE.AmbientLight(0xffffff, 0.68);
  scene.add(ambient);

  const hemi = new THREE.HemisphereLight(0x8ab8ff, 0x0b111b, 0.72);
  scene.add(hemi);

  const key = new THREE.DirectionalLight(0xffffff, 1.05);
  key.position.set(7, 10, 7);
  key.castShadow = true;
  key.shadow.mapSize.width = 1024;
  key.shadow.mapSize.height = 1024;
  scene.add(key);

  const rim = new THREE.PointLight(0x5b8cff, 1.9, 18, 2);
  rim.position.set(-3.5, 5.2, -4.2);
  scene.add(rim);

  const orange = new THREE.PointLight(0xff8a3d, 1.15, 14, 2);
  orange.position.set(4.2, 2.8, 4);
  scene.add(orange);

  const mats = createUploadMaterials();

  addUploadFloor(scene, mats);

  const rackInfo = addUploadRackStructure(scene, mats);

  const boxes = [];

  // Put boxes one per shelf, clearly separated.
  const finalPositions = [
    new THREE.Vector3(0, rackInfo.levelYs[0] + 0.18, 0.08),
    new THREE.Vector3(0, rackInfo.levelYs[1] + 0.18, 0.08),
    new THREE.Vector3(0, rackInfo.levelYs[2] + 0.18, 0.08),
    new THREE.Vector3(0, rackInfo.levelYs[3] + 0.18, 0.08)
  ];

  steps.forEach((step, i) => {
    const box = createInputRackBox(step, i, mats);

    box.userData.finalPosition = finalPositions[i];

    // Start outside rack, but not too aggressively.
    box.userData.startPosition = new THREE.Vector3(
      5.9,
      finalPositions[i].y + 1.05,
      2.65
    );

    box.position.copy(box.userData.startPosition);
    box.rotation.y = -0.42;
    box.rotation.z = 0.08;

    scene.add(box);
    boxes.push(box);
  });

  UPLOAD_RACK_3D = {
    renderer,
    scene,
    camera,
    controls,
    container,
    animationId: null,
    resizeHandler: null,
    boxes,
    initialized: true
  };

  updateUploadRackBoxes(files, steps);

  function animate() {
    UPLOAD_RACK_3D.animationId = requestAnimationFrame(animate);

    const time = performance.now() * 0.001;

    boxes.forEach((box, i) => {
      const target = box.userData.targetProgress;
      const current = box.userData.progress;
      const next = current + (target - current) * 0.08;

      box.userData.progress = next;

      if (target === 0 && next < 0.015) {
        box.visible = false;
      }

      if (!box.visible) return;

      const e = 1 - Math.pow(1 - clampUpload(next, 0, 1), 3);

      const start = box.userData.startPosition;
      const end = box.userData.finalPosition;

      const arc = Math.sin(e * Math.PI) * 0.75;

      box.position.set(
        start.x + (end.x - start.x) * e,
        start.y + (end.y - start.y) * e + arc,
        start.z + (end.z - start.z) * e
      );

      box.rotation.y = -0.42 + e * 0.42;
      box.rotation.z = (1 - e) * 0.08;

      box.scale.setScalar(0.90 + e * 0.10);

      if (e > 0.985) {
        box.position.y += Math.sin(time * 2.0 + i * 0.6) * 0.006;
      }
    });

    if (rackInfo.rack) {
      rackInfo.rack.rotation.y = Math.sin(time * 0.28) * 0.01;
    }

    controls.update();
    renderer.render(scene, camera);
  }

  animate();

  UPLOAD_RACK_3D.resizeHandler = () => {
    if (!UPLOAD_RACK_3D.renderer || !UPLOAD_RACK_3D.camera || !UPLOAD_RACK_3D.container) return;

    const w = UPLOAD_RACK_3D.container.clientWidth || 720;
    const h = UPLOAD_RACK_3D.container.clientHeight || 520;

    UPLOAD_RACK_3D.renderer.setSize(w, h);
    UPLOAD_RACK_3D.camera.aspect = w / Math.max(1, h);
    UPLOAD_RACK_3D.camera.updateProjectionMatrix();
  };

  window.addEventListener("resize", UPLOAD_RACK_3D.resizeHandler);
}

window.renderUploadRack3D = renderUploadRack3D;
window.destroyUploadRack3D = destroyUploadRack3D;