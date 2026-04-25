let THREE_STATE = null;

function destroy3D() {
  if (!THREE_STATE) return;

  if (THREE_STATE.animId) {
    cancelAnimationFrame(THREE_STATE.animId);
  }

  if (THREE_STATE.renderer) {
    THREE_STATE.renderer.dispose();
  }

  const f = document.getElementById("vz");
  if (f) f.innerHTML = "";

  THREE_STATE = null;
}

function render3D(r) {
  const container = document.getElementById("vz");
  if (!container || !r) return;

  destroy3D();
  container.innerHTML = "";

  const canvasWrap = document.createElement("div");
  canvasWrap.className = "canvas3d";
  container.appendChild(canvasWrap);

  const bounds = getWarehouseBounds(r.warehouse);
  const SCALE = 0.001; // mm -> metres

  const cx = (bounds.x0 + bounds.x1) / 2;
  const cy = (bounds.y0 + bounds.y1) / 2;

  function sx(x) {
    return (x - cx) * SCALE;
  }

  function sz(y) {
    return (y - cy) * SCALE;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070b14);
  scene.fog = new THREE.Fog(0x070b14, 18, 70);

  const width = canvasWrap.clientWidth || container.clientWidth || 900;
  const height = canvasWrap.clientHeight || container.clientHeight || 600;

  const camera = new THREE.PerspectiveCamera(45, width / height, 0.05, 250);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  canvasWrap.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.48));

  const dir = new THREE.DirectionalLight(0xffffff, 0.95);
  dir.position.set(8, 14, 10);
  dir.castShadow = true;
  dir.shadow.mapSize.width = 2048;
  dir.shadow.mapSize.height = 2048;
  scene.add(dir);

  const fill = new THREE.PointLight(0x2a6fff, 0.75, 50);
  fill.position.set(-9, 6, -9);
  scene.add(fill);

  const matFloor = new THREE.MeshStandardMaterial({
    color: 0x141e32,
    roughness: 0.88,
    metalness: 0.03,
    side: THREE.DoubleSide,
  });

  const matLine = new THREE.LineBasicMaterial({
    color: 0x4c78ff,
  });

  const matObstacle = new THREE.MeshStandardMaterial({
    color: 0xff3232,
    roughness: 0.65,
    metalness: 0.05,
    transparent: true,
    opacity: 0.55,
  });

  const matGap = new THREE.MeshStandardMaterial({
    color: 0xf6c343,
    transparent: true,
    opacity: 0.22,
    roughness: 0.8,
    side: THREE.DoubleSide,
    depthWrite: false,
  });

  createWarehouseFloor(scene, r.warehouse, sx, sz, matFloor, matLine);

  const maxDim = Math.max(bounds.x1 - bounds.x0, bounds.y1 - bounds.y0) * SCALE;

  const grid = new THREE.GridHelper(maxDim * 1.15, 40, 0x24314a, 0x111827);
  grid.position.y = 0.003;
  scene.add(grid);

  // Ceiling zones: floor tint + real transparent roof planes
  if (S.showCeiling && r.ceiling && r.ceiling.length) {
    createCeilingZones(scene, r, bounds, sx, sz, SCALE);
    createCeilingRoofPlanes(scene, r, bounds, sx, sz, SCALE);
  }

  // Obstacles
  r.obstacles.forEach((o) => {
    const h = 0.45;
    const geo = new THREE.BoxGeometry(o.w * SCALE, h, o.d * SCALE);
    const mesh = new THREE.Mesh(geo, matObstacle);

    mesh.position.set(
      sx(o.x + o.w / 2),
      h / 2,
      sz(o.y + o.d / 2)
    );

    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
  });

  // Gaps
  if (S.showGaps) {
    r.placed.forEach((b) => {
      if (b.gapCoords && b.gapCoords.length >= 4) {
        const bb = bbox2D(b.gapCoords);
        if (bb.w <= 0 || bb.h <= 0) return;

        const geo = new THREE.PlaneGeometry(bb.w * SCALE, bb.h * SCALE);
        const mesh = new THREE.Mesh(geo, matGap);

        mesh.rotation.x = -Math.PI / 2;
        mesh.position.set(
          sx(bb.x0 + bb.w / 2),
          0.018,
          sz(bb.y0 + bb.h / 2)
        );

        scene.add(mesh);
      }
    });
  }

  // Racks
  r.placed.forEach((b, i) => {
    const rack = createRackBay3D(b, sx, sz, SCALE, i);
    if (rack) scene.add(rack);
  });

  THREE_STATE = {
    scene,
    camera,
    renderer,
    controls,
    animId: null,
    bounds,
    maxDim,
  };

  set3DCamera("iso");

  function animate() {
    if (!THREE_STATE) return;
    THREE_STATE.animId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }

  animate();

  window.onresize = () => {
    if (!THREE_STATE || S.viewMode !== "3d") return;

    const w = canvasWrap.clientWidth || container.clientWidth || 900;
    const h = canvasWrap.clientHeight || container.clientHeight || 600;

    THREE_STATE.camera.aspect = w / h;
    THREE_STATE.camera.updateProjectionMatrix();
    THREE_STATE.renderer.setSize(w, h);
  };
}

