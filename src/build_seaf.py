"""Smarter SEAF: built from the Smarter Guard Dogs & Sentries engine (a built SGD core Lua), as before 4.6.4.

The engine's sentry steering is pointed at the SEAF soldiers instead of the sentries: each SEAF soldier run by this
game is steered like a sentry (trooper_gun.lua adds his real gun, the EAT, pings and structures), and nothing else is
touched (no dogs, no sentries, no laser, no in-game options menu). Options (mod manager): Friendly Fire Safety (helldivers /
other troopers), Armor Intelligence, Ping Targeting - each a tiny addon setting flags the core reads every frame.

usage: python3 build_seaf.py <sgd core.lua> <out dir>             release + release Tester
       python3 build_seaf.py <sgd core.lua> <out dir> --test N    numbered test build (Tester, logs in Logs\test)
"""
import sys, os, re, json, struct, zipfile, shutil, subprocess, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hd2_patch import resource_hash, lua_resource, write_lua_archive

VERSION = '1.0.0'
MODULE = 'mods/chef/smarter_seaf'
GUID_LIVE = 'f7c3abbe-902c-41a7-8183-057a6ab15768'
GUID_TEST = '3c821d48-50e2-40c2-85e4-2a4c6f42b870'
HEADER12_72 = bytes.fromhex('00000000000000000000000000000000000000004d0b0600000000000000000000000000000000000000000000000000000000000000000000000000')
KIND = {'75f7e96af7dcd303': 'RIFLEMAN', '6b22ae8e5f669d4f': 'RIFLEMAN', 'a00331f24deef2ee': 'RIFLEMAN', '548136f66f5c9b5c': 'RIFLEMAN',
        'bcfc57848f206106': 'LEADER', '78dabc7344e50234': 'LEADER', '14453b8fcb040099': 'MEDIC', '6fb1e73e00a84329': 'MEDIC', 'c47287d738be91c3': 'MEDIC',
        'bfb5c88d557595d8': 'SPECIALIST', 'a6dcc225e1263606': 'SPECIALIST'}
SOLDIERS = ['75f7e96af7dcd303', '6b22ae8e5f669d4f', 'a00331f24deef2ee', '548136f66f5c9b5c', 'bcfc57848f206106',
            '78dabc7344e50234', '14453b8fcb040099', '6fb1e73e00a84329', 'c47287d738be91c3', 'bfb5c88d557595d8', 'a6dcc225e1263606']


def once(src, old, new, what):
    n = src.count(old)
    assert n == 1, '%s: found %d times' % (what, n)
    return src.replace(old, new)


