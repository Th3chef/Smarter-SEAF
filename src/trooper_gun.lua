  -- ======================================================================================================
  -- (Smarter SEAF, Test 4) each soldier's gun - the weapon actually in his hands - and where it really points.
  -- His weapon wielder record (WeaponWielderComponent, rows of 464 bytes) starts with the entity id of the weapon in his
  -- hands (0 = nothing: a Test 3 F8 right after a specialist fired his EAT). That weapon's own record (the same weapon
  -- list as the sentries') gives its muzzle part, and its unit's pose that part's place and axes. Which axis is the
  -- barrel is learned per weapon kind while he aims at his target (as the sentries' barrels are).
  -- * Gun on a friend: whenever his barrel's line passes a friend (you, a teammate, another SEAF soldier, a civilian) -
  --   staggered, getting up, swinging round - every enemy is hidden from him for that moment, so he can't fire.
  -- * The EAT: a specialist carries one EAT-17 (one shot). While he has it he goes for heavy armor first; once it is
  --   gone he is treated like a rifleman (Medium pen, closest first), and again as a specialist if he picks up another.
  -- The lists are found at their places in the known game build only (2026-09-24); otherwise this part stays off.
  -- ======================================================================================================
  local SEAF_WEAPON = {}
  for h, k in pairs({ ['3357eebb0184fdee'] = 'AR-23P Liberator Penetrator', ['ca4bbef63c869c18'] = 'SMG (12x25mm)',
    ['587878fb76f4b9b1'] = 'rifle (8x60mm)', ['5c54e81a4aaa31fc'] = 'EAT-17' }) do SEAF_WEAPON[EXT.type_hash(h)] = k end
  local EAT_TYPE = EXT.type_hash('5c54e81a4aaa31fc')
  -- (1.0.0 patch-proofing) the weapon wielder list is found like the engine's other game lists: its place in the known
  -- build, or a search of the game's code after an update (PATTERNS.optional.wielder; the patterns include its 464-byte
  -- rows at +0x60, so a changed layout is not found rather than misread). Without it this part stays off
  local GUN = { axis = {}, learn = {}, steps = {}, notes = 0, frame = -1, misses = 0, hits = 0 }
  -- (Test 6) the barrel axis of the guns, learned in game (Test 4: rifle 0.953, AR-23P 0.968, SMG 0.969; Test 5:
  -- SMG 0.989, AR-23P 0.974 - all axis 2+): set from the start, so the check works from his first shot. (1.0.0 review)
  -- the EAT too: he aims it too briefly for it to be learned (never in Tests 4-5), and all three others are axis 2+
  for _, h in ipairs({ '3357eebb0184fdee', 'ca4bbef63c869c18', '587878fb76f4b9b1', '5c54e81a4aaa31fc' }) do GUN.axis[EXT.type_hash(h)] = { axis = 2, sign = 1, match = 0, preset = true } end
  -- the AI steps where he is staggered or getting up (Test 4: his gun 89-100% off his aim in these)
  local STAGGER_STEP = { [11] = true, [13] = true, [17] = true, [18] = true, [19] = true }
  local function gun_known() return A ~= nil and A.g.wielder ~= nil and A.g.weapons ~= nil end
  -- ((1.0.1 review) the AI step numbers below are from the known game build: after an update they may mean other steps)
  local function steps_known() return A ~= nil and A.known == true end
  -- a weapon entity: its record in the weapon list (index, owner row, unit, kind, muzzle part)
  local function weapon_of(wid)
    local wm = ptr_of(read(A.g.weapons, 8), 0)
    if not wm then return nil end
    local wi = map_lookup(wm + 48, wid, 32768, nil, true)
    if not wi or wi >= 16384 then return nil end
    local owners = ptr_of(read(wm + 72, 8), 0)
    local op = owners and ptr_of(read(owners + wi * 8, 8), 0)
    local oe = op and read(op, 24)
    if not (oe and u32(oe, 8) == wid) then return nil end
    local kind = oe:sub(1, 8)
    local rt = ptr_of(read(wm + 88, 8), 0)
    local wr = rt and read(rt + wi * 1008, 228)
    local node
    if wr then
      local count, index = u32(wr, 216), u32(wr, 220)
      if count > 0 and count <= 24 and index < count then local n = u32(wr, 120 + 4 * index); if n < 1024 then node = n end end
    end
    return { id = wid, wi = wi, ptr = op, unit = u32(oe, 12), kind = kind, name = SEAF_WEAPON[kind], node = node }
  end
  -- the weapon id in his hands (his wielder record's first word), the wielder list's map header read once a frame
  local function in_hand(s)
    if not A.g.wielder then return nil end   -- ((1.0.1 review) the spent-EAT check below still runs: it needs only the weapon list)
    if GUN.frame ~= FRAME then
      GUN.frame = FRAME
      local m = ptr_of(read(A.g.wielder, 8), 0)
      GUN.mgr = m
      GUN.head = m and read(m + 0x30, 20)
      GUN.rows = m and ptr_of(read(m + 0x60, 8), 0)
    end
    if not (GUN.mgr and GUN.head and GUN.rows) then return nil end
    local idx = map_lookup(GUN.mgr + 0x30, s.id, 32768, GUN.head, true)
    if not idx or idx >= 16384 then return nil end
    local w = read(GUN.rows + idx * 464, 4)
    return w and u32(w, 0)
  end
  local function nrm3(x, y, z) local l = math.sqrt(x * x + y * y + z * z); if l < 1e-6 then return nil end; return { x / l, y / l, z / l } end
  -- (the same, into a table he keeps: no new tables every frame)
  local function nrm3_into(v, x, y, z) local l = math.sqrt(x * x + y * y + z * z); if l < 1e-6 then return nil end; v[1], v[2], v[3] = x / l, y / l, z / l; return v end
  -- (1.0.0 review) four times a second: the weapon in his hands and, for a specialist, whether he still carries an EAT.
  -- Runs for every soldier whatever the options, apart from the pose read below (only needed for the gun check)
  local function gun_track(s, t)
    if t < (s.gun_next or 0) then return end
    s.gun_next = t + 0.25
    local wid = in_hand(s)
    -- ((1.0.0 review) looked up again while it isn't found: the game may list his weapon a moment after he switches)
    if wid ~= s.gun_wid or (wid and wid ~= 0 and not s.gun) then
      local again = wid == s.gun_wid
      s.gun_wid = wid
      s.gun = (wid and wid ~= 0) and weapon_of(wid) or nil
      -- (patch-proofing) weapons in hands that never resolve in the weapon list: the log says so once
      if wid and wid ~= 0 then
        if s.gun then GUN.hits = GUN.hits + 1 elseif not again then GUN.misses = GUN.misses + 1 end
        if GUN.misses == 40 and GUN.hits == 0 and not GUN.told_miss then
          GUN.told_miss = true
          note('SEAF gun: the weapons in the soldiers\' hands are not in the weapon list (game update?): the gun checks wait for them')
        end
      end
      if TESTER and (not again or s.gun) and (GUN.notes or 0) < 30 then
        GUN.notes = GUN.notes + 1
        event(string.format('SEAF gun (test): %s now holds %s', s.tag or s.def.name, s.gun and string.format('%s (id %d%s)', s.gun.name or EXT.hexr(s.gun.kind), s.gun.id,
          s.gun.node and (', muzzle part ' .. s.gun.node) or ', no muzzle part') or (wid == 0 and 'nothing' or 'a weapon not in the list')))
      end
    end
    -- (a specialist: does he still carry an EAT? His two weapons are the entities right after his own id - the next
    -- soldier's come after those, so only +1 and +2 are his (1.0.0 review: +3 and +4 could be a neighbor's EAT))
    if s.def.eat ~= nil then
      local has = s.gun ~= nil and s.gun.kind == EAT_TYPE
      if not has then
        local me
        for k = 1, 2 do
          local w = weapon_of(s.id + k)
          if w and w.kind == EAT_TYPE then
            me = me or unit_position(s.unit)
            local p = unit_position(w.unit)
            if p and me and (p[1] - me[1]) ^ 2 + (p[2] - me[2]) ^ 2 + (p[3] - me[3]) ^ 2 < 6.25 then has = true; break end
          end
        end
      end
      if has then s.eat_seen, s.eat_gone = true, nil
      elseif s.eat_seen and not s.eat_gone then s.eat_gone = t end
    end
  end
  -- his gun this frame: muzzle place and the axes of the muzzle part (nil when nothing usable is in his hands); the
  -- tables are his own, filled in place
  local function gun_pose(s)
    local g = s.gun
    if not (g and g.node) then return nil end
    local base = unit_position(g.unit)
    if not (base and base.pose) then return nil end
    local m = read(base.pose + 64 * g.node, 64)
    if not m then return nil end
    local x, y, z = f32(m, 48), f32(m, 52), f32(m, 56)
    if not (x == x and y == y and z == z and math.abs(x) < 1e6 and math.abs(y) < 1e6 and math.abs(z) < 1e6) then return nil end
    local M, axes = s.gun_M, s.gun_axes
    if not M then M, axes = { 0, 0, 0 }, { {}, {}, {} }; s.gun_M, s.gun_axes = M, axes end
    M[1], M[2], M[3] = x, y, z
    for r = 0, 2 do
      if not nrm3_into(axes[r + 1], f32(m, r * 16), f32(m, r * 16 + 4), f32(m, r * 16 + 8)) then return nil end
    end
    return M, axes, g
  end
  -- which axis of the muzzle part runs along the barrel, per weapon kind: learned while he aims steadily at his target
  -- (at least 40 frames, his aim spread over 30 degrees, the best axis matching 0.95 or better on average)
  local function barrel_of(g, M, axes, st, s)
    local k = g.kind
    local known = GUN.axis[k]
    if known then
      local a, B = axes[known.axis], s.gun_B
      if not B then B = {}; s.gun_B = B end
      B[1], B[2], B[3] = a[1] * known.sign, a[2] * known.sign, a[3] * known.sign
      -- ((1.0.1 review) a preset is checked against where he really aims (steadily on his target, not staggered): 60
      -- samples, on average well along his aim (a wrong axis is about square to it). A wrong one is dropped and the
      -- barrel learned instead (the EAT's was set from the other guns, never measured)
      if known.preset and not known.checked and st.target ~= 0 and st.synced and st.aim and not STAGGER_STEP[st.node] then
        local dx, dy, dz = st.aim[1] - M[1], st.aim[2] - M[2], st.aim[3] - M[3]
        local l = math.sqrt(dx * dx + dy * dy + dz * dz)
        if l > 1 then
          known.sum, known.n = (known.sum or 0) + (B[1] * dx + B[2] * dy + B[3] * dz) / l, (known.n or 0) + 1
          if known.n >= 60 then
            local mean = known.sum / known.n
            if mean >= 0.7 then known.checked = true
            else
              GUN.axis[k] = nil
              note(string.format('SEAF gun: the preset barrel of the %s does not match his aim (%.2f): learning it instead', g.name or EXT.hexr(k), mean))
              return nil
            end
          end
        end
      end
      return B
    end
    if not (st.target ~= 0 and st.synced and st.aim) then return nil end
    local v = nrm3(st.aim[1] - M[1], st.aim[2] - M[2], st.aim[3] - M[3])
    if not v then return nil end
    local L = GUN.learn[k]
    if not L then L = { sums = { 0, 0, 0, 0, 0, 0 }, n = 0, d0 = v, spread = 1, tries = 0 }; GUN.learn[k] = L end
    if L.tries >= 5 then return nil end
    for r = 1, 3 do
      local c = axes[r][1] * v[1] + axes[r][2] * v[2] + axes[r][3] * v[3]
      L.sums[2 * r - 1], L.sums[2 * r] = L.sums[2 * r - 1] + c, L.sums[2 * r] - c
    end
    L.n = L.n + 1
    L.spread = math.min(L.spread, L.d0[1] * v[1] + L.d0[2] * v[2] + L.d0[3] * v[3])
    if L.n >= 40 and L.spread <= 0.87 then
      local best, bk
      for i = 1, 6 do if not best or L.sums[i] > best then best, bk = L.sums[i], i end end
      local mean = best / L.n
      L.tries = L.tries + 1
      if mean >= 0.95 then
        GUN.axis[k] = { axis = math.floor((bk + 1) / 2), sign = bk % 2 == 1 and 1 or -1, match = mean }
        note(string.format('SEAF gun: barrel of the %s found (axis %d%s, match %.3f)', g.name or EXT.hexr(k), GUN.axis[k].axis, GUN.axis[k].sign > 0 and '+' or '-', mean))
      elseif TESTER then
        note(string.format('SEAF gun (test): barrel of the %s not found yet (best match %.3f)', g.name or EXT.hexr(k), mean))
      end
      GUN.learn[k] = { sums = { 0, 0, 0, 0, 0, 0 }, n = 0, d0 = v, spread = 1, tries = L.tries }
    end
    return nil
  end
  -- does his barrel's line (60 m out) pass a friend? Returns the body or nil; also keeps, per AI step, how often his
  -- barrel was more than 25 degrees off his aim (test builds: to see which steps are staggers and getting up)
  local GUN_REACH, GUN_MARGIN = 60, 0.35
  -- ((1.0.0 review) your sentries too, with Friendly Fire Safety for helldivers: st.posts, nil with it off)
  local function gun_on_friend(s, st, bodies, t)
    local posts = st.posts
    if not gun_known() or (#bodies == 0 and not (posts and posts[1])) then return nil end
    -- (Test 6) with no target he isn't firing: only checked while staggered or getting up (before, every enemy was
    -- hidden from a soldier walking with his gun across his squad, so he couldn't pick one - 33,021 frames in Test 5)
    if st.target == 0 and not (steps_known() and STAGGER_STEP[st.node]) then return nil end
    local M, axes, g = gun_pose(s)
    if not M then return nil end
    local B = barrel_of(g, M, axes, st, s)
    if not B then return nil end
    if TESTER and st.target ~= 0 and st.aim then
      local v = nrm3(st.aim[1] - M[1], st.aim[2] - M[2], st.aim[3] - M[3])
      if v then
        local S = GUN.steps[st.node]
        if not S then S = { n = 0, off = 0 }; GUN.steps[st.node] = S end
        S.n = S.n + 1
        if B[1] * v[1] + B[2] * v[2] + B[3] * v[3] < 0.906 then S.off = S.off + 1 end
      end
    end
    -- (Test 5) with a target, only as far as just past it (his shots stop there): a friend well behind it doesn't count
    local reach = GUN_REACH
    if st.current and st.current.pos then
      local p = st.current.pos
      reach = math.min(GUN_REACH, math.sqrt((p[1] - M[1]) ^ 2 + (p[2] - M[2]) ^ 2 + (p[3] - M[3]) ^ 2) + 3)
    end
    local far = s.gun_far
    if not far then far = {}; s.gun_far = far end
    far[1], far[2], far[3] = M[1] + B[1] * reach, M[2] + B[2] * reach, M[3] + B[3] * reach
    for k = 1, 2 do
      for _, b in ipairs(k == 1 and bodies or posts or bodies) do
        if (k == 1 or posts) and b.sid ~= s.id then
          local a = b.at
          local ax, ay, az = a[1] - M[1], a[2] - M[2], a[3] + 1 - M[3]
          local along = ax * B[1] + ay * B[2] + az * B[3]
          if along > 0.3 and along < reach then
            if segment_distance(M, far, b.lo, b.hi) < GUN_MARGIN + (b.extra or 0) then return b end
          end
        end
      end
      if not posts then break end
    end
    return nil
  end
  SGD.seaf_gun = GUN
  -- ======================================================================================================
  -- (1.0.0) the options: each a tiny addon setting a flag, read every frame (Friendly Fire Safety sets the engine's own safety
  -- flags; Armor Intelligence its armor and priority flags; Ping Targeting this one)
  -- ======================================================================================================
  local function opt_armor() return rawget(_G, 'SmarterSEAFArmor') == true end
  local function opt_ping() return OPT.ping() end
  -- ======================================================================================================
  -- (Test 7) structures. STRUCT_EAT: what a specialist's EAT can destroy (fabricators, bug holes and other objectives;
  -- type ids from the HD2 Codex, Oct 2026). STRUCT_NEVER: what SEAF can't damage at all (the Detector Tower), always
  -- hidden from soldiers. STRUCT_ALL: those and the other objectives, for the Tester's research log.
  -- ======================================================================================================
  local EAT_HEAVY, EAT_WAIT, EAT_REACH2 = 4, 4, 100 * 100
  local STRUCT_EAT, STRUCT_ALL = {}, {}
  for h, k in pairs({ a57ae2a703c02899 = 'Automaton Fabricator', ['5c9fb9272608b8dc'] = 'Automaton Fabricator (static)',
    a2a86454f67fbc47 = 'Bulk Fabricator', ['2e454bd4d24eb04a'] = 'Bug Hole (small)', a83587cbff25c79e = 'Bug Hole (medium)',
    ['3b3327050e8c2c23'] = 'Bug Hole (ceiling)', d6a27adb179ad4ff = 'Bug Hole (large)', ['095686275a113614'] = 'Shrieker Nest',
    aa28caf964d05500 = 'Spore Spewer', ['0883366204e1ccc5'] = 'Gazer',
    ['14a5d7e66f994a69'] = 'Lightning Spire', ['01fe503dcd17847b'] = 'Warp Gateway' }) do
    STRUCT_EAT[EXT.type_hash(h)] = k; STRUCT_ALL[EXT.type_hash(h)] = k
  end
  for h, k in pairs({ ['2670e0047b2eb409'] = 'Detector Tower', d38424635441103f = 'Automaton Fabricator (marker)', a8ae6952b375ef6c = 'Gunship Facility',
    cdb573e646581547 = 'Stratagem Jammer', ['6e499c5c95b019fc'] = 'Command Bunker', ['1448d494665d01a0'] = 'Gazer Spire',
    ['1445df29152c9be2'] = 'Cognitive Disruptor', ['4e6a3daf2d221aa5'] = 'Transmission Tower', ['6838d8c197cc9c78'] = 'Orbital Cannon',
    ['5fbf41e3daedc606'] = 'Air Base Control Tower', b8fe3a0fe1a58465 = 'Supply Stockpile', dd2dac48bc52d2be = 'Spore Lung',
    e979fe35857c54d9 = 'Terminid Control System tower', ['06d3c4720e642fc1'] = 'Hatchery egg', ['691d6c666bfaccf5'] = 'Monolith' }) do
    STRUCT_ALL[EXT.type_hash(h)] = k
  end
  local STRUCT_NEVER = { [EXT.type_hash('2670e0047b2eb409')] = 'Detector Tower' }
  SEAF.struct_types = TESTER and STRUCT_ALL or nil   -- (1.0.0 review: the targeting-list scan keeps them for the Tester's log only)
  SEAF.structs = SEAF.structs or {}
  -- what a specialist may fire his EAT at: armor 4 and up (Chargers and heavier), or a structure it can destroy
  local function eat_ok(c)
    local a = c.kind and ARMOR[c.kind]
    if a then return a.av >= EAT_HEAVY and not a.sentries_skip end
    return c.kind ~= nil and STRUCT_EAT[c.kind] ~= nil
  end
  -- is the EAT in his hands, and still kept for heavy armor (not let go yet)?
  local function eat_kept(s)
    return s.def.eat == true and s.gun ~= nil and s.gun.kind == EAT_TYPE and not (s.eat_hold and s.eat_hold.free) and opt_armor()
  end
  -- an enemy that a friend was in front of a moment ago (the engine's 0.3 s linger after an unsafe shot), or that is
  -- unsafe right now: never one he is pushed onto
  local function unsafe_now(s, st, id)
    return (st.unsafe_why and st.unsafe_why[id]) or (s.P.unsafe_seen and s.P.unsafe_seen[id]) or false
  end
  -- ======================================================================================================
  -- (Smarter SEAF) pings: an enemy you (or a teammate) ping has its spot record (SpottableComponent, 24-byte rows) marked:
  -- +0x10 a flag set to 1, and +8 the game's clock (microseconds, low 32 bits) at the moment of the ping - each ping
  -- in a Test 5 log was that many seconds after the one before. So a ping's age is read, not guessed: a soldier
  -- within 50 m of you goes for an enemy pinged in the last 20 s that he can see and hurt. Known game build only.
  -- ======================================================================================================
  -- (1.0.0 patch-proofing) the spot list is found like the wielder list (PATTERNS.optional.spotted; the patterns include
  -- its 24-byte rows at +0x40); a flag byte other than 0/1 means the record changed (game update?): pings then stay off.
  -- (1.0.0 review) a ping word seen expired is never taken again: were the flag left set, the same word would read as
  -- fresh again when the clock's low 32 bits come round (every ~71.6 minutes)
  local PING = { t = -1, pinged = {}, dead = {}, ndead = 0, odd = 0, okrows = 0, notes = 0, LAST = 20, NEAR = 50 }
  local TWO32 = 4294967296
  local NOPE = {}
  local function ping_refresh(t, me)
    if t < PING.t then return end
    PING.t = t + 0.25
    if PING.off or not A.g.spotted then return end
    local m = ptr_of(read(A.g.spotted, 8), 0)
    local h = m and read(m + 0x20, 20)
    local rows = m and ptr_of(read(m + 0x40, 8), 0)
    if not (h and rows) then return end
    local cap = u32(h, 8)
    if cap == 0 or cap > 65536 or bit.band(cap, cap - 1) ~= 0 then return end
    local now32 = clock_now() % TWO32
    local seen = {}
    local near2 = PING.NEAR * PING.NEAR
    for _, s in pairs(sentries) do
      -- ((1.0.1 review) only the soldiers a ping can move: within 50 m of you)
      local b = s.st and s.st.base
      for _, c in ipairs((b and me and (b[1] - me[1]) ^ 2 + (b[2] - me[2]) ^ 2 + (b[3] - me[3]) ^ 2 <= near2) and s.last_cands or NOPE) do
        local id = c.id
        if not seen[id] then
          seen[id] = true
          local idx = map_lookup(m + 0x20, id, 65536, h, true)
          local row = idx and idx < 65536 and read(rows + idx * 24, 24)
          local P0 = PING.pinged[id]
          if row and row:byte(17) > 1 and not A.known then   -- ((1.0.1 review) after a game update only)
            PING.odd = PING.odd + 1
            if PING.odd >= 20 and PING.odd > PING.okrows then
              PING.off, PING.pinged = true, {}
              note('SEAF pings: the spot record layout is not recognized (game update?): Ping Targeting off')
              return
            end
          elseif row then PING.okrows = PING.okrows + 1 end
          if row and row:byte(17) == 1 and u32(row, 8) ~= 0 then
            local word = u32(row, 8)
            local age = ((now32 - word) % TWO32) / 1e6
            if PING.dead[id] == word then age = PING.LAST + 1 end
            if age > PING.LAST and PING.dead[id] ~= word then
              if PING.ndead >= 512 then PING.dead, PING.ndead = {}, 0 end
              PING.dead[id], PING.ndead = word, PING.ndead + 1
            end
            if age <= PING.LAST then
              if not P0 or P0.word ~= word then
                PING.pinged[id] = { word = word, t = t - age }
                if TESTER and PING.notes < 30 then
                  PING.notes = PING.notes + 1
                  event(string.format('SEAF ping: enemy %d (%s) pinged %.1f s ago: soldiers within 50 m of you who can hurt it go for it', id, c.kind and EXT.hexr(c.kind) or '?', age))
                end
              end
            elseif P0 then PING.pinged[id] = nil end
          elseif P0 then PING.pinged[id] = nil end
        end
      end
    end
    for id, P0 in pairs(PING.pinged) do
      if not seen[id] or t - P0.t > PING.LAST then PING.pinged[id] = nil
      -- (test builds) 4 s after each ping: how many soldiers got onto it, and how many gave up
      elseif TESTER and not P0.told and t - P0.t >= 4 and PING.notes < 30 then
        P0.told, PING.notes = true, PING.notes + 1
        local on, chasing, gave, see = 0, 0, 0, 0
        for _, s in pairs(sentries) do
          if s.def.trooper then
            if s.ping and s.ping.id == id and s.ping.word == P0.word then if s.ping.on then on = on + 1 else chasing = chasing + 1 end end
            if s.ping_skip and s.ping_skip[id] == P0.word then gave = gave + 1 end
            for _, c in ipairs(s.last_cands or {}) do if c.id == id and c.visible then see = see + 1; break end end
          end
        end
        event(string.format('SEAF ping result: enemy %d after 4 s: %d soldiers on it, %d still turning to it, %d gave up (2 s without getting onto it), %d can see it', id, on, chasing, gave, see))
      end
    end
  end
  -- the pinged enemy he should go for (nil if none he can see and hurt, fresh, safe, within reach)
  local function ping_target(s, st, t, me)
    if PING.off or not A.g.spotted then return nil end
    local b = st.base
    if not (me and b and (b[1] - me[1]) ^ 2 + (b[2] - me[2]) ^ 2 + (b[3] - me[3]) ^ 2 <= PING.NEAR * PING.NEAR) then return nil end
    ping_refresh(t, me)
    if not next(PING.pinged) then return nil end
    local kept = eat_kept(s)
    local best, bd
    for _, c in ipairs(st.candidates) do
      local P0 = PING.pinged[c.id]
      if P0 and t - P0.t <= PING.LAST and c.alive and c.visible and c.pos and c.d2 and c.d2 < 100 * 100
        and not (s.ping_skip and s.ping_skip[c.id] == P0.word) and not unsafe_now(s, st, c.id)
        and not EXT.cannot_hurt(s.def, c)
        -- (1.0.0 review) not one the other rules would hide from him anyway (a light enemy while he keeps his EAT for
        -- heavy armor, a structure SEAF can't damage): he would only stand idle 2 s before giving up
        and not (c.kind and STRUCT_NEVER[c.kind]) and not (kept and not eat_ok(c))
        and not (st.aboard and st.aboard[c.id]) then   -- ((1.0.1 review) not one still aboard a dropship)
        if not bd or c.d2 < bd then best, bd = c, c.d2 end
      end
    end
    return best
  end
  -- (Ping Targeting) everything but the pinged enemy hidden from him and he is moved onto it; once he is on it, no
  -- other rule but safety moves him off it (1.0.0 review: the closest-first rule kept clearing his target, 6 times in
  -- 3 s). If he isn't on it within 2 s (the game won't let him pick it) he gives up on that ping and fights as before.
  local function ping_step(s, st, t, req, me)
    local pc = opt_ping() and ping_target(s, st, t, me)
    if not pc then
      s.ping = nil
      if s.ping_skip then for id, w in pairs(s.ping_skip) do local P0 = PING.pinged[id]; if not (P0 and P0.word == w) then s.ping_skip[id] = nil end end end
      return
    end
    local P0 = PING.pinged[pc.id]
    local sp = s.ping
    if not (sp and sp.id == pc.id and sp.word == P0.word) then
      sp = { id = pc.id, word = P0.word, t0 = t }
      s.ping = sp
      bump(session.actions, 'trooper_ping_chase')
    end
    if st.target == pc.id then
      if not sp.on then sp.on = t; bump(session.actions, 'trooper_ping_on_it') end
      if req.kick and req.reason ~= 'sentry_safety' then req.kick = false end
    elseif not sp.on and t - sp.t0 > 2 then
      s.ping_skip = s.ping_skip or {}
      s.ping_skip[pc.id] = P0.word
      s.ping = nil
      bump(session.actions, 'trooper_ping_gave_up')
      return
    end
    local b = {}
    for _, c in ipairs(st.candidates) do if c.id ~= pc.id then b[c.id] = true end end
    for k in pairs(req.block) do if k ~= pc.id then b[k] = true end end
    req.block = b
    if st.target ~= pc.id then
      if not req.kick then req.kick, req.quiet, req.reason = true, true, 'trooper_ping' end
      s.P.ignored = math.max(s.P.ignored or 0, 1)
    end
  end
  -- (Armor Intelligence) a specialist keeps his EAT for heavy armor (armor 4 and up: Chargers and heavier) and the
  -- structures it can destroy. While the EAT is in his hands, every lighter enemy is hidden from him so he can't fire
  -- it at them (Test 5: all three EATs went into a Predator Stalker a minute before a Charger came). Only a heavy one he
  -- can see, alive, within 100 m counts; 4 s after the last one he is let go so he isn't left standing with it out
  -- (1.0.0 review: a dead or far-off Charger kept him holding it, 15 s in a sim).
  local function eat_hold(s, st, t)
    if s.def.eat ~= true or not opt_armor() then s.eat_hold = nil; return nil end
    local g = s.gun
    if not (g and g.kind == EAT_TYPE) then
      if s.eat_hold and TESTER and (GUN.eat_notes or 0) < 12 then
        GUN.eat_notes = (GUN.eat_notes or 0) + 1
        event(string.format('SEAF EAT: %s no longer has his EAT in his hands (fired it or put it away) after %.1f s', s.tag or s.def.name, t - s.eat_hold.t0))
      end
      s.eat_hold = nil
      return nil
    end
    local H = s.eat_hold
    if not H then H = { t0 = t, last = t }; s.eat_hold = H end
    if H.free then return nil end
    -- ((1.0.0 review) his own set, emptied and refilled: no new table every frame)
    local light = s.eat_light
    if light then for k in pairs(light) do light[k] = nil end else light = {}; s.eat_light = light end
    local any = false
    for _, c in ipairs(st.candidates) do
      if eat_ok(c) then
        if c.alive and c.visible and c.d2 and c.d2 < EAT_REACH2 then H.last = t end
      else light[c.id] = true; any = true end
    end
    if not any then light = nil end
    if t - H.last > EAT_WAIT then
      H.free = true
      bump(session.actions, 'trooper_eat_let_go')
      if TESTER and (GUN.eat_notes or 0) < 12 then
        GUN.eat_notes = (GUN.eat_notes or 0) + 1
        event(string.format('SEAF EAT: %s held his EAT %d s with nothing heavy (or a structure) in sight: let go', s.tag or s.def.name, EAT_WAIT))
      end
      return nil
    end
    if light and not H.counted then H.counted = true; bump(session.actions, 'trooper_eat_kept') end   -- ((1.0.0 review) once per draw)
    return light
  end
  -- (Armor Intelligence) structures SEAF can't damage at all (the Detector Tower): always hidden from soldiers, so they
  -- don't stand shooting at one
  local function struct_never(s, st, req)
    if not opt_armor() then return end
    local b
    for _, c in ipairs(st.candidates) do
      if c.kind and STRUCT_NEVER[c.kind] then
        if not b then b = {}; for k in pairs(req.block) do b[k] = true end end
        b[c.id] = true
      end
    end
    if b then
      req.block = b
      if b[st.target] then
        -- ((1.0.0 review) counted when it takes him off one, not every frame it is hidden)
        if s.never_on ~= st.target then s.never_on = st.target; bump(session.actions, 'trooper_structure_hidden') end
        if not req.kick then req.kick, req.quiet, req.reason = true, true, 'trooper_cannot_damage'; s.P.ignored = math.max(s.P.ignored or 0, 1) end
      else s.never_on = nil end
    end
  end
  -- (Armor Intelligence) a specialist who still carries his EAT, with no heavy enemy in sight and nothing at his feet,
  -- goes for a structure the EAT can destroy, in sight within 80 m (the others hidden from him, as for a ping) - if the
  -- game lists it among his enemies at all (the Tester's research log says). He gives up on it, for 20 s, if he isn't on
  -- it within 2 s, or hasn't drawn his EAT 6 s after getting onto it (1.0.0 review: a specialist on a fabricator with
  -- his rifle stayed on it for good), or after 20 s in all.
  local STRUCT_NEAR2, STRUCT_SELF2 = 80 * 80, 8 * 8
  local function struct_step(s, st, t, req)
    if s.def.eat ~= true or s.ping or not s.eat_seen or not opt_armor() or not gun_known() then s.struct = nil; return end
    if s.struct_skip then for id, until_t in pairs(s.struct_skip) do if t >= until_t then s.struct_skip[id] = nil end end end
    local best, bd
    for _, c in ipairs(st.candidates) do
      if c.alive and c.visible then
        local a = c.kind and ARMOR[c.kind]
        if a and a.av >= EAT_HEAVY and not a.sentries_skip then s.struct = nil; return end   -- (a heavy enemy: that first)
        local st_kind = c.kind and STRUCT_EAT[c.kind]
        if not st_kind and not (c.kind and STRUCT_ALL[c.kind]) and c.d2 and c.d2 < STRUCT_SELF2 then s.struct = nil; return end   -- (one at his feet: that first)
        if st_kind and c.pos and c.d2 and c.d2 < STRUCT_NEAR2 and not (s.struct_skip and s.struct_skip[c.id]) and not unsafe_now(s, st, c.id)
          and not (st.aboard and st.aboard[c.id]) then
          if not bd or c.d2 < bd then best, bd = c, c.d2 end
        end
      end
    end
    if not best then s.struct = nil; return end
    local sp = s.struct
    if not (sp and sp.id == best.id) then
      sp = { id = best.id, t0 = t }; s.struct = sp
      bump(session.actions, 'trooper_eat_structure_chase')
      if TESTER and (GUN.eat_notes or 0) < 20 then
        GUN.eat_notes = (GUN.eat_notes or 0) + 1
        event(string.format('SEAF EAT: %s goes for %s %d (%.0f m)', s.tag or s.def.name, STRUCT_EAT[best.kind], best.id, math.sqrt(bd)))
      end
    end
    if s.gun and s.gun.kind == EAT_TYPE then sp.drawn = true end
    local give_up
    if st.target == best.id then
      if not sp.on then sp.on = t; bump(session.actions, 'trooper_eat_structure_on_it') end
      if not sp.drawn and t - sp.on > 6 then give_up = 'no EAT drawn' end
      if req.kick and req.reason ~= 'sentry_safety' then req.kick = false end
    elseif not sp.on and t - sp.t0 > 2 then give_up = 'not picked' end
    if not give_up and t - sp.t0 > 20 then give_up = 'too long' end
    if give_up then
      s.struct_skip = s.struct_skip or {}
      s.struct_skip[best.id] = t + 20
      s.struct = nil
      bump(session.actions, 'trooper_eat_structure_gave_up')
      if TESTER and (GUN.eat_notes or 0) < 20 then
        GUN.eat_notes = (GUN.eat_notes or 0) + 1
        event(string.format('SEAF EAT: %s gave up on %s %d (%s)', s.tag or s.def.name, STRUCT_EAT[best.kind], best.id, give_up))
      end
      return
    end
    local b = {}
    for _, c in ipairs(st.candidates) do if c.id ~= best.id then b[c.id] = true end end
    for k in pairs(req.block) do if k ~= best.id then b[k] = true end end
    req.block = b
    if st.target ~= best.id then
      if not req.kick then req.kick, req.quiet, req.reason = true, true, 'trooper_structure' end
      s.P.ignored = math.max(s.P.ignored or 0, 1)
    end
  end
  -- (test builds, Test 7) research: structures in the game's targeting list near the soldiers, and whether any soldier
  -- lists them as an enemy; and every enemy type the soldiers list that the mod has no armor for (once per type)
  local SR = { t = -1, told = {}, listed = {}, kinds = {}, n = 0 }
  local function struct_research(t)
    if not TESTER or t < SR.t or SR.n >= 40 then return end
    SR.t = t + 1
    local inlist = {}
    for _, s in pairs(sentries) do
      if s.def.trooper then
        for _, c in ipairs(s.last_cands or {}) do
          inlist[c.id] = inlist[c.id] or (c.visible and 'in sight' or 'listed, out of sight')
          if c.kind and not ARMOR[c.kind] and not SR.kinds[c.kind] and SR.n < 40 then
            SR.kinds[c.kind], SR.n = true, SR.n + 1
            event(string.format('SEAF research: soldiers list type %s (%s), no armor known for it', EXT.hexr(c.kind), STRUCT_ALL[c.kind] or 'unnamed'))
          end
        end
      end
    end
    for id, q in pairs(SEAF.structs) do
      if t - q.t < 5 and STRUCT_ALL[q.ty] then
        local p = unit_position(q.unit)
        local nd
        if p then
          for _, s in pairs(sentries) do
            if s.def.trooper then
              local m = unit_position(s.unit)
              if m then local d = math.sqrt((p[1] - m[1]) ^ 2 + (p[2] - m[2]) ^ 2 + (p[3] - m[3]) ^ 2); if not nd or d < nd then nd = d end end
            end
          end
        end
        local l = inlist[id]
        if nd and nd < 100 and ((not SR.told[id]) or (l and not SR.listed[id])) and SR.n < 40 then
          SR.told[id], SR.n = true, SR.n + 1
          if l then SR.listed[id] = true end
          event(string.format('SEAF research: %s %d, %.0f m from the nearest soldier: %s', STRUCT_ALL[q.ty] or EXT.hexr(q.ty), id, nd,
            l and ('a soldier lists it as an enemy (' .. l .. ')') or 'no soldier lists it'))
        end
      end
    end
  end
