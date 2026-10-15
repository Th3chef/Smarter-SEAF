# Smarter SEAF art

The release art is a propaganda-poster version of the game's own SEAF soldiers, EAT-17 and Charger models, rendered in
three.js and printed as flat inks.

1. Export the models with Filediver (glTF): `content/fac_super_earth/cha_seaf/cha_battlefront_seaf`, the assault rifle
   (`content/fac_helldivers/equipment/primary_weapons/assault_rifle/assault_rifle` with its magazine, muzzle and optics),
   `content/fac_helldivers/equipment/support_weapons/lat_oneshot/lat_oneshot` and `content/fac_bugs/cha_charger/cha_charger`.
   Put them in `models/`. They are game files and are not stored here.
2. `npm install three@0.169.0 playwright-core@1.47.2 @fontsource/anton @fontsource/barlow-condensed`, serve this folder
   (`python3 -m http.server 8765`) and render pages with `node shot.mjs "<page>?<params>" out.png W H`.
   - `pose.js` poses each soldier with two-bone IK onto the weapons' `IK_right` / `IK_left` bones; shading is
     MeshMatcapMaterial with `matcap_body.png` / `matcap_gun.png`.
   - The squad: `scene.html?shot=poster&w=1254&h=1254&bx=-0.5&bz=-0.8&ccx=-1.05&ccz=-1.7&ax=0.2&az=0.3&yb=0.6&yc=0.4&px=-2.0&cy=0.15&pz=3.3&aty=0.95&atx=0.1&fov=40`
     to `layers/P_squad.png`, then `posterize.py` makes `layers/P_squad_post.png` (three inks). The Charger:
     `charger.html` to `layers/L_charger.png`.
3. `poster.py pspec_<size>.json` makes each backdrop (sunburst, sun, halftone, ridge with Charger silhouettes and a ping
   marker, the squad, the title band); `ptitle_<size>.html` sets the type over it; `finish.py` prints worn ink and paper
   grain over everything. Sizes: `thumb` 1254 (the Arsenal icon is this at 512), `wide` 1920x1080 (gallery), `header`
   1300x372 (Nexus header), `cover` 1600x1000 (AyakaMods cover; title and badge inside the middle 1200 px), `social`
   1280x640 (GitHub social preview, JPG q90).
4. Option icons: `icons.py` (256 px), from the earlier painted composite (`bg.py`, `comp.py spec_wide.json`).