def transform(src, version, tester, test_build, research):
    # --- identity
    src = once(src, '-- HD2-Addon: mods/chef/smarter_guard_dogs\n', '-- HD2-Addon: %s\n' % MODULE, 'module line')
    head_end = src.index("local VERSION = ")
    head = src[:head_end]
    lines = head.split('\n')
    new_head = [lines[0],
        '-- Smarter SEAF for Helldivers 2 (Bingus Shared Loader v19+ addon).',
        '--  A new brain for the SEAF soldiers run by your game (you host or play solo):',
        '--  * Friendly Fire Safety: they hold fire while you, a teammate, a sentry, another SEAF soldier or a civilian is in their line',
        '--    of fire, and while their gun is pointed at one (staggered, getting up); they pick another enemy instead.',
        '--  * Armor Intelligence: they skip armor they can\'t hurt while there is something else to shoot (and shoot it anyway',
        '--    when there isn\'t); specialists keep their one EAT for Chargers and heavier, and for structures it can destroy.',
        '--  * Ping Targeting: soldiers within 50 m of you go for an enemy you ping, if they can see and hurt it.',
        '--  * Built from the Smarter Guard Dogs & Sentries engine; loads next to it.',
        '-- Keeps a small status log (SmarterSEAF.log) with the other Bingus mods\' logs for bug reports.', '']
    src = '\n'.join(new_head) + src[head_end:]
    src = re.sub(r"local VERSION = '[^']*'", "local VERSION = '%s'" % version, src, count=1)
    src = re.sub(r'local TESTER = (true|false)', 'local TESTER = %s' % ('true' if tester else 'false'), src, count=1)
    src = re.sub(r'local TEST_BUILD = (true|false)', 'local TEST_BUILD = %s' % ('true' if test_build else 'false'), src, count=1)
    src = re.sub(r'local READ_ONLY = (true|false)', 'local READ_ONLY = false', src, count=1)
    # the old SGD file clean-up (moving SGD's own old cache and logs) is not this mod's business
    i = src.index("    pcall(function()\n      local old, new = base .. '\\\\SmarterGuardDogs'")
    j = src.index("    end)\n", i) + len("    end)\n")
    src = src[:i] + src[j:]
    # (comments that name the author: reworded, as SGD's own sanitize step does)
    src = re.sub(r"\bDon\b(?!')", 'the author', src)
    # names: files and globals
    src = src.replace('SmarterGuardDogsAndSentries', 'SmarterSEAF')
    src = src.replace('SmarterGuardDogs', 'SmarterSEAF')
    src = src.replace("'Smarter Guard Dogs & Sentries ' .. VERSION", "'Smarter SEAF ' .. VERSION")
    # no options: everything this mod does is on (the flags the option addons set in SGD)
    src = once(src, "rawset(_G, 'SmarterSEAF', SGD)\n",
        "rawset(_G, 'SmarterSEAF', SGD)\n"
        "-- (Smarter SEAF) the core steers the SEAF soldiers ('Sentries' here means the soldiers the engine steers); the options\n"
        "-- set the rest: Friendly Fire Safety (helldivers: 'Safety', 'Teammates', 'SentrySafety'; other troopers: 'SEAFSafety'),\n"
        "-- Armor Intelligence ('Armor', 'Priority'), Ping Targeting ('Ping'). Read every frame, so load order doesn't matter\n"
        "rawset(_G, 'SmarterSEAFSentries', true)\n",
        'option flags')
    # (1.0.0 review) the unit cache is emptied when it grows past 4096 units: it was only emptied when a guard dog was
    # looked up, which never happens here, so every soldier, weapon and wave of the mission stayed in it
    src = once(src, "local unit_cache = {}\n", "local unit_cache, unit_cache_n = {}, 0\n", 'unit cache n')
    src = once(src, "  unit_cache[id] = obj\n  return obj, h\n",
        "  unit_cache_n = unit_cache_n + 1\n"
        "  if unit_cache_n > 4096 then unit_cache, unit_cache_n = {}, 0 end   -- (Smarter SEAF 1.0.0 review: bounded)\n"
        "  unit_cache[id] = obj\n  return obj, h\n", 'unit cache cap')
    # (1.0.0 patch-proofing) the two game lists only this mod uses - the weapon in each soldier's hands (wielder) and the
    # ping marks (spotted) - are found like the engine's others: their place in the known build, or a search of the
    # game's code after an update (3 patterns each from the 2026-09-24 game.dll; the majority wins). Optional: without
    # one, only the part that needs it stays off
    src = once(src, "    weapons = { { p = '488b3d????????458bda8b77388b6f40', disp_at = 3, size = 7 },",
        "    -- (Smarter SEAF) the weapon wielder list (464-byte rows at +0x60: the first word is the weapon in his hands) and the\n"
        "    -- spot list (24-byte rows at +0x40: the ping marks)\n"
        "    wielder = { " + ', '.join("{ p = '%s', disp_at = 3, size = 7 }" % p for p in WIELDER_PATS) + " },\n"
        "    spotted = { " + ', '.join("{ p = '%s', disp_at = 3, size = 7 }" % p for p in SPOTTED_PATS) + " },\n"
        "    weapons = { { p = '488b3d????????458bda8b77388b6f40', disp_at = 3, size = 7 },", 'patterns')
    src = once(src, "behaviours = 53634880, perception = 53634376, registry = 53636280, clock = 53633864, weapons = 53636320, heatbar = 53636424 },\n  owner_index",
        "behaviours = 53634880, perception = 53634376, registry = 53636280, clock = 53633864, weapons = 53636320, heatbar = 53636424, wielder = %d, spotted = %d },\n  owner_index" % (0x3326420, 0x3326450), 'known')
    # the option log lines in this mod's words (and Ping Targeting's)
    src = once(src, "  OPT.safety = function() return flag('SmarterSEAFSafety', 'safety for you', ': your dogs and sentries may fire through you') end\n",
        "  OPT.safety = function() return flag('SmarterSEAFSafety', 'friendly fire safety: helldivers', ': SEAF soldiers may fire through you and your teammates') end\n", 'opt safety')
    src = once(src, "  OPT.sentry_safety = function() return flag('SmarterSEAFSentrySafety', 'sentry safety', ': your sentries may fire through other sentries') end\n",
        "  OPT.sentry_safety = function() return flag('SmarterSEAFSentrySafety', 'friendly fire safety: sentries', ': SEAF soldiers may fire through sentries') end\n", 'opt sentry safety')
    src = once(src, "  OPT.seaf_safety = function() return flag('SmarterSEAFSEAFSafety', 'SEAF safety', ': your dog and sentries may fire through SEAF soldiers and civilians') end\n",
        "  OPT.seaf_safety = function() return flag('SmarterSEAFSEAFSafety', 'friendly fire safety: other troopers', ': SEAF soldiers may fire through each other and civilians') end\n", 'opt seaf safety')
    src = once(src, "  OPT.priority = function() return flag('SmarterSEAFPriority', 'target prioritization', ': the game decides the order') end\n",
        "  OPT.priority = function() return flag('SmarterSEAFPriority', 'target prioritization', ': the game decides the order') end\n"
        "  OPT.ping = function() return flag('SmarterSEAFPing', 'ping targeting', ': soldiers leave your pings alone') end\n", 'opt ping')
    src = once(src, '  menu_step()\n', '  -- (Smarter SEAF: no in-game options menu)\n', 'menu step')
    i = src.index("-- (4.5.3) Bingus' Mod Options Menu (optional")
    j = src.index('end)()\n', i) + len('end)()\n')
    assert src[i:j].count('local menu_step = (function()') == 1, 'menu block'
    src = src[:i] + src[j:]
    # the SEAF soldiers are what gets steered
    troopers = ("local SENTRY_BY_TYPE = {}\nfor _, d in ipairs(SENTRIES) do d.sentry = true; SENTRY_BY_TYPE[d.type] = d end\n"
        "-- (Smarter SEAF) the SEAF soldiers (every SEAF Soldier entity) are steered like a sentry, one kind per loadout (game data):\n"
        "-- riflemen and squad leaders: AR-23P Liberator Penetrator (armor pen 3, Medium); medics: 12x25mm SMG (pen 2, Light);\n"
        "-- specialists: 8x60mm rifle (pen 3) and one EAT-17 Expendable Anti-Tank (lat_oneshot: one 75mm HEAT shot, pen 6), so they may take on heavy armor.\n"
        "-- 'pen': what Armor Intelligence lets each kind shoot at; 'sentry': no dropships (none of them can hurt one).\n"
        "-- 'muzzle_up': a rifle at chest height; no barrel to follow\n"
        "-- 'prefer' (Target Prioritization, Test 3): the specialists go for the heaviest armor first (their EAT-17:\n"
        "-- Chargers and heavier), everyone else for the closest enemy first\n"
        "local function trooper(name, pen, prefer) return { name = name, trooper = true, sentry = true, pen = pen, prefer = prefer, line = 0.45, spread = 0.015, sweep = true, muzzle_up = 1.4 } end\n"
        "local RIFLEMAN, LEADER, MEDIC, SPECIALIST = trooper('SEAF Soldier', 3, 'near'), trooper('SEAF Squad Leader', 3, 'near'), trooper('SEAF Medic', 2, 'near'), trooper('SEAF Specialist', 6, 'heavy')\n"
        "local SPECIALIST_SPENT = trooper('SEAF Specialist (EAT used)', 3, 'near')\n"
        "SPECIALIST.eat, SPECIALIST_SPENT.eat = true, false\n"
        "SPECIALIST.base_name, SPECIALIST_SPENT.base_name = SPECIALIST.name, SPECIALIST.name   -- (a soldier found again is matched by his type)\n"
        "local TROOPER_BY_TYPE = {}\n"
        "for h, d in pairs({ %s }) do TROOPER_BY_TYPE[type_hash(h)] = d end\n" % ', '.join("['%s'] = %s" % (h, KIND[h]) for h in SOLDIERS))
    src = once(src, "local SENTRY_BY_TYPE = {}\nfor _, d in ipairs(SENTRIES) do d.sentry = true; SENTRY_BY_TYPE[d.type] = d end\n", troopers, 'trooper defs')
    src = once(src, "        local def = not seaf_only and SENTRY_BY_TYPE[ty] or nil\n",
        "        -- (Smarter SEAF) 'pdef': a sentry (a body to keep clear of); 'def': a SEAF soldier to steer\n"
        "        local pdef = not seaf_only and SENTRY_BY_TYPE[ty] or nil\n"
        "        local def = not seaf_only and TROOPER_BY_TYPE[ty] or nil\n", 'scan def')
    src = once(src, "        if not def and SEAF.types[ty] then\n", "        if SEAF.types[ty] then\n", 'scan seaf')
    src = once(src, "          if not q or q.unit ~= unit then SEAF.troops[id] = { unit = unit, civ = SEAF.types[ty] == 'civilian' } end\n",
        "          if not q or q.unit ~= unit then SEAF.troops[id] = { unit = unit, civ = SEAF.types[ty] == 'civilian', ty = ty, mine = EXT.is_local(e) } end\n", 'seaf troop')
    src = once(src, "        if def and not (def.vehicle or def.mount) then\n", "        if pdef and not (pdef.vehicle or pdef.mount) then\n", 'posts if')
    src = once(src, "          if not q or q.unit ~= unit or q.def ~= def then posts[id] = { unit = unit, def = def, sid = id, mine = EXT.is_local(e) } end\n",
        "          if not q or q.unit ~= unit or q.def ~= pdef then posts[id] = { unit = unit, def = pdef, sid = id, mine = EXT.is_local(e) } end\n", 'posts set')
    src = once(src, "        elseif not def and not seaf_only and EXT.is_local(e) and type_ai[ty] == nil then\n",
        "        elseif not def and not pdef and not seaf_only and EXT.is_local(e) and type_ai[ty] == nil then\n", 'unknown agents')
    # (Test 2) his friends in his list are never his enemies
    src = once(src, "    st.deadline = u64(rec, 152)\n",
        "    if s.def.trooper then\n"
        "      -- (Smarter SEAF) his friends in his list (helldivers, SEAF soldiers, civilians - who he follows, heals or covers) are\n"
        "      -- never treated as enemies: left out, so never hidden from him; while one is his 'target' he is left alone\n"
        "      local keep, friend = {}, false\n"
        "      for _, c in ipairs(st.candidates) do\n"
        "        if c.kind == AVATAR_TYPE or (c.kind and SEAF.types[c.kind]) then\n"
        "          if c.id == st.target then friend = true end\n"
        "        else keep[#keep + 1] = c end\n"
        "      end\n"
        "      st.candidates = keep\n"
        "      if friend then st.friend_target, st.target = st.target, 0 end\n"
        "    end\n"
        "    st.deadline = u64(rec, 152)\n", 'friends')
    # (Test 2) a soldier ignores the ask to choose again: his AI record's target is cleared
    src = once(src, "        if not write(s.rec_addr + 152, u64bytes(now)) then stats.write_failures = stats.write_failures + 1 end\n      end\n    end\n",
        "        if not write(s.rec_addr + 152, u64bytes(now)) then stats.write_failures = stats.write_failures + 1 end\n      end\n    end\n"
        "    -- (Smarter SEAF) a SEAF soldier doesn't choose again when asked, the way a sentry does: a Test 1 log had him hold his aim on\n"
        "    -- an enemy hidden from him without firing. From his second ask for the same enemy on, his AI record's target is\n"
        "    -- cleared so his AI chooses again (only enemies are ever asked about; at most every 0.5 s)\n"
        "    if req.kick and s.def.trooper and st.target ~= 0 and (s.P.ignored or 0) >= 1 and os.clock() >= (s.P.clear_t or 0) then\n"
        "      local r = read(s.rec_addr + 24, 4)\n"
        "      if r and u32(r, 0) == st.target then\n"
        "        s.P.clear_t = os.clock() + 0.5\n"
        "        if SGD.seaf_trace then pcall(SGD.seaf_trace, s, st, req.reason) end\n"
        "        if write(s.rec_addr + 24, pack32(0)) then bump(session.actions, 'trooper_target_cleared') else stats.write_failures = stats.write_failures + 1 end\n"
        "      end\n"
        "    end\n", 'clear target')
    # (Test 3) a soldier is never let off: his target is cleared instead (sentries back off after two ignored asks)
    src = once(src, "P = s.P, tag = s.tag, t = os.clock(), name = s.def.name, unit = s.unit, why = why,",
        "P = s.P, tag = s.tag, t = os.clock(), name = s.def.base_name or s.def.name, unit = s.unit, why = why, eat_seen = s.eat_seen, eat_gone = s.eat_gone, def = s.def, eat_hold = s.eat_hold, ping_skip = s.ping_skip, struct_skip = s.struct_skip, gun = s.gun, gun_wid = s.gun_wid,", 'remember eat')
    src = once(src, "local old = s and { heat = s.heat, heat_measured = s.heat_measured, meter_ok_t = s.meter_ok_t, P = s.P, tag = s.tag, t = t }",
        "local old = s and { heat = s.heat, heat_measured = s.heat_measured, meter_ok_t = s.meter_ok_t, P = s.P, tag = s.tag, t = t, eat_seen = s.eat_seen, eat_gone = s.eat_gone, def = s.def, eat_hold = s.eat_hold, ping_skip = s.ping_skip, struct_skip = s.struct_skip, gun = s.gun, gun_wid = s.gun_wid }", 'old eat')
    src = once(src, "    ns.tag = old.tag\n",
        "    ns.tag = old.tag\n"
        "    -- (Smarter SEAF, 1.0.0 review) a specialist keeps what is known about his EAT when his records move (he was put back\n"
        "    -- to heavy-first with his rifle for the rest of the mission); his kind follows from it on his next step\n"
        "    ns.eat_seen, ns.eat_gone = old.eat_seen, old.eat_gone\n"
        "    -- ((1.0.0 review) and the rest of what he was doing: an EAT he was let go of stays let go, a ping or structure he\n"
        "    -- gave up on stays given up on, and the weapon in his hands is known)\n"
        "    ns.eat_hold, ns.ping_skip, ns.struct_skip, ns.gun, ns.gun_wid = old.eat_hold, old.ping_skip, old.struct_skip, old.gun, old.gun_wid\n"
        "    if old.def and old.def.base_name and old.def.base_name == ns.def.base_name then ns.def = old.def end\n", 'carry eat')
    src = once(src, "    if P.ignored >= 2 and reason ~= 'sentry_safety' then\n", "    if P.ignored >= 2 and reason ~= 'sentry_safety' and not s.def.trooper then\n", 'no back-off')
    # (Test 6) a soldier's own gun never runs dry (only the EAT does): armor he can't hurt is skipped only while
    # something he can hurt is in sight to shoot instead. With nothing else about he shoots at it anyway (Test 5:
    # with their EATs spent they stood around beside a Charger)
    src = once(src, "    -- fire spreading (Laser Sentry, like the Rover): once one is burning it moves on to an unlit one.",
        "    -- (Smarter SEAF) a soldier skips armor he can't hurt only while there is something else to shoot\n"
        "    if def.trooper and N ~= NONE then\n"
        "      local other = false\n"
        "      for _, c in ipairs(cands) do\n"
        "        local id = c.id\n"
        "        if c.visible and open(c) and in_play(c, st) and not N[id] and not U[id] and not O[id] and not D[id] and not HV[id] then other = true; break end\n"
        "      end\n"
        "      if not other then N = NONE end\n"
        "    end\n"
        "    -- fire spreading (Laser Sentry, like the Rover): once one is burning it moves on to an unlit one.", 'armor only with another target')
    # (Test 4) each soldier's gun (trooper_gun.lua, inside the sentry part) and what it means each frame
    src = once(src, "  local function sentry_step(s, st, bodies, t, people, me)\n",
        open(os.path.join(HERE, 'trooper_gun.lua')).read() + "  local function sentry_step(s, st, bodies, t, people, me)\n", 'gun module')
    src = once(src, "  local function sentry_step(s, st, bodies, t, people, me)\n    local req = plan_sentry(s, st, bodies, t, people)\n",
        "  local function sentry_step(s, st, bodies, t, people, me)\n"
        "    local pb = bodies\n"
        "    if s.def.trooper then\n"
        "      -- (Smarter SEAF) four times a second: the weapon in his hands, and for a specialist whether he still has his EAT\n"
        "      if gun_known() then pcall(gun_track, s, t) end\n"
        "      -- a specialist whose EAT is gone fights like a rifleman (and as a specialist again once he has one)\n"
        "      if s.def.eat ~= nil then\n"
        "        local want = (s.eat_gone and t - s.eat_gone > 1) and SPECIALIST_SPENT or SPECIALIST\n"
        "        if s.def ~= want then\n"
        "          s.def = want\n"
        "          session.sentries[want.name] = session.sentries[want.name] or { placed = 0, out = 0, targeted = 0, stops = 0, mate_stops = 0, armour = 0 }\n"
        "          session.eat_swaps = (session.eat_swaps or 0) + 1\n"
        "          if session.eat_swaps <= 20 then event(string.format('SEAF: %s %s', s.tag or 'a specialist', want.eat and 'has an EAT again: heavy armor first' or 'used his EAT: fights like a rifleman now')) end\n"
        "        end\n"
        "      end\n"
        "      -- (1.0.0 review) only the friends that could be in his line of fire: within reach of the enemies he lists, plus a\n"
        "      -- margin (before, every soldier checked every enemy against every friend within 250 m)\n"
        "      local B = st.base\n"
        "      if B and #bodies > 0 then\n"
        "        local far2 = 0\n"
        "        for _, c in ipairs(st.candidates) do if c.d2 and c.d2 > far2 then far2 = c.d2 end end\n"
        "        local r = math.sqrt(far2) + 6\n"
        "        local r2 = r * r\n"
        "        -- ((1.0.0 review) his own list, emptied and refilled: no new table every frame; plan_sentry only reads it)\n"
        "        pb = s.pb\n"
        "        if pb then for k = #pb, 1, -1 do pb[k] = nil end else pb = {}; s.pb = pb end\n"
        "        for _, b in ipairs(bodies) do\n"
        "          local a = b.at\n"
        "          if not a or (a[1] - B[1]) ^ 2 + (a[2] - B[2]) ^ 2 + (a[3] - B[3]) ^ 2 <= r2 then pb[#pb + 1] = b end\n"
        "        end\n"
        "      end\n"
        "    end\n"
        "    local req = plan_sentry(s, st, pb, t, people)\n"
        "    if s.def.trooper then\n"
        "      s.cur_target, s.cur_kind, s.last_cands = st.target, st.current and st.current.kind, st.candidates\n"
        "      -- (Friendly Fire Safety) his gun pointing at a friend the options protect (staggered, getting up, swinging round): every\n"
        "      -- enemy hidden from him for that moment and 0.3 s after, so he can't fire ('bodies' holds only those friends)\n"
        "      local ok, fb = pcall(gun_on_friend, s, st, bodies, t)\n"
        "      if ok and fb then\n"
        "        s.gun_hold = t + 0.3\n"
        "        bump(session.actions, st.target ~= 0 and 'trooper_gun_on_friend (with a target)' or 'trooper_gun_on_friend (no target)')\n"
        "        if TESTER and (s.P.gun_notes or 0) < 3 then\n"
        "          s.P.gun_notes = (s.P.gun_notes or 0) + 1\n"
        "          event(string.format('SEAF gun: %s pointed at %s (AI step %d, target %d): fire blocked', s.tag or s.def.name, fb.civ and 'a civilian' or fb.seaf and 'a SEAF soldier' or fb.mate and 'a teammate' or 'you', st.node, st.target))\n"
        "        end\n"
        "      end\n"
        "      -- (Ping Targeting, Armor Intelligence) a pinged enemy, or a structure for his EAT: everything else hidden from him\n"
        "      if not ((s.gun_hold or 0) > t) then pcall(ping_step, s, st, t, req, me); pcall(struct_step, s, st, t, req) end\n"
        "      if TESTER then pcall(struct_research, t) end\n"
        "      pcall(struct_never, s, st, req)\n"
        "      -- (Armor Intelligence) a specialist keeps his EAT for heavy armor: lighter enemies hidden while it is in his hands\n"
        "      local oke, light = pcall(eat_hold, s, st, t)\n"
        "      if oke and light and next(light) then\n"
        "        local b = {}\n"
        "        for k in pairs(req.block) do b[k] = true end\n"
        "        for k in pairs(light) do b[k] = true end\n"
        "        req.block = b\n"
        "        if light[st.target] and not req.kick then req.kick, req.quiet, req.reason = true, true, 'trooper_eat'; s.P.ignored = math.max(s.P.ignored or 0, 1) end\n"
        "      end\n"
        "      if (s.gun_hold or 0) > t then\n"
        "        local b = {}\n"
        "        for k in pairs(req.block) do b[k] = true end\n"
        "        for _, c in ipairs(st.candidates) do b[c.id] = true end\n"
        "        -- (1.0.0 review) the safety's own ask to choose again still goes through; any other is put off meanwhile\n"
        "        req.block = b\n"
        "        if req.reason ~= 'sentry_safety' then req.kick = false end\n"
        "      end\n"
        "    end\n", 'step hooks')
    # each soldier leaves out his own body; soldiers further off are steered too
    # (Test 7) structures in the targeting list (fabricators, bug holes...): kept with when they were last seen, for the
    # specialists' EAT and the research log
    src = once(src, "        -- (4.6.5 Sentry Safety: every sentry out, whoever's; not the guns on a resupply pod or the Supply FRV)\n",
        "        if SEAF.struct_types and SEAF.struct_types[ty] then SEAF.structs[u32(e, 8)] = { unit = u32(e, 12), ty = ty, t = t } end   -- (Tester research only)\n"
        "        -- (4.6.5 Sentry Safety: every sentry out, whoever's; not the guns on a resupply pod or the Supply FRV)\n", 'structures in scan')
    src = once(src, "    for id in pairs(SEAF.troops) do if not fseen[id] then SEAF.troops[id] = nil end end\n",
        "    for id in pairs(SEAF.troops) do if not fseen[id] then SEAF.troops[id] = nil end end\n"
        "    if SEAF.structs then for id, q in pairs(SEAF.structs) do if t - q.t > 10 then SEAF.structs[id] = nil end end end\n", 'prune structs')
    n = src.count("SEAF.troops, SEAF.list = {}, nil")
    assert n == 2, 'mission reset: %d' % n
    src = src.replace("SEAF.troops, SEAF.list = {}, nil", "SEAF.troops, SEAF.list, SEAF.structs = {}, nil, {}")
    src = once(src, "reach = 100, list = nil, t = -1, types = {} }", "reach = 250, list = nil, t = -1, types = {} }", 'seaf reach')
    i = src.index('  local function seaf_bodies(t, me)')
    j = src.index('\n  end\n', i)
    body = src[i:j]
    body = once(body, '    for _, q in pairs(SEAF.troops) do\n      local p = unit_position(q.unit)', '    for qid, q in pairs(SEAF.troops) do\n      local p = unit_position(q.unit)', 'bodies loop')
    body = once(body, 'extra = SEAF.margin, seaf = true, civ = q.civ }', 'extra = SEAF.margin, seaf = true, civ = q.civ, sid = qid }', 'body sid')
    body = once(body, 'extra = SEAF.margin, seaf = true, civ = q.civ, lead = true }', 'extra = SEAF.margin, seaf = true, civ = q.civ, lead = true, sid = qid }', 'lead sid')
    src = src[:i] + body + src[j:]
    src = once(src, "  TEAM.seaf_bodies = seaf_bodies",
        "  SGD.seaf_state = function() return SEAF.troops, sentries end   -- (Smarter SEAF research: the soldiers listed, the ones steered)\n  TEAM.seaf_bodies = seaf_bodies", 'expose')
    # the research module instead of SGD's ping probe
    i = src.index('-- (4.6.6 Test 2+, research only')
    i = src.rindex('-- ====', 0, i)
    j = src.index('-- Main loop')
    j = src.rindex('-- ====', 0, j)
    src = src[:i] + (open(os.path.join(HERE, 'seaf_research.lua')).read() if research else '') + src[j:]
    return src