function set3DCamera(mode) {
  if (!THREE_STATE) return;

  const { camera, controls, maxDim } = THREE_STATE;
  const d = Math.max(maxDim, 8);

  if (mode === "top") {
    camera.position.set(0, d * 1.65, 0.001);
  } else {
    camera.position.set(d * 0.75, d * 0.75, d * 0.95);
  }

  controls.target.set(0, 0, 0);
  camera.lookAt(0, 0, 0);
  controls.update();
}

function getWarehouseBounds(wh) {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;

  wh.forEach((v) => {
    x0 = Math.min(x0, v.x);
    y0 = Math.min(y0, v.y);
    x1 = Math.max(x1, v.x);
    y1 = Math.max(y1, v.y);
  });

  return {
    x0,
    y0,
    x1,
    y1,
    w: x1 - x0,
    h: y1 - y0,
  };
}

function bbox2D(coords) {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;

  coords.forEach((c) => {
    x0 = Math.min(x0, c[0]);
    y0 = Math.min(y0, c[1]);
    x1 = Math.max(x1, c[0]);
    y1 = Math.max(y1, c[1]);
  });

  return {
    x0,
    y0,
    x1,
    y1,
    w: x1 - x0,
    h: y1 - y0,
  };
}

function createWarehouseFloor(scene, wh, sx, sz, matFloor, matLine) {
  if (!wh || wh.length < 3) return;

  const shape = new THREE.Shape();

  wh.forEach((v, i) => {
    const x = sx(v.x);
    const y = -sz(v.y);

    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });

  shape.closePath();

  const geo = new THREE.ShapeGeometry(shape);
  geo.rotateX(-Math.PI / 2);

  const mesh = new THREE.Mesh(geo, matFloor);
  mesh.receiveShadow = true;
  scene.add(mesh);

  const pts = wh.map((v) => new THREE.Vector3(sx(v.x), 0.035, sz(v.y)));
  pts.push(pts[0].clone());

  const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
  const line = new THREE.Line(lineGeo, matLine);
  scene.add(line);
}

