// Smarter SEAF art: load the game's SEAF soldier and weapons (Filediver glTF), pose them with simple two-bone IK
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const loader = new GLTFLoader();
export const load = (u) => new Promise((res, rej) => loader.load(u, res, undefined, rej));
const V = () => new THREE.Vector3();

export function byName(root) { const m = {}; root.traverse(o => { if (o.name) m[o.name] = o; }); return m; }
export function wpos(o) { o.updateWorldMatrix(true, false); return o.getWorldPosition(V()); }

// rotate bone so that the direction bone->child (world) points along dir (world)
export function aim(bone, child, dir) {
  bone.updateWorldMatrix(true, true);
  const a = wpos(bone), b = wpos(child);
  const cur = b.sub(a).normalize();
  const q = new THREE.Quaternion().setFromUnitVectors(cur, dir.clone().normalize());
  const bw = bone.getWorldQuaternion(new THREE.Quaternion());
  const pw = bone.parent.getWorldQuaternion(new THREE.Quaternion());
  bone.quaternion.copy(pw.invert().multiply(q.multiply(bw)));
  bone.updateWorldMatrix(false, true);
}
// two-bone IK: upper (shoulder) -> lower (elbow) -> end (hand) reaches target, elbow bent toward pole
export function ik(upper, lower, end, target, pole) {
  const S = wpos(upper), E = wpos(lower), H = wpos(end);
  const L1 = S.distanceTo(E), L2 = E.distanceTo(H);
  const toT = target.clone().sub(S); let d = toT.length();
  d = Math.min(d, (L1 + L2) * 0.999);
  const dir = toT.normalize();
  const a = Math.acos(THREE.MathUtils.clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1));
  // plane: dir and pole
  const p = pole.clone().sub(S); p.sub(dir.clone().multiplyScalar(p.dot(dir))).normalize();
  const elbow = S.clone().add(dir.clone().multiplyScalar(Math.cos(a) * L1)).add(p.multiplyScalar(Math.sin(a) * L1));
  aim(upper, lower, elbow.clone().sub(S));
  aim(lower, end, target.clone().sub(wpos(lower)));
}
// orient a hand (and its fingers stay as they are) so its local axes follow a world rotation
export function setWorldQuat(bone, q) {
  const pw = bone.parent.getWorldQuaternion(new THREE.Quaternion());
  bone.quaternion.copy(pw.invert().multiply(q.clone()));
  bone.updateWorldMatrix(false, true);
}
export function fixNormals(g) {
  const pos = g.attributes.position, on = g.attributes.normal;
  const idx = g.index ? g.index.array : null;
  const n = pos.count, acc = new Float32Array(n * 3);
  const tri = idx ? idx.length / 3 : n / 3;
  const a = V(), b = V(), c = V(), e1 = V(), e2 = V(), f = V(), o = V();
  for (let t = 0; t < tri; t++) {
    const i0 = idx ? idx[3 * t] : 3 * t, i1 = idx ? idx[3 * t + 1] : 3 * t + 1, i2 = idx ? idx[3 * t + 2] : 3 * t + 2;
    a.fromBufferAttribute(pos, i0); b.fromBufferAttribute(pos, i1); c.fromBufferAttribute(pos, i2);
    f.crossVectors(e1.subVectors(b, a), e2.subVectors(c, a));   // area-weighted face normal
    if (on) {
      o.set(0, 0, 0);
      for (const i of [i0, i1, i2]) o.x += on.getX(i), o.y += on.getY(i), o.z += on.getZ(i);
      if (f.dot(o) < 0) f.negate();
    }
    for (const i of [i0, i1, i2]) { acc[3 * i] += f.x; acc[3 * i + 1] += f.y; acc[3 * i + 2] += f.z; }
  }
  for (let i = 0; i < n; i++) {
    const x = acc[3 * i], y = acc[3 * i + 1], z = acc[3 * i + 2], l = Math.hypot(x, y, z) || 1;
    acc[3 * i] = x / l; acc[3 * i + 1] = y / l; acc[3 * i + 2] = z / l;
  }
  g.setAttribute('normal', new THREE.BufferAttribute(acc, 3));
}
export function clean(root, keep, mat) {
  root.traverse(o => {
    if (o.isMesh) {
      o.visible = keep.test(o.name);
      o.frustumCulled = false; o.castShadow = true; o.receiveShadow = true;
      o.material = (typeof mat === 'function') ? mat(o) : mat;
    }
  });
}