# (1.0.0) the options (mod manager), in this order: the mod, Friendly Fire Safety (who they never shoot through), Armor
# Intelligence, Ping Targeting. Each optional part is a tiny addon setting flags the core reads every frame
CORE_DIR = 'Smarter SEAF'
HD_DIR, TR_DIR, ARMOR_DIR, PING_DIR = 'Friendly Fire Safety - Helldivers', 'Friendly Fire Safety - Other Troopers', 'Armor Intelligence', 'Ping Targeting'
ADDONS = {
    HD_DIR: ('mods/chef/smarter_seaf_helldivers', 'Friendly Fire Safety, helldivers: SEAF soldiers never shoot through you, your teammates or your sentries.',
             ['Safety', 'Teammates', 'SentrySafety']),
    TR_DIR: ('mods/chef/smarter_seaf_troopers', 'Friendly Fire Safety, other troopers: SEAF soldiers never shoot through other SEAF soldiers or civilians.',
             ['SEAFSafety']),
    ARMOR_DIR: ('mods/chef/smarter_seaf_armor', 'Armor Intelligence: armor they can\'t hurt is left for later, specialists keep their EAT for heavy armor.',
                ['Armor', 'Priority']),
    PING_DIR: ('mods/chef/smarter_seaf_ping', 'Ping Targeting: soldiers within 50 m of you go for the enemy you ping.', ['Ping']),
}
ARCHIVE = '9ba626afa44a3aa3.patch_0'
# (1.0.0 patch-proofing) code patterns for the two lists only Smarter SEAF uses (each matches once in the 2026-09-24
# game.dll and gives its address; the first of each also holds the list's row size and place, so a changed layout isn't found)
WIELDER_PATS = ['4c8b15????????75??b8ffffffff8bc84869c1d00100004903426048', '488b1d????????8b40083bc274??448b5b38448bd68b7b400faff845',
                '488b0d????????448bce448b59388b59400fafda458d73ff4585db74']
