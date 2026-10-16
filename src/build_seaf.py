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

VERSION = '1.0.3'
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
    src = once(src, "    if next(unit_cache) then unit_cache = {} end", "    if next(unit_cache) then unit_cache, unit_cache_n = {}, 0 end", 'unit cache wipe 1')
    src = once(src, "      ctx, ctx_until, unit_cache, reg_rows = c, t + LOCATE_SECONDS, {}, {}\n", "      ctx, ctx_until, unit_cache, reg_rows = c, t + LOCATE_SECONDS, {}, {}\n      unit_cache_n = 0\n", 'unit cache wipe 2')
    # (1.0.1 review) whether the layout is the known build's (the AI step numbers are from it); a scanned one is not
    src = once(src, "    exe_units = ebase + L.exe_units, g = {}, gbase = gbase }\n", "    exe_units = ebase + L.exe_units, g = {}, gbase = gbase, known = (L == KNOWN) }\n", 'known flag')
    # (1.0.1 review) the wielder and spot lists are taken only where their first pattern - the one holding the record
    # layout this mod reads - agrees: after an update that changed the layout they are not found (their parts off)
    src = once(src, "        local v = base_rva + o + p.size + si32(txt, o + p.disp_at)\n",
        "        local v = base_rva + o + p.size + si32(txt, o + p.disp_at)\n        if p.layout then layout_v = v end\n", 'layout vote')
    src = once(src, "  local function target(txt, base_rva, pats, what)\n    local votes, order = {}, {}\n",
        "  local function target(txt, base_rva, pats, what)\n    local votes, order, layout_v = {}, {}, nil\n", 'layout local')
    src = once(src, "    assert(not tie, what .. ': patterns disagree')\n",
        "    assert(not tie, what .. ': patterns disagree')\n"
        "    for _, p in ipairs(pats) do if p.layout then assert(layout_v == val, what .. ': its record layout is not the one this mod knows (game update?)') end end\n", 'layout check')
    # (1.0.1 review) where the core hides enemies still aboard a dropship from a soldier, his pings and structures do too
    src = once(src, "              if (p[1] - q[1]) ^ 2 + (p[2] - q[2]) ^ 2 <= reach2 and dz >= -DROPSHIP.below and dz <= DROPSHIP.above then D = put(D, c.id); break end\n            end\n          end\n        end\n      end\n    end\n",
        "              if (p[1] - q[1]) ^ 2 + (p[2] - q[2]) ^ 2 <= reach2 and dz >= -DROPSHIP.below and dz <= DROPSHIP.above then D = put(D, c.id); break end\n            end\n          end\n        end\n      end\n    end\n"
        "    st.aboard = D ~= NONE and D or nil   -- (Smarter SEAF 1.0.1: read by ping and structure steering)\n", 'aboard')
    # (1.0.0 patch-proofing) the two game lists only this mod uses - the weapon in each soldier's hands (wielder) and the
    # ping marks (spotted) - are found like the engine's others: their place in the known build, or a search of the
    # game's code after an update (3 patterns each from the 2026-09-24 game.dll; the majority wins). Optional: without
    # one, only the part that needs it stays off
    src = once(src, "    weapons = { { p = '488b3d????????458bda8b77388b6f40', disp_at = 3, size = 7 },",
        "    -- (Smarter SEAF) the weapon wielder list (464-byte rows at +0x60: the first word is the weapon in his hands) and the\n"
        "    -- spot list (24-byte rows at +0x40: the ping marks)\n"
        "    wielder = { " + ', '.join("{ p = '%s', disp_at = 3, size = 7%s }" % (p, ', layout = true' if i == 0 else '') for i, p in enumerate(WIELDER_PATS)) + " },\n"
        "    spotted = { " + ', '.join("{ p = '%s', disp_at = 3, size = 7%s }" % (p, ', layout = true' if i == 0 else '') for i, p in enumerate(SPOTTED_PATS)) + " },\n"
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
        "      if A and A.g.weapons then pcall(gun_track, s, t) end   -- ((1.0.1 review) the spent-EAT check needs only the weapon list)\n"
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
    # (1.0.3, performance) map lookups from a per-frame snapshot: a component map looked up 3+ times in one frame is
    # read whole, once, into its own buffer (one system call instead of one per lookup and probe); its header is read
    # once a frame. Reset each frame and after the game's update (sentry_after). Tester: reads per frame in the log
    # ((Test 4) declared before the log writer: Test 3 declared it after, so the log's cost section hit a nil global and
    # the log was never rewritten once the frame timing had started)
    src = once(src, "local function write_log_to(f)\n",
        "local RDN = { n = 0, b = 0, snaps = 0, snapb = 0 }   -- ((1.0.3) Tester: memory reads made, and map snapshots)\n"
        "local function write_log_to(f)\n",
        'read counter')
    src = once(src, "    if K32.SgdReadProcessMemory(PROCESS, ffi.cast(PVOID, addr), buf, n, DONE) == 0 or DONE[0] ~= n then return nil end\n",
        "    if TESTER then RDN.n, RDN.b = RDN.n + 1, RDN.b + n end   -- ((1.0.3) Tester log only)\n"
        "    if K32.SgdReadProcessMemory(PROCESS, ffi.cast(PVOID, addr), buf, n, DONE) == 0 or DONE[0] ~= n then return nil end\n",
        'read count')
    src = once(src, "local function map_lookup(addr, key, max_capacity, header, soft)\n  local h = header or rd(addr, 20, 'map header')\n",
        "-- ((1.0.3) a component map looked up 3 or more times in one frame - one lookup per soldier and enemy - is read whole\n"
        "-- into its own buffer once that frame and probed there: one system call (~2-3 us each) instead of two or more per\n"
        "-- lookup. Snapshots are dropped every frame and after the game's update; at most 64 maps, capacity up to 16384)\n"
        "local MAPS = { gen = 0, n = 0, PU32 = ffi.typeof('const uint32_t *') }\n"
        "local function map_snapshot(addr, slots, cap)\n"
        "  local S = MAPS[addr]\n"
        "  if not S then\n"
        "    if MAPS.n >= 64 then return nil end\n"
        "    S = { gen = -1, ugen = -1, uses = 0 }; MAPS[addr] = S; MAPS.n = MAPS.n + 1\n"
        "  end\n"
        "  if S.gen == MAPS.gen and S.slots == slots and S.cap == cap then return S.p end\n"
        "  if S.ugen ~= MAPS.gen then S.ugen, S.uses = MAPS.gen, 0 end\n"
        "  S.uses = S.uses + 1\n"
        "  if S.uses < 3 or cap > 16384 then return nil end\n"
        "  local size = cap * 8\n"
        "  if not S.buf or S.size < size then S.buf, S.size = ffi.new('uint8_t[?]', size), size end\n"
        "  if TESTER then RDN.snaps, RDN.snapb = RDN.snaps + 1, RDN.snapb + size end\n"
        "  if K32.SgdReadProcessMemory(PROCESS, ffi.cast('const void *', slots), S.buf, size, DONE) == 0 or DONE[0] ~= size then S.gen = -1; return nil end\n"
        "  S.gen, S.slots, S.cap, S.p = MAPS.gen, slots, cap, ffi.cast(MAPS.PU32, S.buf)\n"
        "  return S.p\n"
        "end\n"
        "local function map_lookup(addr, key, max_capacity, header, soft)\n"
        "  local h = header\n"
        "  if not h then\n"
        "    local S = MAPS[addr]\n"
        "    if S and S.hgen == MAPS.gen then h = S.h\n"
        "    else\n"
        "      h = rd(addr, 20, 'map header')\n"
        "      if S then S.h, S.hgen = h, MAPS.gen end\n"
        "    end\n"
        "  end\n",
        'map snapshot')
    src = once(src, "  local hash = (key * mlo + (key * ((mult - mlo) / 65536) % 65536) * 65536) % 4294967296\n  for i = 0, math.min(cap, 128) - 1 do\n",
        "  local hash = (key * mlo + (key * ((mult - mlo) / 65536) % 65536) * 65536) % 4294967296\n"
        "  local P = map_snapshot(addr, slots, cap)\n"
        "  if P then\n"
        "    for i = 0, math.min(cap, 128) - 1 do\n"
        "      local j = bit.band(hash + i, cap - 1)\n"
        "      local k = tonumber(P[2 * j])\n"
        "      if k == key then\n"
        "        local v = tonumber(P[2 * j + 1])\n"
        "        return v ~= 4294967295 and v or nil\n"
        "      end\n"
        "      if k == empty then return nil end\n"
        "    end\n"
        "    if soft then return nil end\n"
        "    error({ Abort, 'map probe' }, 0)\n"
        "  end\n"
        "  for i = 0, math.min(cap, 128) - 1 do\n",
        'map probe from snapshot')
    src = once(src, "  FRAME = FRAME + 1\n", "  FRAME = FRAME + 1\n  MAPS.gen = MAPS.gen + 1   -- ((1.0.3) map snapshots are per frame)\n", 'snapshot frame')
    src = once(src, "    RC.frame = -1   -- (the game's update may have moved its lists)\n",
        "    RC.frame = -1   -- (the game's update may have moved its lists)\n    MAPS.gen = MAPS.gen + 1   -- ((1.0.3) and its maps: snapshots taken before it are stale)\n", 'snapshot after update')
    src = once(src, "    f:write(string.format('mod cost per frame (test): average %.3f ms, highest %.2f ms, over 1 ms in %d of %d frames\\n', T.sum / T.n, T.max, T.over, T.n))\n",
        "    f:write(string.format('mod cost per frame (test): average %.3f ms, highest %.2f ms, over 1 ms in %d of %d frames\\n', T.sum / T.n, T.max, T.over, T.n))\n"
        "    f:write(string.format('memory reads (test, since start): %.1f a frame (%.0f bytes); map snapshots %d (%.1f a frame, %.0f KB in all)\\n', RDN.n / T.n, RDN.b / T.n, RDN.snaps, RDN.snaps / T.n, RDN.snapb / 1024))\n"
        "    f:write(string.format('relaxed pacing (test): %d soldier checks; %d with no target (checked 20 a second), %d with a target and nobody near him or his line (checked 30 a second)\\n', RDN.checked or 0, RDN.idle or 0, RDN.relaxed or 0))\n",
        'reads line')
    src = once(src, "    laser.step = part('laser', laser.step)\n",
        "    laser.step = part('laser', laser.step)\n    if SGD.probe_step then SGD.probe_step = part('research (test builds)', SGD.probe_step) end\n", 'research part')
    # (1.0.3, performance) positions read once a frame: a unit's place is looked up again and again in one frame (each
    # soldier as a body for the others, as a shooter, his gun); the first lookup reads it, the rest get a copy
    src = once(src, "function unit_position(id, want_axes)\n  if not id or id == 0 then return nil end\n  local ok, pos = pcall(unit_position_raw, id, want_axes)\n  return ok and pos or nil\nend",
        "local UPM = { frame = -1, t = {} }   -- ((1.0.3) this frame's unit places)\n"
        "MAPS.upm = UPM   -- ((Test 4) reset after the game's update through MAPS: UPM is local to this block)\n"
        "function unit_position(id, want_axes)\n  if not id or id == 0 then return nil end\n"
        "  if not want_axes then\n"
        "    if UPM.frame ~= FRAME then UPM.frame, UPM.t = FRAME, {} end\n"
        "    local c = UPM.t[id]\n"
        "    if c then return { c[1], c[2], c[3], pose = c.pose } elseif c == false then return nil end\n"
        "  end\n"
        "  local ok, pos = pcall(unit_position_raw, id, want_axes)\n"
        "  if not want_axes and UPM.frame == FRAME then UPM.t[id] = ok and pos and { pos[1], pos[2], pos[3], pose = pos.pose } or false end\n"
        "  return ok and pos or nil\nend",
        'unit position per frame')
    # (1.0.3) the registry's map header and list once a frame, not once per soldier
    src = once(src, "  local reg_head = rd(registry + 73808, 20, 'registry map')\n  local reg_list = ptr_of(read(registry + 73832, 8), 0)\n",
        "  if RDN.rh_frame ~= FRAME or RDN.rh_reg ~= registry then\n"
        "    RDN.rh_head = rd(registry + 73808, 20, 'registry map')   -- ((1.0.3) once a frame, not once per soldier)\n"
        "    RDN.rh_list, RDN.rh_frame, RDN.rh_reg = ptr_of(read(registry + 73832, 8), 0), FRAME, registry\n"
        "  end\n"
        "  local reg_head, reg_list = RDN.rh_head, RDN.rh_list\n",
        'registry header per frame')
    src = once(src, "    MAPS.gen = MAPS.gen + 1   -- ((1.0.3) and its maps: snapshots taken before it are stale)\n",
        "    MAPS.gen = MAPS.gen + 1   -- ((1.0.3) and its maps: snapshots taken before it are stale)\n"
        "    RDN.rh_frame, MAPS.upm.frame = -1, -1   -- ((1.0.3) and the registry header and this frame's places)\n", 'after-update resets')
    # (1.0.3, Test 5) a busy soldier is checked every other frame (30 a second) unless a helldiver or one of your
    # sentries is within 25 m of him or within 15 m of his line of fire (from him to where he aims, or to his target):
    # those - everyone your safety depends on - are still checked every frame. Only a line toward another SEAF soldier,
    # with no helldiver near, can be seen up to one frame later
    src = once(src, "      if s.moved or s.busy ~= false or not s.st or t >= (s.next_read or 0) then",
        "      -- ((1.0.3 Test 6) a soldier with no target is checked every third frame (at least 15 a second): the game has to give\n"
        "      -- him a target and he has to turn to it before he fires, and from that frame on he is checked every frame again)\n"
        "      local lag = t - (s.read_t or -1) + (dt or 0)\n"
        "      local skip = (s.idle and (FRAME + s.id) % 3 ~= 0 and lag < 0.07) or (not s.idle and s.far and (FRAME + s.id) % 2 == 1 and lag < 0.045)\n"
        "      -- (and a skipped soldier's AI step and target are still read every frame - one small read: a new step (staggered, say)\n"
        "      -- or a new target and he is checked in full straight away)\n"
        "      if skip and s.st and s.busy ~= false then\n"
        "        local r = read(s.rec_addr, 28)\n"
        "        if not r or u32(r, 8) ~= s.st.node or u32(r, 24) ~= (s.st.friend_target or s.st.target) then skip = false end\n"
        "        -- (with a target: his barrel's line as it is now, near a friend - swung by a stagger, say - and he is checked in full)\n"
        "        local W = SGD.seaf_gun and SGD.seaf_gun.watch\n"
        "        if skip and not s.idle and W then\n"
        "          local okw, w = pcall(W, s, s.st, bodies, pbodies)\n"
        "          if not okw or w then skip = false end\n"
        "        end\n"
        "      end\n"
        "      if s.moved or not s.st or t >= (s.next_read or 0) or (s.busy ~= false and not skip) then", 'far pacing')
    src = once(src, "          st.me, st.posts = me, pbodies\n",
        "          st.me, st.posts = me, pbodies\n"
        "          -- ((1.0.3 Test 6) relaxed pacing: no helldiver, sentry of yours or other SEAF soldier near him (8 m; a soldier 2 m) or\n"
        "          -- within 25 degrees of his line of fire - he would have to turn that far, which takes longer than a frame, to\n"
        "          -- put his fire on them; Test 5's rule also stays: a helldiver or sentry 25 m away and 15 m off his line is clear)\n"
        "          local far = st.base ~= nil and me ~= nil and not ((s.gun_hold or 0) > t)\n"
        "          if far then\n"
        "            local b0, tp = st.base, st.aim\n"
        "            if not tp and st.target ~= 0 then\n"
        "              for _, c in ipairs(st.candidates) do if c.id == st.target then tp = c.pos; break end end\n"
        "            end\n"
        "            local lx, ly = tp and tp[1] - b0[1] or 0, tp and tp[2] - b0[2] or 0\n"
        "            local ll = lx * lx + ly * ly\n"
        "            local bx, by = b0[1], b0[2]\n"
        "            if seaf_near(me[1], me[2], bx, by, lx, ly, ll, 8) then far = false end\n"
        "            if far then\n"
        "              for _, b in ipairs(people) do local a = b.at; if a and seaf_near(a[1], a[2], bx, by, lx, ly, ll, 8) then far = false; break end end\n"
        "            end\n"
        "            if far and pbodies then\n"
        "              for _, b in ipairs(pbodies) do local a = b.at; if a and seaf_near(a[1], a[2], bx, by, lx, ly, ll, 8) then far = false; break end end\n"
        "            end\n"
        "            if far and fb then\n"
        "              for _, b in ipairs(fb) do local a = b.at; if a and b.sid ~= s.id and seaf_near(a[1], a[2], bx, by, lx, ly, ll, 2) then far = false; break end end\n"
        "            end\n"
        "          end\n"
        "          s.far = far or nil\n"
        "          if TESTER then RDN.relaxed, RDN.checked = (RDN.relaxed or 0) + (far and st.target ~= 0 and 1 or 0), (RDN.checked or 0) + 1 end\n",
        'far flag')
    src = once(src, "          s.busy = b\n",
        "          s.busy = b\n"
        "          -- ((1.0.3 Test 6) no target, not in his firing step, not staggered or getting up, no hold on his fire: checked every third frame)\n"
        "          s.idle = (s.def.trooper and st.target == 0 and st.node ~= (s.def.fire_node or FIRE_NODE) and not s.staggered and not ((s.gun_hold or 0) > t)) or nil\n"
        "          if TESTER and s.idle then RDN.idle = (RDN.idle or 0) + 1 end\n",
        'idle flag')
    # ((1.0.3 review) the relaxed-pacing test as one plain function, defined once: Tests 5-6 made a small function inside
    # the per-soldier loop every check, and LuaJIT can't compile a loop that does (NYI: FNEW))
    src = once(src, "  sentry_tick = function(st_dog, t, dt)\n",
        "  -- ((1.0.3) relaxed pacing) is (px, py) near him (rc m) or within 25 degrees of his line (lx, ly; ll its length squared)?\n"
        "  -- (with no line: within 25 m. A point 25 m away and 15 m off his line is clear, Test 5's rule)\n"
        "  local function seaf_near(px, py, bx, by, lx, ly, ll, rc)\n"
        "    local dx, dy = px - bx, py - by\n"
        "    local d2 = dx * dx + dy * dy\n"
        "    if d2 < rc * rc then return true end\n"
        "    if ll <= 1e-6 then return d2 < 625 end\n"
        "    local w = dx * lx + dy * ly\n"
        "    if w > 0 and w * w > 0.821 * d2 * ll then   -- (cos^2 25 degrees = 0.821)\n"
        "      if d2 >= 625 then\n"
        "        local u = w / ll\n"
        "        u = u > 1 and 1 or u\n"
        "        local ex, ey = dx - u * lx, dy - u * ly\n"
        "        if ex * ex + ey * ey >= 225 then return false end\n"
        "      end\n"
        "      return true\n"
        "    end\n"
        "    return false\n"
        "  end\n"
        "  sentry_tick = function(st_dog, t, dt)\n",
        'relaxed pacing helper')
    # (1.0.3, performance) the line-of-fire check first measures a cheap lower bound - the body's middle from the line to
    # the middle of where his shots land, less half the body and half that spread - and skips the two exact segment
    # distances when the body is clearly off the line (over 1 m clear: the 0.3 m 'linger' rule and every reason only
    # look at gaps under that). Every other check (the target's aim line, sweeps, splash) is unchanged
    src = once(src, "              local m = math.min(segment_distance(M, AIM_LO, b.lo, b.hi), segment_distance(M, AIM_HI, b.lo, b.hi))\n",
        "              local m\n"
        "              do   -- ((1.0.3) a cheap lower bound first: the body's middle against the line to the middle of the aim heights)\n"
        "                local lo, hi = b.lo, b.hi\n"
        "                local am, ah = (AIM_UP[1] + AIM_UP[2]) * 0.5, math.abs(AIM_UP[2] - AIM_UP[1]) * 0.5\n"
        "                local vx, vy, vz = p[1] - M[1], p[2] - M[2], p[3] + am - M[3]\n"
        "                local wx, wy, wz = (lo[1] + hi[1]) * 0.5 - M[1], (lo[2] + hi[2]) * 0.5 - M[2], (lo[3] + hi[3]) * 0.5 - M[3]\n"
        "                local vv = vx * vx + vy * vy + vz * vz\n"
        "                local tt = vv > 1e-9 and (wx * vx + wy * vy + wz * vz) / vv or 0\n"
        "                tt = tt < 0 and 0 or (tt > 1 and 1 or tt)\n"
        "                local ex, ey, ez = wx - tt * vx, wy - tt * vy, wz - tt * vz\n"
        "                local bound = math.sqrt(ex * ex + ey * ey + ez * ez) - 0.5 * math.sqrt((hi[1] - lo[1]) ^ 2 + (hi[2] - lo[2]) ^ 2 + (hi[3] - lo[3]) ^ 2) - ah - 0.01\n"
        "                if bound - r > 1.0 then m = bound end\n"
        "              end\n"
        "              m = m or math.min(segment_distance(M, AIM_LO, b.lo, b.hi), segment_distance(M, AIM_HI, b.lo, b.hi))\n",
        'line bound')
    # (1.0.3, Tester) where the steering's time goes, per phase: reading the soldiers, deciding (safety, armor, pings,
    # guns), the bodies list; in ms a frame on average, written under the mod cost
    src = once(src, "    local q2 = ffi.new('int64_t[1]')\n",
        "    local q2 = ffi.new('int64_t[1]')\n"
        "    local q3 = ffi.new('int64_t[1]')\n"
        "    T.phases, T.porder = {}, {}\n"
        "    SGD.now_ms = function() K32.SgdQueryPerformanceCounter(q3); return tonumber(q3[0]) / per_ms end\n"
        "    SGD.phase = function(name, ms)\n"
        "      local P = T.phases[name]\n"
        "      if not P then P = { n = 0, sum = 0, max = 0 }; T.phases[name] = P; T.porder[#T.porder + 1] = name end\n"
        "      P.n, P.sum = P.n + 1, P.sum + ms\n"
        "      if ms > P.max then P.max = ms end\n"
        "    end\n",
        'phase timer')
    src = once(src, "        if s.moved then ok, st, why = true, nil, nil else ok, st, why = pcall(read_sentry, s, registry) end\n",
        "        local q0 = TESTER and SGD.now_ms and SGD.now_ms()\n"
        "        if s.moved then ok, st, why = true, nil, nil else ok, st, why = pcall(read_sentry, s, registry) end\n"
        "        if q0 then SGD.phase('reading a soldier', SGD.now_ms() - q0) end\n",
        'phase read')
    src = once(src, "          local okp, perr = pcall(sentry_step, s, st, bodies, t, people, me)\n",
        "          local q1 = TESTER and SGD.now_ms and SGD.now_ms()\n"
        "          local okp, perr = pcall(sentry_step, s, st, bodies, t, people, me)\n"
        "          if q1 then SGD.phase('deciding for a soldier', SGD.now_ms() - q1) end\n",
        'phase decide')
    src = once(src, "    local fb = seaf_bodies(t, me)\n",
        "    local qb = TESTER and SGD.now_ms and SGD.now_ms()\n"
        "    local fb = seaf_bodies(t, me)\n"
        "    if qb then SGD.phase('the soldiers as bodies', SGD.now_ms() - qb) end\n",
        'phase bodies')
    src = once(src, "    for _, Pt in ipairs(T.parts or {}) do\n",
        "    for _, name in ipairs(T.porder or {}) do\n"
        "      local P = T.phases[name]\n"
        "      f:write(string.format('  - %-26s %d times, %.3f ms a frame on average, %.3f ms each, highest %.2f ms\\n', name, P.n, P.sum / T.n, P.sum / P.n, P.max))\n"
        "    end\n"
        "    for _, Pt in ipairs(T.parts or {}) do\n",
        'phase report')
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
                zi.compress_type, zi.external_attr, zi.create_system = zipfile.ZIP_DEFLATED, 0o644 << 16, 3   # ((1.0.1) the same bytes on any OS)
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
        # ((1.0.1 review) the author's own words come from SANITIZE_EXTRA; without it the build says the check was partial)
        if not os.environ.get('SANITIZE_EXTRA'): print('note: SANITIZE_EXTRA not set: only the generic personal-data checks ran')
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