function createCeilingZones(scene, r, bounds, sx, sz, SCALE) {
  const colors = [0x2a6fff, 0x2ed573, 0xffd700, 0xff6b35, 0xa55eea];
  const ceiling = [...r.ceiling].sort((a, b) => a.x - b.x);

  ceiling.forEach((c, i) => {
    const startX = Math.max(c.x, bounds.x0);
    const endX =
      i < ceiling.length - 1
        ? Math.min(ceiling[i + 1].x, bounds.x1)
        : bounds.x1;

    const w = endX - startX;
    if (w <= 0) return;

    // Coloured floor projection of each ceiling zone
    const geo = new THREE.PlaneGeometry(w * SCALE, bounds.h * SCALE);

    const mat = new THREE.MeshStandardMaterial({
      color: colors[i % colors.length],
      transparent: true,
      opacity: 0.09,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(
      sx(startX + w / 2),
      0.01,
      sz(bounds.y0 + bounds.h / 2)
    );

    scene.add(mesh);
  });
}

function createCeilingRoofPlanes(scene, r, bounds, sx, sz, SCALE) {
  const colors = [0x66a3ff, 0x5cff9d, 0xffdf5c, 0xff8a4c, 0xb388ff];
  const ceiling = [...r.ceiling].sort((a, b) => a.x - b.x);

  ceiling.forEach((c, i) => {
    const startX = Math.max(c.x, bounds.x0);
    const endX =
      i < ceiling.length - 1
        ? Math.min(ceiling[i + 1].x, bounds.x1)
        : bounds.x1;

    const w = endX - startX;
    if (w <= 0) return;

    const roofHeight = c.h * SCALE;

    // Transparent roof plane at the actual ceiling height
    const roofGeo = new THREE.PlaneGeometry(w * SCALE, bounds.h * SCALE);

    const roofMat = new THREE.MeshStandardMaterial({
      color: colors[i % colors.length],
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
      depthWrite: false,
      roughness: 0.35,
      metalness: 0.05,
    });

    const roof = new THREE.Mesh(roofGeo, roofMat);
    roof.rotation.x = -Math.PI / 2;
    roof.position.set(
      sx(startX + w / 2),
      roofHeight,
      sz(bounds.y0 + bounds.h / 2)
    );

    scene.add(roof);

    // Roof wireframe outline
    const edges = new THREE.EdgesGeometry(roofGeo);
    const edgeMat = new THREE.LineBasicMaterial({
      color: colors[i % colors.length],
      transparent: true,
      opacity: 0.65,
    });

    const edgeLine = new THREE.LineSegments(edges, edgeMat);
    edgeLine.rotation.x = -Math.PI / 2;
    edgeLine.position.copy(roof.position);
    scene.add(edgeLine);

    // Vertical separators at the beginning of each ceiling zone
    const sepMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.22,
    });

    const xSep = sx(startX);
    const z0 = sz(bounds.y0);
    const z1 = sz(bounds.y1);

    const sepGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(xSep, 0.02, z0),
      new THREE.Vector3(xSep, roofHeight, z0),
      new THREE.Vector3(xSep, roofHeight, z1),
      new THREE.Vector3(xSep, 0.02, z1),
    ]);

    const sepLine = new THREE.Line(sepGeo, sepMat);
    scene.add(sepLine);

    // Floating label
    const label = makeTextSprite(`${Math.round(c.h)} mm`);
    label.position.set(
      sx(startX + w / 2),
      roofHeight + 0.18,
      sz(bounds.y0 + bounds.h * 0.08)
    );
    label.scale.set(0.9, 0.42, 1);
    scene.add(label);
  });
}