SPOTTED_PATS = ['4c8b15????????75??b8ffffffff8bc8498b4240488d1449488d04d0', '488b0d????????33db448bc3448b4928448b5930440fafd8458d71ff',
                '4c8b05????????33d2458b4828458b5030440fafd1458d69ff4585c9']
DESC = ('A new brain for the SEAF soldiers run by your game (you host or play solo). They don\'t shoot through you, your teammates, '
        'other SEAF soldiers or civilians, hold fire while staggered or getting up, skip armor they can\'t hurt while something else '
        'is around, keep their EAT for Chargers and heavier, and go for the enemies you ping. Each part can be turned on or off in the '
        'options. Requires Bingus Shared Loader v19 or newer.')
OPTIONS = [
    {'Name': 'Smarter SEAF', 'Description': 'The SEAF soldiers\' new brain. Keep this on; the parts below can each be turned on or off.',
     'Image': 'options/option_core.png', 'Include': [CORE_DIR]},
    {'Name': 'Friendly Fire Safety', 'Description': 'Who SEAF soldiers never shoot through: they hold fire while one is in their line of fire or '
     'their gun is pointed at one (staggered or getting up), and pick another enemy. Turn off at your own risk: they will fire '
     'through anyone, as in the base game. Everything else keeps working.',
     'Image': 'options/option_friendly_fire.png',
     'SubOptions': [
         {'Name': 'Helldivers and other troopers', 'Description': 'Protects you, your teammates and your sentries, other SEAF soldiers and civilians.',
          'Image': 'options/option_friendly_fire.png', 'Include': [HD_DIR, TR_DIR]},
         {'Name': 'Only helldivers', 'Description': 'Protects you, your teammates and your sentries; they may fire through other SEAF soldiers and civilians.',
          'Image': 'options/option_helldivers.png', 'Include': [HD_DIR]},
         {'Name': 'Only other troopers', 'Description': 'Protects other SEAF soldiers and civilians; they may fire through helldivers and sentries.',
          'Image': 'options/option_troopers.png', 'Include': [TR_DIR]},
     ]},
    {'Name': 'Armor Intelligence', 'Description': 'SEAF soldiers know what their guns can hurt: armor they can\'t get through is left for '
     'later while something else is around (and shot at anyway when nothing else is), and specialists keep their one EAT for Chargers '
     'and heavier, and for structures it can destroy. Turn off to leave targets to the game. Everything else keeps working.',
     'Image': 'options/option_armor.png', 'Include': [ARMOR_DIR]},
    {'Name': 'Ping Targeting', 'Description': 'SEAF soldiers within 50 m of you go for the enemy you ping, if they can see it and hurt it, '
     'for up to 20 seconds. Turn off to leave your pings alone. Everything else keeps working.',
     'Image': 'options/option_ping.png', 'Include': [PING_DIR]},
]


