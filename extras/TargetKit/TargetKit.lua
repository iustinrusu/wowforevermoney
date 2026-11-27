-- TargetKit: three one-key target helpers for WoW: Forever, each a macro the addon makes for you.
-- Not part of the WoW Forever Money app: it lives in the repo's extras/ folder and the app never copies it.
-- The request it follows (revised): extras/TargetKit/README.md.
--
--   TK Find        your find list (/tkit add <name>): the closest match, by name. With one of them targeted, the next
--                  name from the list that's in sight; never the game's Tab, which lands on other mobs (1.4.5).
--                  Dead mobs are skipped; dead players count, and dead friendly NPCs (a dead neutral or hostile unit
--                  could be a mob, so it is skipped).
--   TK Pickpocket  the closest humanoid you can rob (attackable, not a player, alive, not in combat, not pickpocketed
--                  yet): Sap, then Pick Pocket, in one press (Sap doesn't break stealth on Forever: the user, 2026-11-27).
--                  If one of the two was still on cooldown, the next press within 10 s on that unit does the other,
--                  while it's still in range for it; walked on, the closest one again, never the old target (1.4.7).
--   TK Sap         your mouseover enemy first. Else the closest enemy player in Sap range the addon can see, whoever
--                  you have targeted; else the game's own nearest enemy player (an enemy player you target further off
--                  than Sap's range is let go of first, 1.4.6); else the closest NPC in Sap range; else the game's
--                  nearest enemy. The macro is rewritten at once when the enemy player to Sap changes (1.4.6).
--
-- How, within WoW's rules: an addon may never pick a target by itself; only a key press running a macro can, and a
-- macro can only be changed out of combat. So out of combat, five times a second, the addon looks at every unit it can
-- see (nameplates, target, mouseover, soft targets, focus, your group), ranks them and writes its choice into the three
-- macros themselves (EditMacro): "/target nameplate7" and the spell. A press runs whatever is written then, with no
-- addon code in between. In combat, or when it finds nothing, a macro holds a fixed text made only of the game's own
-- targeting. The keys you set in the TargetKit window run the same macros.
-- 1.4.0 (the user: "still cant target friendly saved targets with the macro"). Until 1.3.0 each macro was
-- "/click TKFind" on a secure button holding the choice. The 1.3.0 log showed the game ran the macro's first line (a
-- /click on a plain button) on every press, but never the secure button's macro after it, so the choice never ran.
-- There is no secure button any more: the choice is in the macro, the way RXPGuides keeps its targeting macro on
-- Forever. The mouseover and soft targets move with the mouse and camera, so they are written by name (/targetexact).
-- 1.4.2 (the user: TK Find on Zhevra Runners went "closest, none, closest", and failed while CorpseGlow lit a corpse).
-- The log showed two things about Forever. Nameplates are restricted regions: asking one where it is on screen
-- (GetCenter) is an error, and that error made every look fail. And within one press, a macro's [conditions] still see
-- the target you had before it: after "/cleartarget", "/target [noexists] X" doesn't act. So the macros no longer chain
-- "/cleartarget" with [noexists] lines; each line's conditions are written about the target you had before the press.
-- 1.4.3 (the user: "now it doesnt work at all"): Forever refuses "/target nameplate1" in a macro (the game ran it on
-- every press, the target stayed none; before, the by-name line behind it had hidden that). So a unit is targeted by
-- name (the game takes the closest of that name) or by the game's own Tab, never by its nameplate.
-- Distance: the game gives addons no distance to other units, only "in range" checks, so "closest" is the nearest of
-- these bands: Pick Pocket's range (5 yd), Sap's range, 10 yd (duel), 11 yd (trade), 28 yd (follow), further. Within a
-- band, the unit whose nameplate is lower on the screen (usually nearer the camera) comes first.

local VERSION = "1.4.8"
local PICK_POCKET, SAP = 921, 6770
local SAP_IDS = { [6770] = true, [2070] = true, [11297] = true }        -- Sap, every rank
local HUMANOID = 7                                                       -- creature type id
local CYCLE = 8                       -- seconds: TK Find going round the list's names keeps going within this
local AGAIN = 10                      -- seconds: TK Pickpocket pressed again on its last unit finishes the job
local KEEP_PICKED = 2 * 3600          -- a robbed unit is skipped for 2 hours (a respawn is a new unit anyway)
local MAX_BODY = 255                  -- a macro's text: the game takes up to 255 characters
local EDIT_GAP = 0.4                  -- seconds: a macro is rewritten at most this often while nothing is pressed

local db
local debug = false
local function tell(...) print("|cff9ad0ffTargetKit|r", ...) end
-- What the addon notices by itself (a press that found nobody, a warning, an error, the macros made) goes to the log
-- only, and to chat as well just if you turn chat messages on with /tkit chat (1.4.1, the user: "chat debug menus
-- should be hidden, I don't want to see them"). Answers to what you type in chat (/tkit list, /tkit log, /tkit add
-- ...) still show there; what you do in the window shows on the window's bottom line.
local function note(...) if db and db.chat then tell(...) end end

-- The log (1.2.0, the user: "logging should be explicit so we can catch issues"). Always on, not only with
-- /tkit debug. Every press: which macro, what it saw and why it chose what it did, and the macro it ran. Then what came
-- of it in the next 2 s: the game's error line, the cast, the new target. Also the game's settings at login, macros
-- and keys made (and checked), anything the game blocked, and every error with where. Kept in TargetKitDB.log (the
-- last 400 lines); WoW writes it on /reload or logout, where Claude can read it. /tkit log shows the last lines.
local LOG_MAX = 400
local early = {}
local function clean(v)
  return (tostring(v):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("|H.-|h(.-)|h", "%1"):gsub("\n", " / "))
