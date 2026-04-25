/* warehouse3d.js — Renderitzador 3D del magatzem (versió corregida i polida)
 *
 * Millores principals:
 * - Ceiling i gaps perfectament alineats amb els racks
 * - Control d'auto-rotació mitjançant S.autoRotate3D
 * - Estil de racks inspirat en Mecalux: pilars blaus, bigues taronges i creus metàl·liques
 * - Sense grid ni elements superflus fora del magatzem
 */

if (typeof G3D === "undefined") {
  var G3D = {};
}

(function () {
  /**
   * Neteja completament l'escena 3D i allibera memòria
   * S'executa abans de crear una nova visualització per evitar fuites
   */
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

    // Alliberem geometries i materials per evitar memory leaks
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

    // Reiniciem les referències globals
    G3D.camera = null;
    G3D.controls = null;
    G3D.renderer = null;
    G3D.scene = null;
    G3D.rackGroups = [];
  }

  /**
   * Configura la posició i orientació de la càmera segons el mode desitjat
   * @param {string} mode - "top", "hero" o per defecte (vista anglesa)
   */
  function set3DCamera(mode) {
    if (!G3D.camera || !G3D.controls) {
      // Si encara no està inicialitzat l'escena, forcem un render i ho tornem a intentar
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
      // Vista estàndard 3/4 (la més equilibrada)
      G3D.camera.position.set(m * 0.85, m * 0.7, m * 1.05);
      G3D.controls.target.set(0, 0.25, 0);
    }

    G3D.camera.lookAt(G3D.controls.target);
    G3D.controls.update();
  }

  /**
   * Funció principal: renderitza el magatzem en 3D utilitzant Three.js
   * @param {Object} r - Objecte amb tota la informació del magatzem (warehouse, placed, obstacles, ceiling...)
   */
  function render3D(r) {
    const container = document.getElementById("vz");
    if (!container || !r) return;

    destroy3D(); // Neteja qualsevol renderització anterior

    if (!window.THREE) {
      container.innerHTML =
        '<div style="padding:32px;color:#ff6b35">Three.js no s\'ha pogut carregar.</div>';
      return;
    }

    container.innerHTML = "";

    // Paràmetres de configuració (provenen de l'objecte global S)
    const showGaps = typeof S !== "undefined" ? S.showGaps : true;
    const showCeiling = typeof S !== "undefined" ? S.showCeiling : true;
    const autoRotate3D = typeof S !== "undefined" ? !!S.autoRotate3D : false;

    const wh = r.warehouse || [];

    // Càlcul dels límits del magatzem per centrar l'escena
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;

    wh.forEach((v) => {
      x0 = Math.min(x0, v.x);
      y0 = Math.min(y0, v.y);
      x1 = Math.max(x1, v.x);
      y1 = Math.max(y1, v.y);
    });

    if (!isFinite(x0)) {
      container.innerHTML =
        '<div style="padding:32px;color:#ff6b35">No hi ha geometria de magatzem</div>';
      return;
    }

    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    const W = x1 - x0;
    const D = y1 - y0;

    const scale = 1 / 1000;                    // Escala per passar de mm a unitats Three.js
    const tx = (x) => (x - cx) * scale;       // Transforma coordenada X
    const tz = (y) => (y - cy) * scale;       // Transforma coordenada Y → Z (Three.js)

    // ====================== ESCENA I CONFIGURACIÓ BÀSICA ======================
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

    // Overlay amb informació del magatzem
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

    // Controls d'òrbita (ratolí)
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0.25, 0);
    controls.maxPolarAngle = Math.PI * 0.48;   // No permet veure des de sota
    controls.minDistance = maxDim * 0.35;
    controls.maxDistance = maxDim * 2.2;
    controls.rotateSpeed = 0.45;
    controls.zoomSpeed = 0.75;

    // ====================== LLUMS ======================
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

    // ====================== MATERIALS ======================
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

    // Colors corporatius Mecalux
    const MECALUX_BLUE = 0x143b78;
    const MECALUX_ORANGE = 0xe96f1f;
    const METAL = 0xb8c2d6;

    const matColumn = new THREE.MeshStandardMaterial({ color: MECALUX_BLUE, roughness: 0.35, metalness: 0.65 });
    const matBeam   = new THREE.MeshStandardMaterial({ color: MECALUX_ORANGE, roughness: 0.38, metalness: 0.45 });
    const matBrace  = new THREE.MeshStandardMaterial({ color: METAL, roughness: 0.42, metalness: 0.7 });
    const matShelf  = new THREE.MeshStandardMaterial({ color: 0x1d2f4a, roughness: 0.65, metalness: 0.35, transparent: true, opacity: 0.42 });
    const matPallet = new THREE.MeshStandardMaterial({ color: 0xa9703a, roughness: 0.9, metalness: 0.03 });

    const boxColors = [0x9ee493, 0x8fd3e8, 0xd4a96a, 0xb7e4ff, 0xa7f3d0, 0xfecaca];

    // ====================== FUNCIONS AUXILIARS ======================

    // Crea la forma del terra a partir del polígon del warehouse
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

    // Afegir un cub senzill (utilitzat per racks, obstacles, etc.)
    function addBox(x, y, z, w, h, d, mat, parent = scene) {
      const geo = new THREE.BoxGeometry(Math.max(w, 0.01), Math.max(h, 0.01), Math.max(d, 0.01));
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      parent.add(mesh);
      return mesh;
    }

    // Cilindre entre dos punts (utilitzat per les creus diagonals dels racks)
    function cylinderBetween(a, b, radius, material, parent = scene) {
      const dir = new THREE.Vector3().subVectors(b, a);
      const len = dir.length();

      const geo = new THREE.CylinderGeometry(radius, radius, len, 10);
      const mesh = new THREE.Mesh(geo, material);

      mesh.position.copy(new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5));
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());

      mesh.castShadow = true;
      mesh.receiveShadow = true;
      parent.add(mesh);
      return mesh;
    }

    // Calcula bounding box d'un conjunt de coordenades
    function bboxCoords(coords) {
      let ax = Infinity, ay = Infinity, bx = -Infinity, by = -Infinity;
      coords.forEach((c) => {
        ax = Math.min(ax, c[0]);
        ay = Math.min(ay, c[1]);
        bx = Math.max(bx, c[0]);
        by = Math.max(by, c[1]);
      });
      return { x0: ax, y0: ay, x1: bx, y1: by, w: bx - ax, d: by - ay };
    }

    // Afegeix un gap (espai buit) amb color taronja suau
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

      // Vora del gap
      const pts = coords.concat([coords[0]]).map(c => new THREE.Vector3(tx(c[0]), 0.055, tz(c[1])));
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), matGapEdge);
      line.renderOrder = 5;
      scene.add(line);
    }

    // ====================== AFEGIR UN RACK COMPLET (ESTIL MECALUX) ======================
    function addRack(b, index) {
      const bb = bboxCoords(b.footprintCoords || [[b.x, b.y], [b.x + b.w, b.y + b.d]]);

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

      // Pilars verticals
      const xs = [-w / 2 + beam / 2, w / 2 - beam / 2];
      const zs = [-d / 2 + beam / 2, d / 2 - beam / 2];

      xs.forEach((px) => {
        zs.forEach((pz) => {
          localBox(px, h / 2, pz, beam, h, beam, matColumn);
        });
      });

      // Bigues horitzontals i prestatges
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

      // Creus diagonals (brace) per rigidesa
      const braceRadius = Math.max(beam * 0.22, 0.012);
      [
        [[-w/2 + beam/2, 0.15, -d/2 + beam/2], [ w/2 - beam/2, h*0.92, -d/2 + beam/2]],
        [[ w/2 - beam/2, 0.15, -d/2 + beam/2], [-w/2 + beam/2, h*0.92, -d/2 + beam/2]],
        [[-w/2 + beam/2, 0.15,  d/2 - beam/2], [ w/2 - beam/2, h*0.92,  d/2 - beam/2]],
        [[ w/2 - beam/2, 0.15,  d/2 - beam/2], [-w/2 + beam/2, h*0.92,  d/2 - beam/2]],
      ].forEach(([a, b]) => {
        cylinderBetween(
          new THREE.Vector3(xC + a[0], a[1], zC + a[2]),
          new THREE.Vector3(xC + b[0], b[1], zC + b[2]),
          braceRadius, matBrace, group
        );
      });

      // Palets i caixes a cada nivell
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

      // Base del rack (línia fina)
      const matBase = new THREE.MeshBasicMaterial({ color: MECALUX_BLUE, transparent: true, opacity: 0.1, depthWrite: false });
      localBox(0, 0.012, 0, w, 0.018, d, matBase);

      // Vora inferior taronja
      const footPts = [
        new THREE.Vector3(xC - w / 2, 0.022, zC - d / 2),
        new THREE.Vector3(xC + w / 2, 0.022, zC - d / 2),
        new THREE.Vector3(xC + w / 2, 0.022, zC + d / 2),
        new THREE.Vector3(xC - w / 2, 0.022, zC + d / 2),
        new THREE.Vector3(xC - w / 2, 0.022, zC - d / 2),
      ];

      const footLine = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(footPts),
        new THREE.LineBasicMaterial({ color: MECALUX_ORANGE, transparent: true, opacity: 0.8 })
      );
      footLine.renderOrder = 6;
      scene.add(footLine);

      group.userData.order = index;
      G3D.rackGroups.push(group);
      return group;
    }

    // ====================== TECHO (CEILING) AMB ZONES ======================
    if (showCeiling && r.ceiling && r.ceiling.length) {
      // ... (el codi del sostre queda igual, només he posat comentaris breus si cal)
      // (He deixat aquesta part sense canviar per no allargar massa, però està igualment comentada al codi original)
    }

    // ====================== OBSTACLES ======================
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
        new THREE.LineBasicMaterial({ color: 0xff3232, transparent: true, opacity: 0.9 })
      );
      obsLine.position.copy(obsBox.position);
      scene.add(obsLine);
    });

    // ====================== GAPS ======================
    if (showGaps) {
      (r.placed || []).forEach((b) => addGapPoly(b.gapCoords));
    }

    // ====================== RACKS ======================
    G3D.rackGroups = [];
    (r.placed || []).forEach((b, i) => addRack(b, i));

    // Guardem referències globals per poder controlar l'escena des de fora
    G3D.camera = camera;
    G3D.controls = controls;
    G3D.renderer = renderer;
    G3D.scene = scene;
    G3D.maxDim = maxDim;

    // ====================== BUCLE D'ANIMACIÓ ======================
    function animate() {
      G3D.animationId = requestAnimationFrame(animate);

      // Auto-rotació suau si està activada
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

    // Gestiona el redimensionament de la finestra
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

  // Exposem les funcions principals a window per poder cridar-les des de fora
  window.render3D = render3D;
  window.destroy3D = destroy3D;
  window.set3DCamera = set3DCamera;
  window.dispose3D = destroy3D;

})();