def addon_lua(module, text, flags):
    return ('-- HD2-Addon: %s\n-- Smarter SEAF - %s\n' % (module, text)
            + ''.join("rawset(_G, 'SmarterSEAF%s', true)\n" % f for f in flags))


def package(src, zpath, name, guid, desc):
    stage = os.path.join(os.path.dirname(zpath), 'stage'); shutil.rmtree(stage, ignore_errors=True); os.makedirs(stage)
    parts = [(CORE_DIR, MODULE, src)] + [(d, m, addon_lua(m, t, f)) for d, (m, t, f) in ADDONS.items()]
    for folder, module, lua in parts:
        os.makedirs(os.path.join(stage, folder))
        write_lua_archive(os.path.join(stage, folder, ARCHIVE), [(resource_hash(module), lua_resource(lua.encode()))], HEADER12_72)
        for ext in ('.gpu_resources', '.stream'): open(os.path.join(stage, folder, ARCHIVE + ext), 'wb').close()
    man = {'Version': 1, 'Guid': guid, 'Name': name, 'Description': desc, 'IconPath': 'thumbnail.png', 'Options': OPTIONS}
    json.dump(man, open(os.path.join(stage, 'manifest.json'), 'w'), indent=2)
    shutil.copy(os.path.join(HERE, 'thumbnail.png'), os.path.join(stage, 'thumbnail.png'))
    os.makedirs(os.path.join(stage, 'options'))
    for img in sorted({o['Image'] for o in OPTIONS} | {x['Image'] for o in OPTIONS for x in o.get('SubOptions', [])}):
        shutil.copy(os.path.join(HERE, img), os.path.join(stage, img))
    if os.path.exists(zpath): os.remove(zpath)
    # (1.0.0) a fixed date and order in the zip, so the same source always makes the same zip, byte for byte
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for f in sorted(files):
                p = os.path.join(root, f)
                zi = zipfile.ZipInfo(os.path.relpath(p, stage).replace(os.sep, '/'), date_time=(2026, 1, 1, 0, 0, 0))
                zi.compress_type, zi.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                z.writestr(zi, open(p, 'rb').read())
    shutil.rmtree(stage, ignore_errors=True)
    print(zpath, name, hashlib.sha256(open(zpath, 'rb').read()).hexdigest()[:16])