end
local function store(line)
  if not db then early[#early + 1] = line return end
  if type(db.log) ~= "table" then db.log = {} end
  db.log[#db.log + 1] = line
  while #db.log > LOG_MAX do table.remove(db.log, 1) end
end
local function log(kind, ...)
  local parts = {}
  for i = 1, select("#", ...) do parts[#parts + 1] = clean(select(i, ...)) end
  store((date and date("%m-%d %H:%M:%S") or "") .. string.format(" [%.1f] ", GetTime()) .. kind .. ": "
    .. table.concat(parts, " "))
end
local function say(...)                          -- to the log always, to chat with /tkit debug
  log("debug", ...)
  if debug then tell(...) end
end

local function cvar(name)
  local ok, v = pcall(GetCVar, name)
  return ok and tostring(v) or "?"
end

-- What the game ran for a press (1.2.1, the user: "added a target in the find list but macro does not work when
-- pressing"; the log showed each press and its macro, but not whether the game ran it). The game's own targeting and
-- casting functions are watched with hooksecurefunc, which only looks after the fact and can't get in the macro's way.
-- Every call is noted with its time; a press's last line (the marker, see onPress) picks up the ones of that moment,
-- and 0.3 s later they are logged with where the target went.
local recent = {}                                -- { t = GetTime(), s = "TargetUnit(nameplate3)" }, the last 20
local function noteRan(fname, ...)
  local args = {}
  for i = 1, select("#", ...) do args[#args + 1] = tostring((select(i, ...))) end
  recent[#recent + 1] = { t = GetTime(), s = fname .. "(" .. table.concat(args, ", ") .. ")" }
  if #recent > 20 then table.remove(recent, 1) end
end
if hooksecurefunc then
  for _, fname in ipairs({ "TargetUnit", "ClearTarget", "TargetNearestEnemy", "TargetNearestEnemyPlayer",
                           "TargetNearestFriend", "TargetLastTarget", "CastSpellByName", "CastSpellByID" }) do
    if type(_G[fname]) == "function" then
      hooksecurefunc(fname, function(...) noteRan(fname, ...) end)
    end
  end
end

-- Run a handler; an error is logged with where (and the Lua stack when the game gives it) and said once in chat,
-- never swallowed. The same error again is logged its first 3 times, then every 50th.
local failed = {}
local function try(where, fn, ...)
  local n, args = select("#", ...), { ... }
  local ok, err = xpcall(function() return fn(unpack(args, 1, n)) end, function(e)
    return tostring(e) .. (debugstack and (" @ " .. debugstack(2, 3, 0)) or "")
  end)
  if not ok then
    failed[where] = (failed[where] or 0) + 1
    local count = failed[where]
    if count <= 3 or count % 50 == 0 then
      log("ERROR", where .. (count > 1 and (" (" .. count .. " times so far)") or "") .. ":", err)
    end
    if count == 1 then
      note("|cffff6060an error in " .. where .. "|r (" .. clean(err):sub(1, 120) .. "). It's in the log: /tkit log"
        .. " shows it, /reload saves it for a closer look.")
    end
  end
  return ok
end

local function spellName(id)
  local n = (C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(id)) or (GetSpellInfo and GetSpellInfo(id))
  return n
end
local function PP() return spellName(PICK_POCKET) or "Pick Pocket" end
local function SAPN() return spellName(SAP) or "Sap" end

-- 1.4.8 (the user, in a battleground: "sap macro does not work, after targeting the first enemy, pressing the button
-- again does not switch to closer targets"; the log: "attempted to index a table that cannot be indexed with secret
-- keys", 300 times). There the game hides some values about units from addons ("secret" values). TargetKit treats a
-- hidden value as unknown: it never compares one or uses it as a key, and a unit whose id is hidden isn't seen.
local isSecret = issecretvalue or function() return false end
local function known(v) return v ~= nil and not isSecret(v) end
local function yes(fn, ...)                              -- a yes/no from the game: nil when hidden or refused
  local ok, v = pcall(fn, ...)
  if not ok or (v ~= nil and isSecret(v)) then return nil end
  if v then return true end
  return false
end
local hidden = false                                     -- a look met units the game hides (said once in the log)
local function nameOf(u)                                 -- a unit's name, nil when hidden or refused
  local ok, n = pcall(UnitName, u)
  if ok and known(n) then return n end
end

-- ---------- what the addon can see about a unit ----------
local function inRange(id, unit)
  local name = spellName(id)
  local check = (C_Spell and C_Spell.IsSpellInRange) or IsSpellInRange
  if not (name and check) then return false end
  local ok, r = pcall(check, name, unit)
  if not ok or (r ~= nil and isSecret(r)) then return nil end            -- unknown
  return r == true or r == 1
end

local function interact(unit, index)
  if not CheckInteractDistance then return false end
  local ok, r = pcall(CheckInteractDistance, unit, index)
  if not ok or (r ~= nil and isSecret(r)) then return nil end            -- unknown
  return r and true or false
end

-- 1 Pick Pocket's range, 2 Sap's, 3 duel (10 yd), 4 trade (11 yd), 5 follow (28 yd), 6 further; nil: the game said
-- nothing (all hidden or refused)
local function reach(unit)
  local a = inRange(PICK_POCKET, unit)
  if a then return 1 end
  local b = inRange(SAP, unit)
  if b then return 2 end
  local c, d, e = interact(unit, 3), interact(unit, 2), interact(unit, 4)
  if c then return 3 end
  if d then return 4 end
  if e then return 5 end
  if a == nil and b == nil and c == nil and d == nil and e == nil then return nil end
  return 6
end

local function isHumanoid(unit)
  local name, id = UnitCreatureType(unit)
  if type(id) == "number" then return id == HUMANOID end
  local info = C_CreatureInfo and C_CreatureInfo.GetCreatureTypeInfo and C_CreatureInfo.GetCreatureTypeInfo(HUMANOID)
  return name ~= nil and name == ((info and info.name) or "Humanoid")
end

local function hasSap(unit)
  for i = 1, 40 do
    local id
    if C_UnitAuras and C_UnitAuras.GetDebuffDataByIndex then
      local d = C_UnitAuras.GetDebuffDataByIndex(unit, i)
      if not d then return false end
      id = d.spellId
    elseif UnitDebuff then
      local name, _, _, _, _, _, _, _, _, spellId = UnitDebuff(unit, i)
      if not name then return false end
      id = spellId
    else
      return false
    end
    if SAP_IDS[id] then return true end
  end
  return false
end

local function dead(unit) return yes(UnitIsDeadOrGhost or UnitIsDead, unit) or false end

-- every unit the addon can see, once each: nameplates first (their tokens are the steadiest for the click), then
-- mouseover, soft targets, target, focus and your group
local TOKENS = { "mouseover", "softenemy", "softinteract", "softfriend", "target", "focus" }
local rememberName                                       -- set below (TK Find)
local function visibleUnits()
  local out, seen = {}, {}
  local function add(u)
    if not yes(UnitExists, u) or yes(UnitIsUnit, u, "player") ~= false then return end
    local ok, g = pcall(UnitGUID, u)
    if not ok or not known(g) then                       -- hidden by the game (battlegrounds): not seen
      if not hidden then
        hidden = true
        log("addon", "the game hides some units from addons here (" .. u .. "'s id is secret), so TargetKit doesn't"
          .. " see them; TK Sap takes the game's nearest enemy player instead")
      end
      return
    end
    if not seen[g] then
      seen[g] = true
      out[#out + 1] = { unit = u, guid = g }
      if rememberName then rememberName(u) end
    end
  end
  if C_NamePlate and C_NamePlate.GetNamePlates then
    for _, plate in ipairs(C_NamePlate.GetNamePlates() or {}) do
      local u = plate.namePlateUnitToken or (plate.UnitFrame and plate.UnitFrame.unit)
      if u then add(u) end
    end
  end
  for _, u in ipairs(TOKENS) do add(u) end
  local raid = IsInRaid and IsInRaid()
  for i = 1, raid and 40 or 4 do add((raid and "raid" or "party") .. i) end
  return out
end

-- Nearest band first; within a band, the nameplate lower on the screen first where the game lets an addon measure it.
-- On Forever it doesn't (1.4.2: "Can't measure restricted regions"), so after the first refusal ties go by a steady
-- order (the unit's id), which still lets TK Find go round them one by one.
local measure = true
local function plateY(unit)
  if not measure then return nil end
  local plate = C_NamePlate and C_NamePlate.GetNamePlateForUnit and C_NamePlate.GetNamePlateForUnit(unit)
  if not (plate and plate.GetCenter) then return nil end
  local ok, _, y = pcall(plate.GetCenter, plate)
  if ok then return y end
  measure = false
  log("addon", "the game doesn't let addons measure nameplates here (" .. clean(_):sub(1, 90) .. "), so units in the"
    .. " same range band are taken in a steady order instead of lowest on screen first")
  return nil
end

local function rank(list)
  for _, c in ipairs(list) do
    if not c.reach then
      c.reach = reach(c.unit) or 6
      c.y = plateY(c.unit) or math.huge
    end
  end
  table.sort(list, function(a, b)
    if a.reach ~= b.reach then return a.reach < b.reach end
    if a.y ~= b.y then return a.y < b.y end
    return a.guid < b.guid
  end)
  return list
end

local BAND = { "Pick Pocket range", "Sap range", "10 yd", "11 yd", "28 yd", "further" }
local function describe(c) return (UnitName(c.unit) or "?") .. " (" .. c.unit .. ", " .. BAND[c.reach] .. ")" end

local function passed(c, why) return (UnitName(c.unit) or "?") .. " (" .. c.unit .. "): " .. why end

-- The line that targets a unit the addon chose. Your target or focus, or someone in your group, by token. Anything else
-- by name, exactly: the mouseover and the soft targets follow the mouse and camera (1.4.0), and Forever refuses a
-- nameplate's token in a macro (1.4.3). The game takes the closest unit of that name.
local function steady(u)
  return u == "target" or u == "focus" or u:match("^party%d$") or u:match("^raid%d+$")
end
local function fullName(u)
  local n, realm = UnitName(u)
  if n and realm and realm ~= "" then n = n .. "-" .. realm end
  return n
end
local function targetLine(c, cond)
  local pre = cond and (cond .. " ") or ""
  if steady(c.unit) then return "/target " .. pre .. c.unit end
  local n = fullName(c.unit)
  if not n then return "/target " .. pre .. c.unit end
  return "/targetexact " .. pre .. n
end
local function seen(lists, rejected, others)    -- what a look saw, for the log of the press that uses it
  local out = {}
  for _, list in ipairs(lists) do for _, c in ipairs(list) do out[#out + 1] = describe(c) end end
  for _, r in ipairs(rejected) do out[#out + 1] = r end
  while #out > 12 do table.remove(out) end
  if others and others > 0 then out[#out + 1] = others .. " others not on the find list" end
  return out
end

-- ---------- TK Sap ----------
-- The targeting lines' conditions are about the target you had before the press (that's what the game checks), and the
-- last line that finds someone wins: no attackable target, the game's nearest enemy; then, unless you already have a
-- living enemy player, the game's nearest enemy player (revealed stealthers too), which wins if there is one.
local SAP_PLAYER = "/targetenemyplayer [noexists][dead][noharm][noplayer]"
-- The fixed macro (in combat, or when a look fails) starts from scratch every press (1.4.8): it can't know whether
-- your target is near, and the user wants "the closest physically possible".
local function sapFixed()
  local sap = SAPN()
  return table.concat({
    "/cast [@mouseover,harm,nodead] " .. sap,
    "/stopmacro [@mouseover,harm,nodead]",
    "/cleartarget",
    "/targetenemyplayer",
    "/cast " .. sap }, "\n")
end

local function sapWhyNot(u)
  if not UnitCanAttack("player", u) then return "can't be attacked" end
  if dead(u) then return "dead" end
  if UnitAffectingCombat(u) then return "in combat (Sap needs it out of combat)" end
  if not isHumanoid(u) then return "not humanoid (Sap takes humanoids)" end
  if hasSap(u) then return "sapped already" end
end

local function sapBuild(units)
  local sap = SAPN()
  local players, npcs, rejected = {}, {}, {}
  for _, c in ipairs(units or visibleUnits()) do
    local u = c.unit
    local why = sapWhyNot(u)
    if why then
      rejected[#rejected + 1] = passed(c, why)
    elseif UnitIsPlayer(u) then
      players[#players + 1] = c
    else
      npcs[#npcs + 1] = c
    end
  end
  rank(players)
  rank(npcs)
  local saw = seen({ players, npcs }, rejected)
  local head = { "/cast [@mouseover,harm,nodead] " .. sap, "/stopmacro [@mouseover,harm,nodead]" }
  local p = players[1]
  if p and p.reach <= 2 then
    head[#head + 1] = targetLine(p)
    head[#head + 1] = "/cast " .. sap
    return table.concat(head, "\n"), "enemy player in Sap range: " .. describe(p), UnitName(p.unit), saw
  end
  local n = npcs[1]
  if n and n.reach > 2 then n = nil end
  -- Your target is kept only when TargetKit knows it's in Sap range, attackable and alive (then a player the game finds
  -- wins over an NPC). Else, further off or hidden by the game (enemy players in battlegrounds, 1.4.8; an enemy player
  -- you target out of Sap range, 1.4.6: "in case a stealthed rogue pops up next to me, it targets him even though I
  -- maybe have another target enemy player targeted that is farther away"), it's let go of: the NPC in Sap range, or
  -- nothing, then the game's nearest enemy player, which wins if it finds one.
  local tname = nameOf("target")
  local r = yes(UnitExists, "target") and reach("target")
  if r and r <= 2 and yes(UnitCanAttack, "player", "target") and yes(UnitIsDeadOrGhost, "target") == false then
    head[#head + 1] = SAP_PLAYER
    head[#head + 1] = "/cast " .. sap
    return table.concat(head, "\n"), "no enemy player in Sap range in sight; your target " .. (tname or "?")
      .. " is in Sap range, so it stays (unless it's an NPC and the game finds an enemy player)", nil, saw
  end
  head[#head + 1] = n and targetLine(n) or "/cleartarget"
  head[#head + 1] = "/targetenemyplayer"
  head[#head + 1] = "/cast " .. sap
  local why = not yes(UnitExists, "target") and "no target" or (r == nil and ("your target " .. (tname or "?")
    .. " can't be measured here") or ("your target " .. (tname or "?") .. " is out of Sap range"))
  return table.concat(head, "\n"), "no enemy player in Sap range in sight; " .. why .. ", so the game's nearest enemy"
    .. " player from scratch" .. (n and (", else " .. describe(n)) or ""), nil, saw
end

-- ---------- TK Pickpocket ----------
local last = { find = { t = 0 }, pick = { guid = nil, t = 0 } }

local function picked(guid)
  local t = db.picked[guid]
  return t and time() - t < KEEP_PICKED
end

local function pickFixed()
  return table.concat({ "/targetenemy [noharm][dead]", "/cast " .. SAPN(), "/cast " .. PP() }, "\n")
end

local function pickWhyNot(c)
  local u = c.unit
  if UnitIsPlayer(u) then return "a player (players have no pockets to pick)" end
  if not UnitCanAttack("player", u) then return "can't be attacked" end
  if dead(u) then return "dead" end
  if UnitAffectingCombat(u) then return "in combat" end
  if not isHumanoid(u) then return "not humanoid" end
  if picked(c.guid) then return "robbed already" end
end

-- 1.4.7 (the user: "when stealthed and going past multiple enemies, if I press the button I instantly want to sap and
-- pickpocket the one next to me, I don't want to see a failure due to the old target still being selected even
-- though I'm already gone and going away from it"): the half-done rule only holds while the unit is in range for the
-- missing half; with nobody to rob in sight, a target out of Sap range is let go of; and the macro is rewritten at
-- once when its choice changes (see prepare).
local function pickBuild(units)
  -- its last unit, half done (Sap or Pick Pocket still on cooldown then): the missing half, while in range for it
  local t = UnitGUID("target")
  if not known(t) then t = nil end                       -- hidden by the game: unknown
  if t and t == last.pick.guid and GetTime() - last.pick.t <= AGAIN and not dead("target")
      and not UnitAffectingCombat("target") then
    local sapped, robbed = hasSap("target"), picked(t)
    local r = reach("target") or 6
    if sapped and not robbed and r <= 1 then
      return "/cast " .. PP(), "Pick Pocket the one just sapped: " .. (UnitName("target") or "?"), UnitName("target"), {}
    elseif robbed and not sapped and r <= 2 then
      return "/cast " .. SAPN(), "Sap the one just robbed: " .. (UnitName("target") or "?"), UnitName("target"), {}
    end
  end
  local list, rejected, refused = {}, {}, {}
  for _, c in ipairs(units or visibleUnits()) do
    local why = pickWhyNot(c)
    if why then
      rejected[#rejected + 1] = passed(c, why)
      refused[#refused + 1] = c
    else
      list[#list + 1] = c
    end
  end
  rank(list)
  local saw = seen({ list }, rejected)
  -- By name the game takes the closest unit of that name, so a robbed (or dead, or fighting) one of the same name as
  -- near or nearer gets it instead (a camp of Defias Thugs: the one you just robbed). Then another name in Sap range,
  -- else the game's Tab to the next enemy in front of you (1.4.7).
  local function blocker(c)
    local n = UnitName(c.unit)
    for _, o in ipairs(refused) do
      if UnitName(o.unit) == n then
        o.reach = o.reach or reach(o.unit) or 6
        if o.reach <= c.reach then return o end
      end
    end
  end
  local tg = UnitGUID("target")                          -- your target, robbable and in Sap range: that one
  if not known(tg) then tg = nil end
  for _, o in ipairs(list) do
    if tg and o.guid == tg and o.reach <= 2 then
      local cast = {}
      if not hasSap(o.unit) then cast[#cast + 1] = "/cast " .. SAPN() end
      cast[#cast + 1] = "/cast " .. PP()
      return table.concat(cast, "\n"), "your target, in Sap range, to rob: " .. describe(o), UnitName(o.unit), saw
    end
  end
  local c = list[1]
  local b = c and blocker(c)
  if b then
    local free
    for _, o in ipairs(list) do
      if o.reach <= 2 and not blocker(o) then free = o break end
    end
    if free then
      c = free
    else
      return "/targetenemy\n/cast " .. SAPN() .. "\n/cast " .. PP(), "closest to rob: " .. describe(c) .. ", but a"
        .. " nearer one of that name can't be robbed (" .. passed(b, pickWhyNot(b) or "?") .. ") and would be taken by"
        .. " name, so the game's Tab to the next enemy", nil, saw
    end
  end
  if not c then
    if yes(UnitExists, "target") and yes(UnitCanAttack, "player", "target") and not dead("target")
        and (reach("target") or 6) > 2 then
      return "/cleartarget\n/targetenemy\n/cast " .. SAPN() .. "\n/cast " .. PP(), "no humanoid to rob in sight, and"
        .. " your target " .. (UnitName("target") or "?") .. " is out of Sap range: the game's nearest enemy instead",
        nil, saw
    end
    return nil, "no humanoid to rob in sight", nil, saw
  end
  local lines = { targetLine(c) }
  if not hasSap(c.unit) then lines[#lines + 1] = "/cast " .. SAPN() end
  lines[#lines + 1] = "/cast " .. PP()
  return table.concat(lines, "\n"), "closest to rob: " .. describe(c), UnitName(c.unit), saw
end

-- ---------- TK Find ----------
local function wanted(unit)
  local name = UnitName(unit)
  if not name then return false end
  name = strlower(name)
  for _, w in ipairs(db.find) do
    if name:find(strlower(w), 1, true) then return true end
  end
  return false
end

local function findWhyNot(unit)
  if not wanted(unit) then return "not on the find list" end
  if not dead(unit) or UnitIsPlayer(unit) then return nil end     -- dead players count
  local r = UnitReaction(unit, "player")
  if r ~= nil and r >= 5 then return nil end                      -- a dead friendly NPC counts
  return "dead, and neutral or hostile, so it could be a mob"
end

-- Full names seen this session (your target, mouseover, nameplates), 1.2.2. The user put "Game" on the list for a unit
-- named "Game something": the addon matches part of a name itself, but its fallback is the game's own /target by
-- name, and whether that takes part of a name isn't checked on Forever. So the fallback also targets, by full name,
-- every unit seen whose name contains a list entry.
local seenNames, seenCount = {}, 0                       -- lower-case name -> the name
rememberName = function(unit)
  local ok, n = pcall(UnitName, unit)
  if not ok or not known(n) or n == "" or n == UNKNOWNOBJECT then return end
  local key = strlower(n)
  if seenNames[key] then return end
  if seenCount >= 500 then seenNames, seenCount = {}, 0 end
  seenNames[key] = n
  seenCount = seenCount + 1
end

local function namesFor(w)                               -- full names seen that contain w, then w itself
  local out, lw = {}, strlower(w)
  for key, n in pairs(seenNames) do
    if key ~= lw and key:find(lw, 1, true) then out[#out + 1] = n end
  end
  table.sort(out)
  out[#out + 1] = w
  return out
end

-- By name: reaches units with no nameplate (far, friendly with friendly nameplates off). "/cleartarget", then a plain
-- "/target name" for each name: a name nobody near has changes nothing, the last one found wins, so the list goes in
-- backwards (your first entry wins). The game takes the closest unit of a name, alive or a corpse; it can't skip
-- corpses here (a condition would see the target you had before the press).
local function findFixed(n)
  n = n or MAX_BODY
  local names = {}
  for _, w in ipairs(db.find) do
    for _, name in ipairs(namesFor(w)) do names[#names + 1] = name end
  end
  local lines, size = { "/cleartarget" }, #"/cleartarget"
  local kept = {}
  for _, name in ipairs(names) do                        -- as many as fit, first entries first
    local line = "/target " .. name
    if size + 1 + #line > n then break end
    kept[#kept + 1] = line
    size = size + 1 + #line
  end
  for i = #kept, 1, -1 do lines[#lines + 1] = kept[i] end
  return table.concat(lines, "\n")
end

local function findBuild(units)
  if #db.find == 0 then return "", "empty list", nil, {} end
  local list, rejected, others = {}, {}, 0
  for _, c in ipairs(units or visibleUnits()) do
    local why = findWhyNot(c.unit)
    if not why then
      list[#list + 1] = c
    elseif why == "not on the find list" then
      others = others + 1
    else
      rejected[#rejected + 1] = passed(c, why)
    end
  end
  rank(list)
  local saw = seen({ list }, rejected, others)
  -- Forever refuses "/target nameplateN" in a macro (1.4.3), so a unit can only be targeted by name (the closest of
  -- that name, in any direction) or by the game's Tab. Tab goes through every enemy in front of you whose nameplate
  -- shows, so it landed on other mobs; 1.4.5 drops it (the user: "it's now working but is inconsistent, and seems
  -- it's still targeting other mobs other than the ones selected, if it's too messy let's just drop cycling"). So
  -- TK Find only ever targets by name, so only what's on your list: the closest match; with one of them targeted,
  -- the next name from the list in sight (each once a round, then round again). Mobs sharing a name: the closest.
  if #list == 0 then
    return nil, "none in sight, so by name (with the full names seen that contain a list entry)", nil, saw
  end
  local fresh = GetTime() - last.find.t > CYCLE                       -- a pause: a new round
  local done = fresh and {} or (last.find.names or {})
  local tname = UnitName("target")
  if UnitExists("target") and not findWhyNot("target") then
    local other, again
    for _, c in ipairs(list) do                                       -- closest first
      local n = UnitName(c.unit)
      if n ~= tname then
        if not done[n] and not other then other = c end
        if not again then again = c end
      end
    end
    if other then
      local n = UnitName(other.unit)
      return targetLine(other), "your target " .. (tname or "?") .. " is on the list; the next name, by name: "
        .. describe(other), n, saw, { name = n, from = tname }
    end
    if again then
      local n = UnitName(again.unit)
      return targetLine(again), "your target " .. (tname or "?") .. " is on the list; every name had, so round again"
        .. " by name: " .. describe(again), n, saw, { name = n, from = tname, reset = true }
    end
  end
  local pick = list[1]
  local n = UnitName(pick.unit)
  return targetLine(pick), "the closest on the list: " .. describe(pick) .. " (" .. #list .. " in sight)", n, saw,
    { name = n }
end

-- ---------- the macros ----------
local BUTTONS = {             -- name: the marker button (TKFindMark) and the key in TargetKitDB.keys
  { name = "TKFind", macro = "TK Find", icon = "INV_Misc_Spyglass_02", build = findBuild, fixed = findFixed },
  { name = "TKPick", macro = "TK Pickpocket", icon = "INV_Misc_QuestionMark", show = PICK_POCKET,
    build = pickBuild, fixed = pickFixed },
  { name = "TKSap", macro = "TK Sap", icon = "INV_Misc_QuestionMark", show = SAP, build = sapBuild, fixed = sapFixed },
}

local watching                                           -- the last press, for 2 s: what came of it goes to the log
local saidNobody, saidMissed, targetBefore = 0, {}, "none"

-- A macro: its tooltip line, the choice, and last a /click on a plain button (the marker). Clicking that runs no
-- addon code, but its Click is watched by hooksecurefunc, so a press shows in the log. It comes last so that nothing
-- of the addon's comes before the targeting (TK Sap's mouseover Sap ends its macro early, so that press isn't logged;
-- its cast is).
local function marker(b) return "/click " .. b.name .. "Mark" end
local function tooltipLine(b)
  local show = b.show and spellName(b.show)
  return show and ("#showtooltip " .. show .. "\n") or ""
end
local function room(b) return MAX_BODY - #tooltipLine(b) - #marker(b) - 1 end

local function fit(text, n)                              -- whole lines, up to n characters
  if #text <= n then return text, false end
  local out = ""
  for line in text:gmatch("[^\n]+") do
    local more = out == "" and line or (out .. "\n" .. line)
    if #more > n then break end
    out = more
  end
  return out, true
end

local function compose(b, text)
  local kept, short = fit(text or "", room(b))
  if short and b.cutSaid ~= text then
    b.cutSaid = text
    log("WARN", b.macro .. ": its macro would be over " .. MAX_BODY .. " characters, so it was cut to: " .. kept)
  end
  return tooltipLine(b) .. (kept ~= "" and (kept .. "\n") or "") .. marker(b), kept
end

-- Into the macro, out of combat only. Unchanged (as the game keeps it): nothing to do. Otherwise at most every
-- EDIT_GAP seconds, and not while the game's Macros window is open (you may be editing there), unless forced: right
-- after a press (the next press must get the next unit), a change to the find list, combat starting.
local function write(b, force, urgent)                   -- urgent: no EDIT_GAP wait (the Macros window still holds it)
  if not b.body or InCombatLockdown() or not (GetMacroIndexByName and EditMacro) then return end
  local i = GetMacroIndexByName(b.macro)
  if not i or i == 0 then
    if not b.missingSaid then
      b.missingSaid = true
      log("WARN", b.macro .. ": not in your macros (deleted?), so it can't be written; /tkit macros makes it again")
    end
    return
  end
  b.missingSaid = nil
  if b.body == b.written and select(3, GetMacroInfo(i)) == b.stored then
    b.live = b.state                                     -- the same text: this look's reasons stand for it
    return
  end
  local now = GetTime()
  if not force then
    if not urgent and now - (b.editedAt or -100) < EDIT_GAP then return end
    if MacroFrame and MacroFrame.IsShown and MacroFrame:IsShown() then return end
  end
  EditMacro(i, b.macro, nil, b.body)
  b.written, b.editedAt, b.live = b.body, now, b.state
  b.stored = select(3, GetMacroInfo(GetMacroIndexByName(b.macro)))
  if not b.firstSaid then                                -- once a session: the game took the edit (or not, below)
    b.firstSaid = true
    log("macros", b.macro .. ": TargetKit writes its choice into it from now on; first: " .. b.body)
  end
  if b.stored ~= b.body and not b.mismatchSaid then
    b.mismatchSaid = true
    log("WARN", b.macro .. ": written as " .. b.body .. ", but the game keeps it as " .. tostring(b.stored))
  end
end

local function prepare(force)                            -- look once, write all three (out of combat)
  if not db or InCombatLockdown() then return end
  local okName, tn = pcall(UnitName, "target")
  targetBefore = (okName and known(tn)) and tn or "none"
  local okLook, units = pcall(visibleUnits)
  if not okLook then
    try("TargetKit looking", error, units)               -- logged (and counted) like any error
    units = {}
  end
  for _, b in ipairs(BUTTONS) do
    local n = room(b)
    local text, why, expect, saw, extra
    local ok = try(b.macro .. " choosing", function() text, why, expect, saw, extra = b.build(units, n) end)
    if not ok then text, why, expect, saw, extra = nil, "an error (logged), so the fixed macro", nil, {}, nil end
    if not text then why = why or "nothing found, so the fixed macro" end
    local body, kept = compose(b, text or b.fixed(n))
    b.state = { text = kept, why = why, expect = expect, saw = saw or {}, extra = extra or {} }
    b.body = body
    -- TK Sap and TK Pickpocket: a new choice (a player in Sap range, the next one to rob as you walk past) is
    -- written at once, without the 0.4 s wait (1.4.6, 1.4.7)
    local urgent = (b.name == "TKSap" or b.name == "TKPick") and kept ~= (b.live and b.live.text)
    write(b, force, urgent)
  end
end

local function resetMacros()                             -- the fixed macros, just before combat locks them
  if not db or InCombatLockdown() then return end
  for _, b in ipairs(BUTTONS) do
    local body, kept = compose(b, b.fixed(room(b)))
    b.state = { text = kept, why = "the fixed macro (in combat, or just before)", saw = {} }
    b.body = body
    write(b, true)
  end
end

local function afterPress(p)                             -- 0.3 s after a press: what the game ran, where the target went
  local b, st = p.b, p.st
  local after = UnitName("target") or "none"
  log("result", b.macro .. ": the game ran " .. (#p.ran > 0 and table.concat(p.ran, ", ") or "nothing we watch")
    .. "; target " .. p.before .. " -> " .. after)
  if st.expect and UnitName("target") ~= st.expect then
    log("WARN", b.macro .. ": it chose " .. (st.why or "?") .. ", but your target is " .. after
      .. " (the game didn't take the macro's target line)")
    if not saidMissed[b.name] then
      saidMissed[b.name] = true
      note("|cffff6060" .. b.macro .. " chose a target, but the game didn't target it|r (your target: " .. after
        .. "). /reload and tell Claude: the log has the details.")
    end
  end
  if b.name == "TKFind" and after == "none" and #db.find > 0 and GetTime() - saidNobody > 3 then
    saidNobody = GetTime()
    local msg = "TK Find: nobody on your find list (" .. table.concat(db.find, ", ") .. ") is near enough to target."
      .. " The game's own target-by-name found nobody either."
    log("result", msg)
    note(msg)
  end
  if b.name == "TKPick" and st.expect and UnitName("target") == st.expect then   -- its last unit, for the half-done rule
    last.pick.guid, last.pick.t = UnitGUID("target"), p.at
  end
end

local function onPress(b)                                -- the macro's last line ran: the press is real
  local st = b.live or b.state or { text = "", why = "?", saw = {} }
  local now = GetTime()
  watching = { macro = b.macro, untilT = now + 2 }
  local ran = {}
  for _, r in ipairs(recent) do if now - r.t <= 0.1 then ran[#ran + 1] = r.s end end
  recent = {}
  log("press", b.macro .. ": " .. (st.why or "?") .. " -> " .. st.text)
  if #st.saw > 0 then log("press", "  saw: " .. table.concat(st.saw, "; ")) end
  if debug then tell(b.macro .. ": " .. (st.why or "?") .. "\n" .. st.text) end
  if b.name == "TKFind" then
    if #db.find == 0 then
      local msg = "your find list is empty. /tkit add <name> adds one (part of a name is enough), or target"
        .. " something and type /tkit add."
      log("press", msg)
      note(msg)
    end
    local x = st.extra or {}
    if now - last.find.t > CYCLE or x.reset then last.find.names = {} end      -- a pause, or every name had
    last.find.names = last.find.names or {}
    if x.from then last.find.names[x.from] = true end
    if x.name then last.find.names[x.name] = true end
    last.find.t = now
  end
  local p = { b = b, st = st, ran = ran, before = targetBefore, at = now }
  if C_Timer then
    C_Timer.After(0, function() try("TargetKit choosing", prepare, true) end)    -- the next press: written fresh
    C_Timer.After(0.3, function() try(b.macro .. " result", afterPress, p) end)
  end
end

local function makeMarkers()
  for _, b in ipairs(BUTTONS) do
    if not b.mark then
      local mark = CreateFrame("Button", b.name .. "Mark", UIParent)          -- the macro's last line
      mark:SetSize(1, 1)
      mark:SetAlpha(0)
      mark:EnableMouse(false)
      mark:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", 0, 0)
      if hooksecurefunc then hooksecurefunc(mark, "Click", function() try(b.macro .. " press", onPress, b) end) end
      b.mark = mark
    end
  end
end

local function ensureMacros(create)                      -- make the three if they are missing (out of combat)
  if InCombatLockdown() or not GetMacroIndexByName then return end
  local made = {}
  for _, b in ipairs(BUTTONS) do
    local i = GetMacroIndexByName(b.macro)
    if i and i > 0 then
      b.written = nil                                    -- the next look writes it afresh
    elseif create then
      if GetNumMacros() < (MAX_ACCOUNT_MACROS or 120) then
        local body = b.body or compose(b, b.fixed(room(b)))
        CreateMacro(b.macro, b.icon, body, nil)
        b.written = nil
        made[#made + 1] = b.macro
        log("macros", b.macro .. ": made, " .. body)
      else
        note("your account macros are full, so " .. b.macro .. " could not be made. Free one and type /tkit macros.")
        log("WARN", b.macro .. ": not made, your account macros are full")
      end
    else
      log("macros", b.macro .. ": not in your macros (deleted?); /tkit macros makes it again")
    end
  end
  if #made > 0 then
    note("made the macros " .. table.concat(made, ", ") .. " (Escape > Macros, General tab): drag them to your bars."
      .. " TargetKit rewrites their text as you play, so leave it as it is.")
  end
end

-- ---------- events (the frame first: it also owns the keys) ----------
local ev = CreateFrame("Frame")

-- ---------- the find list ----------
local function addName(name)
  name = strtrim(name or "")
  if name == "" then return false, "type a name first (part of one is enough), or target something and use Add my target." end
  for _, w in ipairs(db.find) do
    if strlower(w) == strlower(name) then return false, w .. " is already on the find list." end
  end
  db.find[#db.find + 1] = name
  prepare(true)
  return true, "added " .. name .. " to the find list (" .. #db.find .. " on it). TK Find targets it, closest first."
end

local function removeName(name)
  for i, w in ipairs(db.find) do
    if strlower(w) == strlower(name or "") then
      table.remove(db.find, i)
      prepare(true)
      return true, "removed " .. w .. " from the find list."
    end
  end
  return false, (name or "?") .. " is not on the find list."
end

-- ---------- keys ----------
-- 1.1.0 (the user: "a minimap button would be nice too, for rebinding the macros (key combinations, key + key, should
-- be accepted)"). A key for each macro, saved in TargetKitDB and set again at every login as an override binding. It
-- runs the macro (1.4.0; no need to have it on a bar), it wins over the key's other uses while TargetKit is loaded, and your own key bindings stay as they were underneath: clear the key, or turn TargetKit off, and the key
-- does what it did before. WoW binds one key plus any of Shift, Ctrl and Alt, or mouse button 3 to 5 or the wheel; no
-- addon can bind two ordinary keys pressed together. Keys can't change in combat (the game forbids it).
local pendingKeys = false
local function applyKeys()                       -- returns { [button name] = what went wrong }
  local bad = {}
  if InCombatLockdown() then pendingKeys = true return bad end
  if not (ClearOverrideBindings and (SetOverrideBindingMacro or SetOverrideBinding)) then return bad end
  ClearOverrideBindings(ev)
  for _, b in ipairs(BUTTONS) do
    local key = db.keys[b.name]
    if key then
      if SetOverrideBindingMacro then SetOverrideBindingMacro(ev, true, key, b.macro)
      else SetOverrideBinding(ev, true, key, "MACRO " .. b.macro) end
      local now = GetBindingAction and GetBindingAction(key, true)
      if now == "MACRO " .. b.macro or not GetBindingAction then
        log("keys", b.macro .. " on " .. key)
      else
        local what = (now == nil or now == "") and "nothing" or tostring(now)
        log("WARN", b.macro .. " on " .. key .. ", but the key does " .. what .. " instead")
        bad[b.name] = b.macro .. "'s key " .. key .. " does something else (" .. what .. "). Set it again,"
          .. " or tell Claude: /reload saves the log."
        note("|cffff6060" .. bad[b.name] .. "|r")
      end
    end
  end
  return bad
end

local function keyText(key)
  if not key then return "|cff888888no key|r" end
  return (GetBindingText and GetBindingText(key)) or key
end

local function actionName(action)            -- what a key did before, in words; nil for nothing or one of ours
  if not action or action == "" then return nil end
  local clicked, macro = action:match("^CLICK ([^:]+)"), action:match("^MACRO (.+)$")
  for _, b in ipairs(BUTTONS) do if clicked == b.name or macro == b.macro then return nil end end
  return _G["BINDING_NAME_" .. action] or action
end

local function setKey(b, key)
  if InCombatLockdown() then return false, "keys can't change in combat; try again after it." end
  local before = GetBindingAction and actionName(GetBindingAction(key, true))
  for _, o in ipairs(BUTTONS) do if db.keys[o.name] == key then db.keys[o.name] = nil end end   -- one key, one macro
  db.keys[b.name] = key
  local bad = applyKeys()
  if bad[b.name] then return false, bad[b.name] end
  return true, b.macro .. " is on " .. keyText(key) .. " now" .. (before and (" (it was " .. before
    .. "; it does that again if you clear this key)") or "") .. "."
end

local function clearKey(b)
  if InCombatLockdown() then return false, "keys can't change in combat; try again after it." end
  if not db.keys[b.name] then return false, b.macro .. " has no key." end
  db.keys[b.name] = nil
  applyKeys()
  return true, b.macro .. " has no key now; the key does what it did before."
end

local MODIFIER = { LSHIFT = true, RSHIFT = true, LCTRL = true, RCTRL = true, LALT = true, RALT = true,
                   LMETA = true, RMETA = true }
local MOUSE = { MiddleButton = "BUTTON3", Button4 = "BUTTON4", Button5 = "BUTTON5" }    -- left and right: the interface's
local function withModifiers(key)                                                       -- the game's order: ALT-CTRL-SHIFT
  return (IsAltKeyDown() and "ALT-" or "") .. (IsControlKeyDown() and "CTRL-" or "") .. (IsShiftKeyDown() and "SHIFT-" or "")
    .. (IsMetaKeyDown and IsMetaKeyDown() and "META-" or "") .. key
end

-- ---------- the TargetKit window: keys and the find list (minimap button or /tkit) ----------
local panel, capturing, refreshPanel
local LIST_ROWS = 8

local function report(_, msg, typed)              -- typed: the answer to a /tkit command, so in chat too
  if typed then tell(msg) end
  log("window", msg)
  if panel then
    panel.status:SetText(msg)
    refreshPanel()
  end
end

local function stopCapture()
  capturing = nil
  if panel then
    panel.capture:EnableKeyboard(false)
    panel.capture:Hide()
  end
end

local function captured(key)
  local b = capturing
  stopCapture()
  if b then try("set a key", function() report(setKey(b, key)) end) end
end

local function startCapture(b)
  if InCombatLockdown() then report(false, "keys can't change in combat; try again after it.") return end
  capturing = b
  local c = panel.capture
  c.text:SetText("Press the key for " .. b.macro .. ",\nwith Shift, Ctrl or Alt if you like,\nor mouse button 3 to 5, or turn the"
    .. " mouse wheel.\n\nEscape or a left or right click cancels.")
  c:Show()
  c:EnableKeyboard(true)
  if c.SetPropagateKeyboardInput then c:SetPropagateKeyboardInput(false) end
end

local function backdrop(f, alpha)
  if f.SetBackdrop then
    f:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                    tile = true, tileSize = 16, edgeSize = 12, insets = { left = 3, right = 3, top = 3, bottom = 3 } })
    f:SetBackdropColor(0.04, 0.05, 0.07, alpha or 0.95)
    f:SetBackdropBorderColor(0.6, 0.8, 1, 0.8)
  end
end
local function label(parent, font, justify)
  local fs = parent:CreateFontString(nil, "OVERLAY", font or "GameFontHighlightSmall")
  fs:SetJustifyH(justify or "LEFT")
  return fs
end
local function button(parent, text, w, onClick)
  local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
  b:SetSize(w, 20)
  b:SetText(text)
  b:SetScript("OnClick", function(...) try("the " .. text .. " button", onClick, ...) end)
  return b
end
local function hover(frame, explain)
  frame:SetScript("OnEnter", function(self)
    if not GameTooltip then return end
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    GameTooltip:SetText(explain, 1, 1, 1, 1, true)
    GameTooltip:Show()
  end)
  frame:SetScript("OnLeave", function() if GameTooltip then GameTooltip:Hide() end end)
end

local function makePanel()
  panel = CreateFrame("Frame", "TargetKitPanel", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  panel:SetSize(360, 486)
  panel:SetPoint("CENTER", UIParent, "CENTER", 0, 60)
  panel:SetFrameStrata("DIALOG")
  panel:SetClampedToScreen(true)
  panel:EnableMouse(true)
  panel:SetMovable(true)
  panel:RegisterForDrag("LeftButton")
  panel:SetScript("OnDragStart", panel.StartMoving)
  panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
  backdrop(panel)
  if UISpecialFrames then table.insert(UISpecialFrames, "TargetKitPanel") end       -- Escape closes it
  local title = label(panel, "GameFontNormal")
  title:SetPoint("TOPLEFT", 14, -12)
  title:SetText("TargetKit " .. VERSION)
  local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -2, -2)

  local function head(text, hint, y)
    local h = label(panel, "GameFontNormalSmall")
    h:SetPoint("TOPLEFT", 14, y)
    h:SetText(text)
    local t = label(panel, "GameFontDisableSmall")
    t:SetPoint("TOPLEFT", 14, y - 14)
    t:SetWidth(332)
    t:SetText(hint)
  end

  head("Keys", "One key, with Shift, Ctrl or Alt if you like (Shift-F, Ctrl-Alt-3), or mouse button 3 to 5, or the wheel.", -40)
  panel.keys = {}
  for i, b in ipairs(BUTTONS) do
    local y = -78 - (i - 1) * 24
    local row = {}
    row.name = label(panel, "GameFontHighlight")
    row.name:SetPoint("TOPLEFT", 16, y - 3)
    row.name:SetText(b.macro)
    row.key = label(panel, "GameFontHighlightSmall")
    row.key:SetPoint("TOPLEFT", 132, y - 5)
    row.key:SetWidth(104)
    row.set = button(panel, "Set", 50, function() startCapture(b) end)
    row.set:SetPoint("TOPLEFT", 240, y)
    row.clear = button(panel, "Clear", 56, function() report(clearKey(b)) end)
    row.clear:SetPoint("LEFT", row.set, "RIGHT", 4, 0)
    hover(row.set, "Set the key for " .. b.macro .. ": click, then press the key, with Shift, Ctrl or Alt if you like.")
    hover(row.clear, "Take the key off " .. b.macro .. ". The key does what it did before.")
    panel.keys[i] = row
  end
  panel.bars = label(panel, "GameFontDisableSmall")
  panel.bars:SetPoint("TOPLEFT", 14, -152)
  panel.bars:SetWidth(332)

  head("Find list", "TK Find targets these, closest first. Part of a name is enough: \"thug\" finds Defias Thug.", -192)
  local input = CreateFrame("EditBox", "TargetKitPanelInput", panel, "InputBoxTemplate")
  input:SetSize(150, 20)
  input:SetPoint("TOPLEFT", 22, -226)
  input:SetAutoFocus(false)
  local function addTyped()
    report(addName(input:GetText()))
    input:SetText("")
    input:ClearFocus()
  end
  input:SetScript("OnEnterPressed", function() try("add a name", addTyped) end)
  input:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
  hover(input, "Type a name (or part of one) and press Enter to put it on the find list.")
  panel.input = input
  panel.add = button(panel, "Add", 50, addTyped)
  panel.add:SetPoint("LEFT", input, "RIGHT", 6, 0)
  panel.addTarget = button(panel, "Add my target", 110, function()
    local name = UnitName("target")
    if not name then report(false, "target something first, then click Add my target.") return end
    report(addName(name))
  end)
  panel.addTarget:SetPoint("LEFT", panel.add, "RIGHT", 4, 0)
  hover(panel.addTarget, "Put the name of what you have targeted now on the find list.")

  panel.rows = {}
  panel.offset = 0
  for i = 1, LIST_ROWS do
    local y = -256 - (i - 1) * 20
    local row = {}
    row.name = label(panel, "GameFontHighlightSmall")
    row.name:SetPoint("TOPLEFT", 18, y - 4)
    row.name:SetWidth(246)
    row.remove = button(panel, "Remove", 70, function() report(removeName(row.value)) end)
    row.remove:SetPoint("TOPLEFT", 272, y)
    panel.rows[i] = row
  end
  panel.more = label(panel, "GameFontDisableSmall")
  panel.more:SetPoint("TOPLEFT", 18, -256 - LIST_ROWS * 20 - 2)
  panel:EnableMouseWheel(true)
  panel:SetScript("OnMouseWheel", function(_, delta)                                -- a long list scrolls
    panel.offset = panel.offset - delta
    refreshPanel()
  end)

  local y = -256 - LIST_ROWS * 20 - 22
  panel.debug = button(panel, "Debug: off", 96, function() SlashCmdList.TARGETKIT("debug") refreshPanel() end)
  panel.debug:SetPoint("TOPLEFT", 14, y)
  hover(panel.debug, "Print in chat, on every press, what the macro chose and why.")
  panel.macros = button(panel, "Make the macros", 120, function() SlashCmdList.TARGETKIT("macros") end)
  panel.macros:SetPoint("LEFT", panel.debug, "RIGHT", 4, 0)
  hover(panel.macros, "Make TK Find, TK Pickpocket and TK Sap again in your macros, if you deleted them.")
  panel.forget = button(panel, "Forget robbed", 110, function() SlashCmdList.TARGETKIT("forget") end)
  panel.forget:SetPoint("LEFT", panel.macros, "RIGHT", 4, 0)
  hover(panel.forget, "TK Pickpocket forgets whom you have robbed, and may try them again.")
  panel.status = label(panel, "GameFontDisableSmall")
  panel.status:SetPoint("BOTTOMLEFT", 14, 12)
  panel.status:SetWidth(332)

  -- the key catcher: over the whole window while you press the key
  local c = CreateFrame("Button", nil, panel)
  c:SetAllPoints(panel)
  c:SetFrameLevel(panel:GetFrameLevel() + 20)
  local shade = c:CreateTexture(nil, "BACKGROUND")
  shade:SetAllPoints(c)
  shade:SetColorTexture(0, 0, 0, 0.88)
  c.text = label(c, "GameFontHighlight", "CENTER")
  c.text:SetPoint("CENTER")
  c.text:SetWidth(320)
  c:EnableMouse(true)
  c:EnableMouseWheel(true)
  c:SetScript("OnKeyDown", function(_, key)
    if key == "ESCAPE" then stopCapture() report(false, "no key set.") return end
    if MODIFIER[key] then return end                                                -- wait for the key with it
    captured(withModifiers(key))
  end)
  c:SetScript("OnMouseDown", function(_, mouse)
    local key = MOUSE[mouse]
    if key then captured(withModifiers(key)) else stopCapture() report(false, "no key set.") end
  end)
  c:SetScript("OnMouseWheel", function(_, delta)
    captured(withModifiers(delta > 0 and "MOUSEWHEELUP" or "MOUSEWHEELDOWN"))
  end)
  c:Hide()
  panel.capture = c
  panel:SetScript("OnShow", function() refreshPanel() end)
  panel:SetScript("OnHide", stopCapture)
  panel:Hide()
end

refreshPanel = function()
  if not panel then return end
  for i, b in ipairs(BUTTONS) do
    local row = panel.keys[i]
    row.key:SetText(keyText(db.keys[b.name]))
    if db.keys[b.name] then row.clear:Enable() else row.clear:Disable() end
  end
  panel.offset = math.max(0, math.min(panel.offset, #db.find - LIST_ROWS))
  for i, row in ipairs(panel.rows) do
    local name = db.find[panel.offset + i]
    row.value = name
    if name then
      row.name:SetText(name)
      row.remove:Show()
    else
      row.name:SetText(i == 1 and #db.find == 0 and "|cff888888empty: type a name above, or target something and"
        .. " click Add my target|r" or "")
      row.remove:Hide()
    end
  end
  local below = #db.find - panel.offset - LIST_ROWS
  panel.more:SetText((panel.offset > 0 or below > 0) and ("scroll for more: " .. panel.offset .. " above, "
    .. math.max(below, 0) .. " below") or "")
  panel.debug:SetText(debug and "Debug: on" or "Debug: off")
  panel.bars:SetText("On your bars: drag TK Find, TK Pickpocket or TK Sap from Escape > Macros (General tab)."
    .. " TargetKit rewrites their text as you play, so leave it as it is.")
end

local function togglePanel()
  if not panel then makePanel() end
  if panel:IsShown() then panel:Hide() else panel:Show() end
end

-- ---------- the minimap button ----------
-- A Sap icon on the minimap's edge: click it for the TargetKit window, drag it around the edge to move it (the place is
-- saved in TargetKitDB, account-wide, and kept through relogs and restarts). /tkit minimap hides or brings it back.
local mmButton
local function placeButton()
  local a = math.rad(db.minimap.angle or 235)
  local r = (Minimap:GetWidth() or 140) / 2 + 10
  mmButton:ClearAllPoints()
  mmButton:SetPoint("CENTER", Minimap, "CENTER", math.cos(a) * r, math.sin(a) * r)
end

local function makeMinimapButton()
  if mmButton or not Minimap then return end
  mmButton = CreateFrame("Button", "TargetKitMinimapButton", Minimap)
  mmButton:SetSize(31, 31)
  mmButton:SetFrameStrata("MEDIUM")
  mmButton:SetFrameLevel(8)
  mmButton:RegisterForClicks("AnyUp")
  mmButton:RegisterForDrag("LeftButton")
  mmButton:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  local border = mmButton:CreateTexture(nil, "OVERLAY")
  border:SetSize(53, 53)
  border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
  border:SetPoint("TOPLEFT")
  local back = mmButton:CreateTexture(nil, "BACKGROUND")
  back:SetSize(20, 20)
  back:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
  back:SetPoint("TOPLEFT", 7, -5)
  local icon = mmButton:CreateTexture(nil, "ARTWORK")
  icon:SetSize(17, 17)
  icon:SetTexture("Interface\\Icons\\Ability_Sap")
  icon:SetTexCoord(0.05, 0.95, 0.05, 0.95)
  icon:SetPoint("TOPLEFT", 7, -6)
  mmButton:SetScript("OnClick", function() try("open the window", togglePanel) end)
  mmButton:SetScript("OnDragStart", function(self)
    self:SetScript("OnUpdate", function()
      local mx, my = Minimap:GetCenter()
      local px, py = GetCursorPosition()
      local s = Minimap:GetEffectiveScale()
      db.minimap.angle = math.floor(math.deg((math.atan2 or atan2)(py / s - my, px / s - mx)) + 0.5) % 360
      placeButton()
    end)
  end)
  mmButton:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)
  hover(mmButton, "|cff9ad0ffTargetKit|r\nClick: the keys for TK Find, TK Pickpocket and TK Sap, and the find list.\n"
    .. "Drag: move this button around the minimap (the place is kept).")
  placeButton()
  if db.minimap.hide then mmButton:Hide() else mmButton:Show() end
end

-- ---------- events ----------
ev:RegisterEvent("PLAYER_LOGIN")
ev:RegisterEvent("PLAYER_REGEN_DISABLED")                -- fires just before combat locks the macros
ev:RegisterEvent("PLAYER_REGEN_ENABLED")
ev:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
ev:RegisterEvent("UI_ERROR_MESSAGE")
for _, e in ipairs({ "UNIT_SPELLCAST_FAILED", "PLAYER_TARGET_CHANGED", "ADDON_ACTION_BLOCKED",
                    "ADDON_ACTION_FORBIDDEN", "UPDATE_MOUSEOVER_UNIT", "NAME_PLATE_UNIT_ADDED",
                    "PLAYER_SOFT_ENEMY_CHANGED" }) do
  pcall(ev.RegisterEvent, ev, e)
end
local function outcome(...)                              -- something that came of the last press
  if watching and GetTime() <= watching.untilT then log("result", watching.macro .. ": " .. table.concat({ ... }, " ")) end
end
local pendingMacros = false
local acc = 0
ev:SetScript("OnUpdate", function(_, dt)
  acc = acc + (dt or 0)
  if acc < 0.2 then return end
  acc = 0
  if db and not InCombatLockdown() then try("TargetKit choosing", prepare, false) end
end)

local function onEvent(_, event, a1, a2, a3)
  if event == "PLAYER_LOGIN" then
    TargetKitDB = TargetKitDB or {}
    db = TargetKitDB
    for _, line in ipairs(early) do store(line) end
    early = {}
    local build = GetBuildInfo and select(2, GetBuildInfo())
    log("addon", "TargetKit " .. VERSION .. " loaded" .. (build and (", game build " .. build) or "")
      .. "; act on key down " .. cvar("ActionButtonUseKeyDown") .. ", enemy nameplates " .. cvar("nameplateShowEnemies")
      .. ", friendly nameplates " .. cvar("nameplateShowFriends") .. ", soft enemy target " .. cvar("SoftTargetEnemy")
      .. ", nameplate range " .. cvar("nameplateMaxDistance") .. "; find list: " .. #(db.find or {}) .. " names")
    db.find = db.find or {}
    db.picked = db.picked or {}
    db.keys = db.keys or {}
    db.minimap = db.minimap or {}
    for g, t in pairs(db.picked) do if time() - t >= KEEP_PICKED then db.picked[g] = nil end end
    makeMarkers()
    if InCombatLockdown() then pendingMacros = true else ensureMacros(not db.macrosMade); db.macrosMade = true end
    prepare(true)
    applyKeys()
    pcall(makeMinimapButton)
  elseif event == "PLAYER_REGEN_DISABLED" then
    resetMacros()
  elseif event == "PLAYER_REGEN_ENABLED" then
    if pendingMacros then pendingMacros = false; ensureMacros(not db.macrosMade); db.macrosMade = true end
    prepare(true)                                        -- out of combat again: look and write
    if pendingKeys then pendingKeys = false; applyKeys() end
  elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
    if a1 == "player" then outcome("cast", spellName(a3) or tostring(a3), "on", UnitName("target") or "no target") end
    if a1 == "player" and a3 == PICK_POCKET and db then        -- robbed: skip it from now on
      local g = UnitGUID("target")
      if known(g) then db.picked[g] = time() end
    end
  elseif event == "UNIT_SPELLCAST_FAILED" then
    if a1 == "player" then outcome(spellName(a3) or tostring(a3), "failed") end
  elseif event == "PLAYER_TARGET_CHANGED" then
    rememberName("target")
    outcome("target now", UnitName("target") or "none")
  elseif event == "UPDATE_MOUSEOVER_UNIT" then
    rememberName("mouseover")
  elseif event == "NAME_PLATE_UNIT_ADDED" or event == "PLAYER_SOFT_ENEMY_CHANGED" then
    if a1 and event == "NAME_PLATE_UNIT_ADDED" then rememberName(a1) end
    if db and not InCombatLockdown() then prepare(false) end         -- someone new in sight: look now
  elseif event == "ADDON_ACTION_BLOCKED" or event == "ADDON_ACTION_FORBIDDEN" then
    if a1 == "TargetKit" then
      log("ERROR", "the game blocked TargetKit from " .. tostring(a2) .. " (" .. event .. ")")
      note("|cffff6060the game blocked TargetKit from " .. tostring(a2) .. "|r. It's in the log: /tkit log.")
    end
  elseif event == "UI_ERROR_MESSAGE" then
    local msg = type(a2) == "string" and a2 or a1                -- (type, message); older clients: (message)
    outcome("the game said:", tostring(msg))
    local none = { SPELL_FAILED_TARGET_NO_POCKETS, ERR_ALREADY_PICKPOCKETED }
    for _, s in ipairs(none) do
      if s and msg == s and db then                               -- already robbed (by you before, or the game says so)
        local g = UnitGUID("target")
        if known(g) then db.picked[g] = time() end
      end
    end
  end
end
ev:SetScript("OnEvent", function(...)
  local _, event = ...
  try("event " .. tostring(event), onEvent, ...)
end)

-- ---------- /tkit ----------
SLASH_TARGETKIT1 = "/tkit"
SLASH_TARGETKIT2 = "/targetkit"
local function slash(msg)
  msg = strtrim(msg or "")
  local cmd, rest = msg:match("^(%S*)%s*(.-)$")
  cmd = strlower(cmd or "")
  if cmd == "" then
    togglePanel()
  elseif cmd == "add" then
    local name = rest ~= "" and rest or UnitName("target")
    if not name then tell("type /tkit add <name>, or target something first.") return end
    local _, said = addName(name)
    report(nil, said, true)
  elseif cmd == "remove" or cmd == "del" then
    local _, said = removeName(rest)
    report(nil, said, true)
  elseif cmd == "list" then
    tell(#db.find == 0 and "the find list is empty. /tkit add <name> adds one."
      or ("find list: " .. table.concat(db.find, ", ")))
  elseif cmd == "clear" then
    db.find = {}
    prepare(true)
    report(true, "the find list is empty now.", true)
  elseif cmd == "macros" then
    if InCombatLockdown() then tell("not in combat: try again after it.") return end
    ensureMacros(true)
    prepare(true)
    tell("macros checked: TK Find, TK Pickpocket, TK Sap (Escape > Macros, General tab).")
  elseif cmd == "forget" then
    db.picked = {}
    tell("forgot which units you have pickpocketed: TK Pickpocket may try them again.")
  elseif cmd == "chat" then
    db.chat = not db.chat
    tell("chat messages " .. (db.chat and "on: what TargetKit notices by itself (nobody near, warnings, errors) shows"
      .. " here too. /tkit chat turns them off." or "off: what TargetKit notices goes to the log only (/tkit log)."))
  elseif cmd == "debug" then
    debug = not debug
    tell("debug " .. (debug and "on: each press prints what it chose and the macro it ran." or "off."))
  elseif cmd == "log" then
    local l = db.log or {}
    if strlower(rest) == "clear" then
      db.log = {}
      tell("the log is empty now.")
    elseif #l == 0 then
      tell("the log is empty.")
    else
      local n = tonumber(rest) or 15
      tell("log, the last " .. math.min(n, #l) .. " of " .. #l .. " lines (/reload saves it to disk):")
      for i = math.max(1, #l - n + 1), #l do print("  " .. l[i]) end
    end
  elseif cmd == "minimap" then
    db.minimap.hide = not db.minimap.hide
    if not mmButton then pcall(makeMinimapButton) end
    if mmButton then if db.minimap.hide then mmButton:Hide() else mmButton:Show() end end
    tell("minimap button " .. (db.minimap.hide and "hidden. /tkit minimap brings it back." or "shown."))
  else
    tell(VERSION .. ". /tkit alone (or the minimap button) opens the window: keys for the macros and the find list.")
    tell("Macros: TK Find, TK Pickpocket, TK Sap (Escape > Macros, General tab), or give them keys in the window.")
    tell("TargetKit writes its choice into those macros as you play (out of combat), so use them as they are: a"
      .. " macro of your own can't run them (the game doesn't run a macro from inside another).")
    tell("/tkit add <name>: put a name (or part of one) on the find list; /tkit add alone adds your target's name.")
    tell("/tkit remove <name>, /tkit list, /tkit clear: change or see the find list.")
    tell("/tkit macros: make the three macros again if you deleted them. /tkit forget: TK Pickpocket forgets whom it robbed.")
    tell("/tkit debug: print what each press chose and why. /tkit minimap: hide or bring back the minimap button.")
    tell("/tkit chat: show in chat what TargetKit notices by itself (nobody near, warnings, errors); off by default,"
      .. " it all goes to the log.")
    tell("/tkit log: the last 15 lines of the log (every press, what came of it, errors); /tkit log 40 for more,"
      .. " /tkit log clear to empty it. /reload saves it to disk.")
  end
end
SlashCmdList.TARGETKIT = function(msg) try("/tkit " .. tostring(msg or ""), slash, msg) end