function createRackBay3D(b, sx, sz, SCALE, index) {
  if (!b.footprintCoords || b.footprintCoords.length < 4) return null;

  const bb = bbox2D(b.footprintCoords);

  const w = Math.max(bb.w * SCALE, 0.05);
  const d = Math.max(bb.h * SCALE, 0.05);
  const h = Math.max((b.h || 2500) * SCALE, 0.5);

  const group = new THREE.Group();

  group.position.set(
    sx(bb.x0 + bb.w / 2),
    0,
    sz(bb.y0 + bb.h / 2)
  );

  const matPost = new THREE.MeshStandardMaterial({
    color: 0x174a88,
    roughness: 0.45,
    metalness: 0.45,
  });

  const matBeam = new THREE.MeshStandardMaterial({
    color: 0xf97316,
    roughness: 0.45,
    metalness: 0.35,
  });

  const matBrace = new THREE.MeshStandardMaterial({
    color: 0xbfc7d5,
    roughness: 0.35,
    metalness: 0.7,
  });

  const matBox = new THREE.MeshStandardMaterial({
    color: 0xb8874a,
    roughness: 0.82,
    metalness: 0.02,
  });

  const matBase = new THREE.MeshStandardMaterial({
    color: 0x0f172a,
    transparent: true,
    opacity: 0.22,
    roughness: 0.9,
  });

  const postT = Math.min(0.09, Math.max(0.035, Math.min(w, d) * 0.09));
  const beamT = postT * 0.75;

  const base = new THREE.Mesh(new THREE.BoxGeometry(w, 0.025, d), matBase);
  base.position.y = 0.012;
  base.receiveShadow = true;
  group.add(base);

  const postGeo = new THREE.BoxGeometry(postT, h, postT);

  [
    [-w / 2, h / 2, -d / 2],
    [w / 2, h / 2, -d / 2],
    [-w / 2, h / 2, d / 2],
    [w / 2, h / 2, d / 2],
  ].forEach((p) => {
    const m = new THREE.Mesh(postGeo, matPost);
    m.position.set(p[0], p[1], p[2]);
    m.castShadow = true;
    m.receiveShadow = true;
    group.add(m);
  });

  const levels = [0.18, 0.5, 0.82].map((v) => Math.max(0.18, h * v));

  levels.forEach((y) => {
    const beamFront = new THREE.Mesh(
      new THREE.BoxGeometry(w + postT * 1.6, beamT, beamT),
      matBeam
    );

    beamFront.position.set(0, y, -d / 2);
    beamFront.castShadow = true;
    group.add(beamFront);

    const beamBack = beamFront.clone();
    beamBack.position.z = d / 2;
    group.add(beamBack);

    const sideA = new THREE.Mesh(
      new THREE.BoxGeometry(beamT, beamT, d + postT * 1.6),
      matBeam
    );

    sideA.position.set(-w / 2, y, 0);
    sideA.castShadow = true;
    group.add(sideA);

    const sideB = sideA.clone();
    sideB.position.x = w / 2;
    group.add(sideB);
  });

  addBrace(
    group,
    new THREE.Vector3(-w / 2, 0.15 * h, -d / 2),
    new THREE.Vector3(-w / 2, 0.82 * h, d / 2),
    postT * 0.22,
    matBrace
  );

  addBrace(
    group,
    new THREE.Vector3(w / 2, 0.15 * h, -d / 2),
    new THREE.Vector3(w / 2, 0.82 * h, d / 2),
    postT * 0.22,
    matBrace
  );

  const boxCount = Math.min(6, Math.max(1, Math.round((b.nLoads || 2) / 2)));
  const cols = Math.min(3, boxCount);
  const rows = Math.ceil(boxCount / cols);

  const boxW = Math.max(0.12, (w * 0.7) / cols);
  const boxD = Math.max(0.12, (d * 0.55) / rows);
  const boxH = Math.min(0.55, h * 0.16);

  let k = 0;

  for (let rz = 0; rz < rows; rz++) {
    for (let cx = 0; cx < cols; cx++) {
      if (k >= boxCount) break;

      const bx = -w * 0.28 + cx * boxW * 1.15;
      const bz = -d * 0.18 + rz * boxD * 1.2;
      const by = levels[0] + boxH / 2 + 0.04;

      const cargo = new THREE.Mesh(
        new THREE.BoxGeometry(boxW, boxH, boxD),
        matBox
      );

      cargo.position.set(bx, by, bz);
      cargo.castShadow = true;
      cargo.receiveShadow = true;
      group.add(cargo);

      k++;
    }
  }

  const label = makeTextSprite(String(b.id));
  label.position.set(0, h + 0.2, 0);
  group.add(label);

  return group;
}

function addBrace(group, p1, p2, radius, material) {
  const dir = new THREE.Vector3().subVectors(p2, p1);
  const len = dir.length();

  const geo = new THREE.CylinderGeometry(radius, radius, len, 8);
  const mesh = new THREE.Mesh(geo, material);

  mesh.position.copy(new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5));

  const quat = new THREE.Quaternion();
  quat.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  mesh.quaternion.copy(quat);

  mesh.castShadow = true;
  group.add(mesh);
}

function makeTextSprite(text) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 128;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "rgba(0,0,0,0.45)";
  roundRect(ctx, 48, 24, 160, 80, 18);
  ctx.fill();

  ctx.font = "bold 54px Outfit, Arial";
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 66);

  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;

  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(0.65, 0.32, 1);

  return sprite;
}

function roundRect(ctx, x, y, w, h, r) {
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