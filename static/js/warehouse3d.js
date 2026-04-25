/* warehouse3d.js — 3D warehouse render corregido
 *
 * Cambios:
 * - Ceiling y gaps alineados con racks.
 * - Auto-rotation controlada por S.autoRotate3D.
 * - Racks estilo Mecalux: pilares azules, vigas naranjas, diagonales metálicas.
 * - Sin grid extra fuera del warehouse.
 */

if (typeof G3D === "undefined") {
  var G3D = {};
}

(function () {
  function destroy3D() {
    if (G3D.animationId) {
      cancelAnimationFrame(G3D.animationId);
      G3D.animationId = null;
    }

    if (G3D.resizeObserver) {
      G3D.resizeObserver.disconnect();
      G3D.resizeObserver = null;
    }

    if (G3D.controls && typeof G3D.controls.dispose === "function") {
      G3D.controls.dispose();
    }

    if (G3D.scene) {
      G3D.scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();

        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose && m.dispose());
          } else {
            obj.material.dispose && obj.material.dispose();
          }
        }
      });
    }

    if (G3D.renderer) {
      G3D.renderer.dispose();
      if (G3D.renderer.domElement && G3D.renderer.domElement.parentNode) {
        G3D.renderer.domElement.parentNode.removeChild(G3D.renderer.domElement);
      }
    }

    const container = document.getElementById("vz");
    if (container) container.innerHTML = "";

    G3D.camera = null;
    G3D.controls = null;
    G3D.renderer = null;
    G3D.scene = null;
    G3D.rackGroups = [];
  }

  function set3DCamera(mode) {
    if (!G3D.camera || !G3D.controls) {
      if (typeof S !== "undefined" && S.viewMode !== "3d") {
        S.viewMode = "3d";
        if (typeof render === "function") {
          render();
          setTimeout(() => set3DCamera(mode), 100);
        }
      }
      return;
    }

    const m = G3D.maxDim || 10;

    if (mode === "top") {
      G3D.camera.position.set(0, m * 1.75, 0.001);
      G3D.controls.target.set(0, 0, 0);
    } else if (mode === "hero") {
      G3D.camera.position.set(m * 0.95, m * 0.55, m * 1.1);
      G3D.controls.target.set(0, 0.28, 0);
    } else {
      G3D.camera.position.set(m * 0.85, m * 0.7, m * 1.05);
      G3D.controls.target.set(0, 0.25, 0);
    }

    G3D.camera.lookAt(G3D.controls.target);
    G3D.controls.update();
  }

  function render3D(r) {
    const container = document.getElementById("vz");
    if (!container || !r) return;

    destroy3D();

    if (!window.THREE) {
      container.innerHTML =
        '<div style="padding:32px;color:#ff6b35">Three.js could not be loaded.</div>';
      return;
    }

    container.innerHTML = "";

    const showGaps = typeof S !== "undefined" ? S.showGaps : true;
    const showCeiling = typeof S !== "undefined" ? S.showCeiling : true;
    const autoRotate3D = typeof S !== "undefined" ? !!S.autoRotate3D : false;

    const wh = r.warehouse || [];

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

    if (!isFinite(x0)) {
      container.innerHTML =
        '<div style="padding:32px;color:#ff6b35">No warehouse geometry</div>';
      return;
    }

    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    const W = x1 - x0;
    const D = y1 - y0;

    const scale = 1 / 1000;
    const tx = (x) => (x - cx) * scale;
    const tz = (y) => (y - cy) * scale;

    const scene = new THREE.Scene();
    scene.background = null;
    scene.fog = new THREE.Fog(
      0x0a0e17,
      Math.max(W, D) * scale * 1.1,
      Math.max(W, D) * scale * 2.6
    );

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 600;

    const maxDim = Math.max(W, D) * scale;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(maxDim * 0.85, maxDim * 0.7, maxDim * 1.05);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position:absolute; top:16px; left:16px;
      padding:10px 14px; border-radius:12px;
      background:rgba(0,0,0,0.45);
      border:1px solid rgba(255,255,255,0.08);
      backdrop-filter:blur(10px);
      font-size:12px; color:rgba(255,255,255,0.82);
      pointer-events:none; line-height:1.45;
    `;
    overlay.innerHTML = `
      <b style="color:white">3D Warehouse</b><br>
      ${r.stats.totalBays} bays · ${r.stats.totalLoads} loads · Q ${r.stats.score.toFixed(2)}
    `;
    container.appendChild(overlay);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0.25, 0);
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = maxDim * 0.35;
    controls.maxDistance = maxDim * 2.2;
    controls.rotateSpeed = 0.45;
    controls.zoomSpeed = 0.75;

    scene.add(new THREE.HemisphereLight(0xfff4e0, 0x1a1200, 0.75));

    const key = new THREE.DirectionalLight(0xffffff, 0.95);
    key.position.set(maxDim * 0.6, maxDim * 1.2, maxDim * 0.4);
    key.castShadow = true;
    key.shadow.mapSize.width = 2048;
    key.shadow.mapSize.height = 2048;
    scene.add(key);

    const fill = new THREE.DirectionalLight(0xc8d8ff, 0.45);
    fill.position.set(-maxDim * 0.8, maxDim * 0.5, -maxDim * 0.6);
    scene.add(fill);

    const ground = new THREE.PointLight(0xffa040, 0.55, maxDim * 2.5);
    ground.position.set(0, 0.3, 0);
    scene.add(ground);

    const matFloor = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 1,
      metalness: 0,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });

    const matObstacle = new THREE.MeshStandardMaterial({
      color: 0x7a1515,
      roughness: 0.75,
      metalness: 0.05,
      transparent: true,
      opacity: 0.82,
    });

    const matGap = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const matGapEdge = new THREE.LineBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.85,
    });

    const MECALUX_BLUE = 0x143b78;
    const MECALUX_ORANGE = 0xe96f1f;
    const METAL = 0xb8c2d6;

    const matColumn = new THREE.MeshStandardMaterial({
      color: MECALUX_BLUE,
      roughness: 0.35,
      metalness: 0.65,
    });

    const matBeam = new THREE.MeshStandardMaterial({
      color: MECALUX_ORANGE,
      roughness: 0.38,
      metalness: 0.45,
    });

    const matBrace = new THREE.MeshStandardMaterial({
      color: METAL,
      roughness: 0.42,
      metalness: 0.7,
    });

    const matShelf = new THREE.MeshStandardMaterial({
      color: 0x1d2f4a,
      roughness: 0.65,
      metalness: 0.35,
      transparent: true,
      opacity: 0.42,
    });

    const matPallet = new THREE.MeshStandardMaterial({
      color: 0xa9703a,
      roughness: 0.9,
      metalness: 0.03,
    });

    const boxColors = [
      0x9ee493,
      0x8fd3e8,
      0xd4a96a,
      0xb7e4ff,
      0xa7f3d0,
      0xfecaca,
    ];

    function shapeFromWarehouse() {
      const shape = new THREE.Shape();

      wh.forEach((v, i) => {
        const px = tx(v.x);
        const pz = -tz(v.y);

        if (i === 0) shape.moveTo(px, pz);
        else shape.lineTo(px, pz);
      });

      shape.closePath();
      return shape;
    }

    const floorGeo = new THREE.ShapeGeometry(shapeFromWarehouse());
    floorGeo.rotateX(-Math.PI / 2);

    const floor = new THREE.Mesh(floorGeo, matFloor);
    floor.receiveShadow = true;
    scene.add(floor);

    const outlinePts = wh.concat([wh[0]]).map(
      (v) => new THREE.Vector3(tx(v.x), 0.035, tz(v.y))
    );

    scene.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(outlinePts),
        new THREE.LineBasicMaterial({ color: 0x2a6fff })
      )
    );

    function addBox(x, y, z, w, h, d, mat, parent) {
      parent = parent || scene;

      const geo = new THREE.BoxGeometry(
        Math.max(w, 0.01),
        Math.max(h, 0.01),
        Math.max(d, 0.01)
      );

      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      parent.add(mesh);
      return mesh;
    }

    function cylinderBetween(a, b, radius, material, parent) {
      const dir = new THREE.Vector3().subVectors(b, a);
      const len = dir.length();

      const geo = new THREE.CylinderGeometry(radius, radius, len, 10);
      const mesh = new THREE.Mesh(geo, material);

      mesh.position.copy(new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5));
      mesh.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        dir.clone().normalize()
      );

      mesh.castShadow = true;
      mesh.receiveShadow = true;

      parent.add(mesh);
      return mesh;
    }

    function bboxCoords(coords) {
      let ax = Infinity;
      let ay = Infinity;
      let bx = -Infinity;
      let by = -Infinity;

      coords.forEach((c) => {
        ax = Math.min(ax, c[0]);
        ay = Math.min(ay, c[1]);
        bx = Math.max(bx, c[0]);
        by = Math.max(by, c[1]);
      });

      return {
        x0: ax,
        y0: ay,
        x1: bx,
        y1: by,
        w: bx - ax,
        d: by - ay,
      };
    }

    function addGapPoly(coords) {
      if (!coords || coords.length < 3) return;

      const sh = new THREE.Shape();

      coords.forEach((c, i) => {
        const px = tx(c[0]);
        const pz = -tz(c[1]);

        if (i === 0) sh.moveTo(px, pz);
        else sh.lineTo(px, pz);
      });

      sh.closePath();

      const geo = new THREE.ShapeGeometry(sh);
      geo.rotateX(-Math.PI / 2);

      const mesh = new THREE.Mesh(geo, matGap);
      mesh.position.y = 0.045;
      mesh.renderOrder = 4;
      scene.add(mesh);

      const pts = coords.concat([coords[0]]).map(
        (c) => new THREE.Vector3(tx(c[0]), 0.055, tz(c[1]))
      );

      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        matGapEdge
      );

      line.renderOrder = 5;
      scene.add(line);
    }

    function addRack(b, index) {
      const bb = bboxCoords(
        b.footprintCoords || [
          [b.x, b.y],
          [b.x + b.w, b.y + b.d],
        ]
      );

      const xC = tx((bb.x0 + bb.x1) / 2);
      const zC = tz((bb.y0 + bb.y1) / 2);

      const w = Math.max(bb.w * scale, 0.05);
      const d = Math.max(bb.d * scale, 0.05);
      const h = Math.max((b.h || 2000) * scale, 0.35);

      const beam = Math.max(Math.min(w, d) * 0.055, 0.045);
      const levels = Math.max(3, Math.min(5, Math.round(h / 0.75)));

      const group = new THREE.Group();
      scene.add(group);

      function localBox(lx, ly, lz, bw, bh, bd, mat) {
        return addBox(xC + lx, ly, zC + lz, bw, bh, bd, mat, group);
      }

      const xs = [-w / 2 + beam / 2, w / 2 - beam / 2];
      const zs = [-d / 2 + beam / 2, d / 2 - beam / 2];

      xs.forEach((px) => {
        zs.forEach((pz) => {
          localBox(px, h / 2, pz, beam, h, beam, matColumn);
        });
      });

      for (let i = 0; i <= levels; i++) {
        const yy = Math.max(beam / 2, (h / levels) * i);

        localBox(0, yy, -d / 2 + beam / 2, w, beam, beam, matBeam);
        localBox(0, yy, d / 2 - beam / 2, w, beam, beam, matBeam);
        localBox(-w / 2 + beam / 2, yy, 0, beam, beam, d, matBeam);
        localBox(w / 2 - beam / 2, yy, 0, beam, beam, d, matBeam);

        if (i > 0 && i < levels) {
          localBox(0, yy - beam * 0.35, 0, w * 0.9, beam * 0.35, d * 0.82, matShelf);
        }
      }

      const braceRadius = Math.max(beam * 0.22, 0.012);

      [
        [
          new THREE.Vector3(xC - w / 2 + beam / 2, 0.15, zC - d / 2 + beam / 2),
          new THREE.Vector3(xC + w / 2 - beam / 2, h * 0.92, zC - d / 2 + beam / 2),
        ],
        [
          new THREE.Vector3(xC + w / 2 - beam / 2, 0.15, zC - d / 2 + beam / 2),
          new THREE.Vector3(xC - w / 2 + beam / 2, h * 0.92, zC - d / 2 + beam / 2),
        ],
        [
          new THREE.Vector3(xC - w / 2 + beam / 2, 0.15, zC + d / 2 - beam / 2),
          new THREE.Vector3(xC + w / 2 - beam / 2, h * 0.92, zC + d / 2 - beam / 2),
        ],
        [
          new THREE.Vector3(xC + w / 2 - beam / 2, 0.15, zC + d / 2 - beam / 2),
          new THREE.Vector3(xC - w / 2 + beam / 2, h * 0.92, zC + d / 2 - beam / 2),
        ],
      ].forEach(([a, b]) => {
        cylinderBetween(a, b, braceRadius, matBrace, group);
      });

      for (let i = 1; i < levels; i++) {
        const yy = (h / levels) * i + beam * 1.7;
        const palletH = Math.min(0.14, (h / levels) * 0.2);
        const count = w > d ? 2 : 1;

        for (let j = 0; j < count; j++) {
          const off = count === 2 ? (j === 0 ? -w * 0.23 : w * 0.23) : 0;
          const palletW = w * (count === 2 ? 0.34 : 0.62);
          const palletD = d * 0.55;

          localBox(off, yy, 0, palletW, palletH, palletD, matPallet);

          const boxColor = boxColors[(index + i + j + b.id) % boxColors.length];
          const matBox = new THREE.MeshStandardMaterial({
            color: boxColor,
            roughness: 0.82,
            metalness: 0.04,
          });


          const boxW = palletW * 0.82;
          const boxD = palletD * 0.78;
          const boxH = Math.min((h / levels) * 0.48, 0.38);

          localBox(off, yy + palletH / 2 + boxH / 2, 0, boxW, boxH, boxD, matBox);
          
        }
      }

      const matBase = new THREE.MeshBasicMaterial({
        color: MECALUX_BLUE,
        transparent: true,
        opacity: 0.1,
        depthWrite: false,
      });

      localBox(0, 0.012, 0, w, 0.018, d, matBase);

      const footPts = [
        new THREE.Vector3(xC - w / 2, 0.022, zC - d / 2),
        new THREE.Vector3(xC + w / 2, 0.022, zC - d / 2),
        new THREE.Vector3(xC + w / 2, 0.022, zC + d / 2),
        new THREE.Vector3(xC - w / 2, 0.022, zC + d / 2),
        new THREE.Vector3(xC - w / 2, 0.022, zC - d / 2),
      ];

      const footLine = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(footPts),
        new THREE.LineBasicMaterial({
          color: MECALUX_ORANGE,
          transparent: true,
          opacity: 0.8,
        })
      );

      footLine.renderOrder = 6;
      scene.add(footLine);

      group.userData.order = index;
      G3D.rackGroups.push(group);
      return group;
    }

if (showCeiling && r.ceiling && r.ceiling.length) {
  const zones = [...r.ceiling].sort((a, b) => a.x - b.x);
  const ceilingColors = [0x2563eb, 0x16a34a, 0xd97706, 0xdc2626, 0x7c3aed];

  function clipPolygonByX(poly, minX, maxX) {
    function clipLeft(points, limit) {
      const out = [];
      for (let i = 0; i < points.length; i++) {
        const a = points[i];
        const b = points[(i + 1) % points.length];
        const ain = a.x >= limit;
        const bin = b.x >= limit;

        if (ain && bin) {
          out.push(b);
        } else if (ain && !bin) {
          const t = (limit - a.x) / (b.x - a.x);
          out.push({ x: limit, y: a.y + t * (b.y - a.y) });
        } else if (!ain && bin) {
          const t = (limit - a.x) / (b.x - a.x);
          out.push({ x: limit, y: a.y + t * (b.y - a.y) });
          out.push(b);
        }
      }
      return out;
    }

    function clipRight(points, limit) {
      const out = [];
      for (let i = 0; i < points.length; i++) {
        const a = points[i];
        const b = points[(i + 1) % points.length];
        const ain = a.x <= limit;
        const bin = b.x <= limit;

        if (ain && bin) {
          out.push(b);
        } else if (ain && !bin) {
          const t = (limit - a.x) / (b.x - a.x);
          out.push({ x: limit, y: a.y + t * (b.y - a.y) });
        } else if (!ain && bin) {
          const t = (limit - a.x) / (b.x - a.x);
          out.push({ x: limit, y: a.y + t * (b.y - a.y) });
          out.push(b);
        }
      }
      return out;
    }

    let result = poly.map(p => ({ x: p.x, y: p.y }));
    result = clipLeft(result, minX);
    result = clipRight(result, maxX);
    return result;
  }

  zones.forEach((c, i) => {
    const start = Math.max(c.x, x0);
    const end = i < zones.length - 1 ? Math.min(zones[i + 1].x, x1) : x1;

    if (end <= start) return;

    const clipped = clipPolygonByX(wh, start, end);
    if (!clipped || clipped.length < 3) return;

    const hh = Math.max((c.h || 1000) * scale, 0.2);
    const zoneColor = ceilingColors[i % ceilingColors.length];

    const roofShape = new THREE.Shape();

    clipped.forEach((p, idx) => {
      const px = tx(p.x);
      const pz = -tz(p.y);

      if (idx === 0) roofShape.moveTo(px, pz);
      else roofShape.lineTo(px, pz);
    });

    roofShape.closePath();

    const roofGeo = new THREE.ShapeGeometry(roofShape);
    roofGeo.rotateX(-Math.PI / 2);

    const roofMat = new THREE.MeshBasicMaterial({
      color: zoneColor,
      transparent: true,
      opacity: 0.1,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const roof = new THREE.Mesh(roofGeo, roofMat);
    roof.position.y = hh;
    roof.renderOrder = 8;
    scene.add(roof);

    const roofPts = clipped.concat([clipped[0]]).map(
      p => new THREE.Vector3(tx(p.x), hh, tz(p.y))
    );

    const roofLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(roofPts),
      new THREE.LineBasicMaterial({
        color: zoneColor,
        transparent: true,
        opacity: 0.85,
      })
    );

    roofLine.renderOrder = 10;
    scene.add(roofLine);

    const wallMat = new THREE.MeshBasicMaterial({
      color: zoneColor,
      transparent: true,
      opacity: 0.1,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    for (let j = 0; j < clipped.length; j++) {
      const a = clipped[j];
      const b = clipped[(j + 1) % clipped.length];

      const pts = [
        new THREE.Vector3(tx(a.x), 0, tz(a.y)),
        new THREE.Vector3(tx(b.x), 0, tz(b.y)),
        new THREE.Vector3(tx(b.x), hh, tz(b.y)),
        new THREE.Vector3(tx(a.x), hh, tz(a.y)),
      ];

      const wallGeo = new THREE.BufferGeometry();

      const verts = new Float32Array([
        pts[0].x, pts[0].y, pts[0].z,
        pts[1].x, pts[1].y, pts[1].z,
        pts[2].x, pts[2].y, pts[2].z,

        pts[0].x, pts[0].y, pts[0].z,
        pts[2].x, pts[2].y, pts[2].z,
        pts[3].x, pts[3].y, pts[3].z,
      ]);

      wallGeo.setAttribute("position", new THREE.BufferAttribute(verts, 3));

      const wall = new THREE.Mesh(wallGeo, wallMat);
      wall.renderOrder = 7;
      scene.add(wall);
    }
  });
}

    (r.obstacles || []).forEach((o) => {
      const obsBox = addBox(
        tx(o.x + o.w / 2),
        0.28,
        tz(o.y + o.d / 2),
        o.w * scale,
        0.56,
        o.d * scale,
        matObstacle
      );

      const obsEdges = new THREE.EdgesGeometry(obsBox.geometry);
      const obsLine = new THREE.LineSegments(
        obsEdges,
        new THREE.LineBasicMaterial({
          color: 0xff3232,
          transparent: true,
          opacity: 0.9,
        })
      );

      obsLine.position.copy(obsBox.position);
      scene.add(obsLine);
    });

    if (showGaps) {
      (r.placed || []).forEach((b) => addGapPoly(b.gapCoords));
    }

    G3D.rackGroups = [];
    (r.placed || []).forEach((b, i) => addRack(b, i));

    G3D.camera = camera;
    G3D.controls = controls;
    G3D.renderer = renderer;
    G3D.scene = scene;
    G3D.maxDim = maxDim;

    function animate() {
      G3D.animationId = requestAnimationFrame(animate);

      if (typeof S !== "undefined" && S.autoRotate3D) {
        G3D.autoTourAngle = (G3D.autoTourAngle || 0) + 0.0022;

        const radius = maxDim * 1.35;
        const heightBase = maxDim * 0.58;
        const heightWave = Math.sin(G3D.autoTourAngle * 0.65) * maxDim * 0.1;

        camera.position.x = Math.cos(G3D.autoTourAngle) * radius;
        camera.position.z = Math.sin(G3D.autoTourAngle) * radius;
        camera.position.y = heightBase + heightWave;

        controls.target.set(0, 0.25, 0);
        camera.lookAt(controls.target);
      }

      controls.update();
      renderer.render(scene, camera);
    }

    animate();

    const ro = new ResizeObserver(() => {
      const w = container.clientWidth || width;
      const h = container.clientHeight || height;

      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });

    ro.observe(container);
    G3D.resizeObserver = ro;
  }

  window.render3D = render3D;
  window.destroy3D = destroy3D;
  window.set3DCamera = set3DCamera;
  window.dispose3D = destroy3D;
})();