// ---- a SEAF soldier with a weapon, posed. opts: { yaw (body turn), aimPitch (rad, + = up), weapon: 'rifle'|'eat'|'smg', mask }
export async function soldier(THREE_, mats, opts = {}) {
  const S = (await load('models/seaf.glb')).scene;
  const mask = opts.mask || 'specialist_mask';
  clean(S, new RegExp('(whole|0x89bb0f3f|visor|flashlight|' + mask + ')$'), mats.body);
  const B = byName(S);
  const root = new THREE.Group(); root.add(S); S.rotation.y = Math.PI;
  root.updateMatrixWorld(true);
  // torso: turn the chest a little so the left shoulder comes forward (a shooting stance), head looks ahead
  const tw = opts.twist ?? -0.35;
  B.spine1.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), tw * 0.4);
  B.spine2.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), tw * 0.6);
  B.head && B.head.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), -tw * 0.8);
  const X = new THREE.Vector3(1, 0, 0), st = opts.stride ?? 1;
  B.l_thigh.rotateOnWorldAxis(X, -0.32 * st); B.l_knee.rotateOnWorldAxis(X, 0.30 * st);
  B.r_thigh.rotateOnWorldAxis(X, 0.22 * st); B.r_knee.rotateOnWorldAxis(X, 0.18 * st);
  B.hips.position.y -= 0.0;
  root.updateMatrixWorld(true);
  // feet back on the ground: the lowest toe at y=0
  const lowest = Math.min(wpos(B.l_toe).y, wpos(B.r_toe).y, wpos(B.l_foot).y - 0.08, wpos(B.r_foot).y - 0.08);
  S.position.y -= lowest - 0.0;
  root.updateMatrixWorld(true);
  let W;
  if (opts.weapon === 'eat') {
    W = (await load('models/lat_oneshot.unit.glb')).scene; clean(W, /^g_lat_1$/, mats.gun);
  } else {
    W = (await load('models/assault_rifle.unit.glb')).scene; clean(W, /^mesh_0/, mats.gun);
    const WB = byName(W);
    for (const [f, att] of [['assaultrifle_standard_magazine', 'attach_mag'], ['muzzle_8mm_naked', 'attach_muzzle'], ['optics_ironsight', 'attach_optic']]) {
      const a = (await load('models/' + f + '.unit.glb')).scene; clean(a, /^g_(?!.*(LOD|shadow)).*_1$/, mats.gun); WB[att].add(a);
    }
  }
  const WB = byName(W);
  root.add(W);
  // weapon: forward is its -z; turn it to face the soldier's front (+z), pitched by aimPitch, stock at the right shoulder
  const pitch = opts.aimPitch ?? 0;
  W.rotation.set(-pitch, Math.PI + (opts.weaponYaw ?? 0.05), 0, 'YXZ');
  const shoulder = wpos(B.r_shoulder);
  const anchor = opts.weapon === 'eat' ? new THREE.Vector3(-0.015, 0.07, 0.42) : new THREE.Vector3(0.015, 0.03, 0.33);   // (weapon-local point at the shoulder)
  W.position.set(0, 0, 0); W.updateMatrixWorld(true);
  const a = anchor.clone().applyQuaternion(W.quaternion);
  const at = shoulder.clone().add(opts.weapon === 'eat' ? new THREE.Vector3(-0.07, 0.16, -0.04) : new THREE.Vector3(0.05, -0.06, 0.08));
  W.position.copy(at.sub(a)); W.updateMatrixWorld(true);
  // hands onto the weapon's grips, elbows down and out
  const R = wpos(WB.IK_right), L = wpos(WB.IK_left);
  ik(B.r_shoulder, B.r_elbow, B.r_hand, R, wpos(B.r_shoulder).add(new THREE.Vector3(-0.5, -0.8, 0.0)));
  ik(B.l_shoulder, B.l_elbow, B.l_hand, L, wpos(B.l_shoulder).add(new THREE.Vector3(0.4, -0.9, 0.2)));
  root.updateMatrixWorld(true);
  curl(B, 'r'); curl(B, 'l');
  root.updateMatrixWorld(true);
  return { root, S, B, W, WB };
}

// fingers closed round a grip: each joint turned about the hand's knuckle line
export function curl(B, side, amount = [0.9, 1.0, 0.7]) {
  const a = wpos(B[side + '_index_finger1']), b = wpos(B[side + '_pinky_finger1']);
  const axis = a.sub(b).normalize();
  for (const f of ['index', 'middle', 'ring', 'pinky']) {
    for (let k = 1; k <= 3; k++) {
      const bone = B[side + '_' + f + '_finger' + k];
      if (bone) { bone.rotateOnWorldAxis(axis, amount[k - 1]); bone.updateWorldMatrix(false, true); }
    }
  }
}