def main():
    core, outdir = sys.argv[1], sys.argv[2]
    test = int(sys.argv[sys.argv.index('--test') + 1]) if '--test' in sys.argv else None
    os.makedirs(outdir, exist_ok=True)
    lj = os.environ.get('LUAJIT', os.path.join(HERE, '..', 'kit', 'luajit', 'src', 'luajit'))
    # a numbered test build (Tester, research, logs in Logs\test), or the release and the release Tester
    builds = [(True, test)] if test else [(False, None), (True, None)]
    for tester, n in builds:
        version = VERSION + (' Test %d' % n if n else '') + (' (tester)' if tester else '')
        src = transform(open(core).read(), version, tester, n is not None, n is not None)
        lua = os.path.join(outdir, 'smarter_seaf%s.lua' % ('' if n else ('_tester' if tester else '_release')))
        open(lua, 'w').write(src)
        # sanitize: nothing from the author's computer
        for bad in ['Don', 'Users\\\\', 'C:\\\\', 'D:\\\\', 'SteamLibrary'] + os.environ.get('SANITIZE_EXTRA', '').split():
            assert bad not in src or bad == 'Don' and not re.search(r"\bDon\b(?!')", src), 'sanitize: ' + bad
        subprocess.check_call([lj, '-e', 'assert(loadfile(%r))' % lua])
        name = 'Smarter SEAF %s' % VERSION + (' Test %d' % n if n else '') + (' (Tester)' if tester else '')
        zname = 'Smarter-SEAF-%s' % VERSION + ('-Test-%d' % n if n else '') + ('-Tester' if tester and not n else '') + '.zip'
        desc = DESC
        if n: desc = 'TEST BUILD %d (extra research logging). ' % n + desc
        elif tester: desc = 'TESTER BUILD: the release plus extra test logging. Install instead of the release, not next to it. ' + desc
        package(src, os.path.join(outdir, zname), name, GUID_TEST if tester else GUID_LIVE, desc)


if __name__ == '__main__':
    main()
