-- TargetKit: three one-key target helpers for WoW: Forever, each a macro the addon makes for you.
-- Not part of the WoW Forever Money app: it lives in the repo's extras/ folder and the app never copies it.
-- The request it follows (revised): extras/TargetKit/README.md.
--
--   TK Find        your find list (/tkit add <name>): the closest match first, each press within 8 s the next one.
--                  Dead mobs are skipped; dead players count, and dead friendly NPCs (a dead neutral or hostile unit
--                  could be a mob, so it is skipped).
--   TK Pickpocket  the closest humanoid you can rob (attackable, not a player, alive, not in combat, not pickpocketed
--                  yet): Sap, then Pick Pocket, in one press (Sap doesn't break stealth on Forever: the user, 2026-11-27).
--                  If one of the two was still on cooldown, the next press within 10 s on that unit does the other.
--   TK Sap         your mouseover enemy first. Else the closest enemy player in Sap range the addon can see; else the
--                  game's own nearest enemy player, which is how a stealthed player the game has just revealed gets
--                  caught (they have no nameplate, so the addon can't see them); else the closest NPC in Sap range;
--                  else the game's nearest enemy.
--
-- How, within WoW's rules: an addon may never pick a target by itself; only a key press on a secure button can, and
-- the button's macro can only be changed out of combat. So each macro is "/click TargetKitX". Just before the click
-- runs (PreClick), out of combat, the addon looks at every unit it can see (nameplates, target, mouseover, soft
-- targets, focus, your group), ranks them and writes the button's macro: "/target nameplate7" and the spell. In combat,
-- or when it finds nothing, the button runs a fixed macro made only of the game's own targeting.
-- Distance: the game gives addons no distance to other units, only "in range" checks, so "closest" is the nearest of
-- these bands: Pick Pocket's range (5 yd), Sap's range, 10 yd (duel), 11 yd (trade), 28 yd (follow), further. Within a
-- band, the unit whose nameplate is lower on the screen (usually nearer the camera) comes first.

local VERSION = "1.0.0"
local PICK_POCKET, SAP = 921, 6770
local SAP_IDS = { [6770] = true, [2070] = true, [11297] = true }        -- Sap, every rank
local HUMANOID = 7                                                       -- creature type id
local CYCLE = 8                       -- seconds: TK Find pressed again within this goes to the next match
local AGAIN = 10                      -- seconds: TK Pickpocket pressed again on its last unit finishes the job
local KEEP_PICKED = 2 * 3600          -- a robbed unit is skipped for 2 hours (a respawn is a new unit anyway)
local MAX_TEXT = 1000                 -- a button's macro text stays under the game's 1023 characters

local db
local debug = false
local function tell(...) print("|cff9ad0ffTargetKit|r", ...) end
local function say(...) if debug then tell(...) end end

local function spellName(id)
  local n = (C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(id)) or (GetSpellInfo and GetSpellInfo(id))
  return n
end
local function PP() return spellName(PICK_POCKET) or "Pick Pocket" end
local function SAPN() return spellName(SAP) or "Sap" end

-- ---------- what the addon can see about a unit ----------
local function inRange(id, unit)
  local name = spellName(id)
  local check = (C_Spell and C_Spell.IsSpellInRange) or IsSpellInRange
  if not (name and check) then return false end
  local ok, r = pcall(check, name, unit)
  return ok and (r == true or r == 1)
end

local function interact(unit, index)
  if not CheckInteractDistance then return false end
  local ok, r = pcall(CheckInteractDistance, unit, index)
  return ok and r and true or false
end

-- 1 Pick Pocket's range, 2 Sap's, 3 duel (10 yd), 4 trade (11 yd), 5 follow (28 yd), 6 further
local function reach(unit)
  if inRange(PICK_POCKET, unit) then return 1 end
  if inRange(SAP, unit) then return 2 end
  if interact(unit, 3) then return 3 end
  if interact(unit, 2) then return 4 end
  if interact(unit, 4) then return 5 end
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

local function dead(unit) return (UnitIsDeadOrGhost or UnitIsDead)(unit) and true or false end

-- every unit the addon can see, once each: nameplates first (their tokens are the steadiest for the click), then
-- mouseover, soft targets, target, focus and your group
local TOKENS = { "mouseover", "softenemy", "softinteract", "softfriend", "target", "focus" }
local function visibleUnits()
  local out, seen = {}, {}
  local function add(u)
    local ok, exists = pcall(UnitExists, u)
    if not (ok and exists) or UnitIsUnit(u, "player") then return end
    local g = UnitGUID(u)
    if g and not seen[g] then seen[g] = true; out[#out + 1] = { unit = u, guid = g } end
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

-- nearest band first; within a band, the nameplate lower on the screen first
local function rank(list)
  for _, c in ipairs(list) do
    c.reach = reach(c.unit)
    c.y = math.huge
    local plate = C_NamePlate and C_NamePlate.GetNamePlateForUnit and C_NamePlate.GetNamePlateForUnit(c.unit)
    if plate and plate.GetCenter then
      local _, y = plate:GetCenter()
      if y then c.y = y end
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

-- ---------- TK Sap ----------
local function sapFixed()
  local sap = SAPN()
  return table.concat({
    "/cast [@mouseover,harm,nodead] " .. sap,
    "/stopmacro [@mouseover,harm,nodead]",
    "/cleartarget [dead][noharm][noplayer]",          -- keep a living enemy player you already target
    "/targetenemyplayer [noexists]",                  -- the game's nearest enemy player: revealed stealthers too
    "/targetenemy [noexists]",
    "/cast " .. sap }, "\n")
end

local function sapBuild()
  local sap = SAPN()
  local players, npcs = {}, {}
  for _, c in ipairs(visibleUnits()) do
    local u = c.unit
    if UnitCanAttack("player", u) and not dead(u) and not UnitAffectingCombat(u) and isHumanoid(u) and not hasSap(u) then
      if UnitIsPlayer(u) then players[#players + 1] = c else npcs[#npcs + 1] = c end
    end
  end
  rank(players)
  rank(npcs)
  local head = { "/cast [@mouseover,harm,nodead] " .. sap, "/stopmacro [@mouseover,harm,nodead]" }
  local p = players[1]
  if p and p.reach <= 2 then
    head[#head + 1] = "/target " .. p.unit
    head[#head + 1] = "/cast " .. sap
    return table.concat(head, "\n"), "enemy player in Sap range: " .. describe(p)
  end
  local n = npcs[1]
  if n and n.reach > 2 then n = nil end
  head[#head + 1] = "/cleartarget [dead][noharm][noplayer]"
  head[#head + 1] = "/targetenemyplayer [noexists]"
  if n then head[#head + 1] = "/target [noexists] " .. n.unit end
  head[#head + 1] = "/targetenemy [noexists]"
  head[#head + 1] = "/cast " .. sap
  return table.concat(head, "\n"), "no enemy player in Sap range in sight: the game's nearest enemy player"
    .. (n and (", else " .. describe(n)) or "")
end

-- ---------- TK Pickpocket ----------
local last = { find = { t = 0, visited = {} }, pick = { guid = nil, t = 0 } }

local function picked(guid)
  local t = db.picked[guid]
  return t and time() - t < KEEP_PICKED
end

local function pickFixed()
  return table.concat({ "/targetenemy [noharm][dead]", "/cast " .. SAPN(), "/cast " .. PP() }, "\n")
end

local function pickBuild()
  -- its last unit, half done (Sap or Pick Pocket still on cooldown then): the missing half
  local t = UnitGUID("target")
  if t and t == last.pick.guid and GetTime() - last.pick.t <= AGAIN and not dead("target")
      and not UnitAffectingCombat("target") then
    local sapped, robbed = hasSap("target"), picked(t)
    if sapped and not robbed then
      last.pick.t = GetTime()
      return "/cast " .. PP(), "Pick Pocket the one just sapped: " .. (UnitName("target") or "?")
    elseif robbed and not sapped then
      last.pick.t = GetTime()
      return "/cast " .. SAPN(), "Sap the one just robbed: " .. (UnitName("target") or "?")
    end
  end
  local list = {}
  for _, c in ipairs(visibleUnits()) do
    local u = c.unit
    if UnitCanAttack("player", u) and not UnitIsPlayer(u) and not dead(u) and not UnitAffectingCombat(u)
        and isHumanoid(u) and not picked(c.guid) then
      list[#list + 1] = c
    end
  end
  rank(list)
  local c = list[1]
  if not c then return nil, "no humanoid to rob in sight" end
  local lines = { "/target " .. c.unit }
  if not hasSap(c.unit) then lines[#lines + 1] = "/cast " .. SAPN() end
  lines[#lines + 1] = "/cast " .. PP()
  last.pick.guid, last.pick.t = c.guid, GetTime()
  return table.concat(lines, "\n"), "closest to rob: " .. describe(c)
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

local function findable(unit)
  if not wanted(unit) then return false end
  if not dead(unit) then return true end
  if UnitIsPlayer(unit) then return true end             -- dead players count
  local r = UnitReaction(unit, "player")
  return r ~= nil and r >= 5                             -- a dead friendly NPC counts; neutral or hostile could be a mob
end

local function findFixed()                               -- by name: reaches units with no nameplate (far, or dead)
  local lines = { "/cleartarget" }
  local size = #lines[1]
  for _, w in ipairs(db.find) do
    local line = "/target [noexists] " .. w
    if size + #line + 40 > MAX_TEXT then break end
    lines[#lines + 1] = line
    size = size + #line + 1
  end
  lines[#lines + 1] = "/cleartarget [dead,noplayer]"     -- a dead mob found by name: let go of it
  return table.concat(lines, "\n")
end

local function findBuild()
  if #db.find == 0 then
    tell("your find list is empty. /tkit add <name> adds one (part of a name is enough), or target something and type /tkit add.")
    return "", "empty list"
  end
  local list = {}
  for _, c in ipairs(visibleUnits()) do
    if findable(c.unit) then list[#list + 1] = c end
  end
  rank(list)
  if #list == 0 then return nil, "none in sight: by name" end
  local now = GetTime()
  if now - last.find.t > CYCLE then last.find.visited = {} end
  local pick
  for _, c in ipairs(list) do
    if not last.find.visited[c.guid] then pick = c break end
  end
  if not pick then last.find.visited = {}; pick = list[1] end             -- all seen: round again, closest first
  last.find.visited[pick.guid] = true
  last.find.t = now
  local i = 0
  for k, c in ipairs(list) do if c == pick then i = k end end
  return "/target " .. pick.unit, describe(pick) .. ", " .. i .. " of " .. #list
end

-- ---------- the buttons and their macros ----------
local BUTTONS = {
  { name = "TargetKitFind", macro = "TK Find", icon = "INV_Misc_Spyglass_02", build = findBuild, fixed = findFixed },
  { name = "TargetKitPick", macro = "TK Pickpocket", icon = "INV_Misc_QuestionMark", show = PICK_POCKET,
    build = pickBuild, fixed = pickFixed },
  { name = "TargetKitSap", macro = "TK Sap", icon = "INV_Misc_QuestionMark", show = SAP, build = sapBuild, fixed = sapFixed },
}

local function resetButtons()                            -- back to the fixed macros (out of combat only)
  if InCombatLockdown() then return end
  for _, b in ipairs(BUTTONS) do
    if b.frame then b.frame:SetAttribute("macrotext", b.fixed()) end
  end
end

local function makeButtons()
  for _, b in ipairs(BUTTONS) do
    local f = CreateFrame("Button", b.name, UIParent, "SecureActionButtonTemplate")
    f:SetAttribute("type", "macro")
    f:SetAttribute("macrotext", b.fixed())
    f:RegisterForClicks("AnyUp", "AnyDown")
    f:Hide()                                             -- clicked by its macro, never seen
    f:SetScript("PreClick", function(self)
      if InCombatLockdown() then say(b.macro .. ": in combat, so the fixed macro") return end
      local ok, text, why = pcall(b.build)
      if not ok then text, why = nil, "error: " .. tostring(text) end
      text = text or b.fixed()
      self:SetAttribute("macrotext", text)
      say(b.macro .. ": " .. (why or "the fixed macro") .. "\n" .. text)
    end)
    f:SetScript("PostClick", function(self)
      if not InCombatLockdown() then self:SetAttribute("macrotext", b.fixed()) end
    end)
    b.frame = f
  end
end

local function macroBody(b)
  -- with "act on key down" on (the game's default), a /click must say so, or the secure button ignores it
  local down = GetCVarBool and GetCVarBool("ActionButtonUseKeyDown")
  local show = b.show and spellName(b.show)
  return (show and ("#showtooltip " .. show .. "\n") or "") .. "/click " .. b.name .. (down and " LeftButton 1" or "")
end

local function ensureMacros(create)
  if InCombatLockdown() or not GetMacroIndexByName then return end
  local made = {}
  for _, b in ipairs(BUTTONS) do
    local body = macroBody(b)
    local i = GetMacroIndexByName(b.macro)
    if i and i > 0 then
      local _, icon, old = GetMacroInfo(i)
      if old ~= body then EditMacro(i, b.macro, icon, body) end
    elseif create then
      local account = GetNumMacros()
      if account < (MAX_ACCOUNT_MACROS or 120) then
        CreateMacro(b.macro, b.icon, body, nil)
        made[#made + 1] = b.macro
      else
        tell("your account macros are full, so " .. b.macro .. " could not be made. Free one and type /tkit macros.")
      end
    end
  end
  if #made > 0 then
    tell("made the macros " .. table.concat(made, ", ") .. " (Escape > Macros, General tab): drag them to your bars.")
  end
end

-- ---------- events ----------
local ev = CreateFrame("Frame")
ev:RegisterEvent("PLAYER_LOGIN")
ev:RegisterEvent("PLAYER_REGEN_DISABLED")                -- fires just before combat locks the buttons
ev:RegisterEvent("PLAYER_REGEN_ENABLED")
ev:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
ev:RegisterEvent("UI_ERROR_MESSAGE")
pcall(ev.RegisterEvent, ev, "CVAR_UPDATE")
local pendingMacros = false
ev:SetScript("OnEvent", function(_, event, a1, a2, a3)
  if event == "PLAYER_LOGIN" then
    TargetKitDB = TargetKitDB or {}
    db = TargetKitDB
    db.find = db.find or {}
    db.picked = db.picked or {}
    for g, t in pairs(db.picked) do if time() - t >= KEEP_PICKED then db.picked[g] = nil end end
    makeButtons()
    if InCombatLockdown() then pendingMacros = true else ensureMacros(not db.macrosMade); db.macrosMade = true end
  elseif event == "PLAYER_REGEN_DISABLED" then
    resetButtons()
  elseif event == "PLAYER_REGEN_ENABLED" then
    if pendingMacros then pendingMacros = false; ensureMacros(not db.macrosMade); db.macrosMade = true end
  elseif event == "CVAR_UPDATE" then
    if db and (a1 == "ActionButtonUseKeyDown" or a1 == "ACTION_BUTTON_USE_KEY_DOWN") then
      if InCombatLockdown() then pendingMacros = true else ensureMacros(false) end
    end
  elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
    if a1 == "player" and a3 == PICK_POCKET and db then        -- robbed: skip it from now on
      local g = UnitGUID("target")
      if g then db.picked[g] = time() end
    end
  elseif event == "UI_ERROR_MESSAGE" then
    local msg = type(a2) == "string" and a2 or a1                -- (type, message); older clients: (message)
    local none = { SPELL_FAILED_TARGET_NO_POCKETS, ERR_ALREADY_PICKPOCKETED }
    for _, s in ipairs(none) do
      if s and msg == s and db then                               -- already robbed (by you before, or the game says so)
        local g = UnitGUID("target")
        if g then db.picked[g] = time() end
      end
    end
  end
end)

-- ---------- /tkit ----------
SLASH_TARGETKIT1 = "/tkit"
SLASH_TARGETKIT2 = "/targetkit"
SlashCmdList.TARGETKIT = function(msg)
  msg = strtrim(msg or "")
  local cmd, rest = msg:match("^(%S*)%s*(.-)$")
  cmd = strlower(cmd or "")
  if cmd == "add" then
    local name = rest ~= "" and rest or UnitName("target")
    if not name then tell("type /tkit add <name>, or target something first.") return end
    for _, w in ipairs(db.find) do
      if strlower(w) == strlower(name) then tell(w .. " is already on the find list.") return end
    end
    db.find[#db.find + 1] = name
    resetButtons()
    tell("added " .. name .. " to the find list (" .. #db.find .. " on it). TK Find targets it, closest first.")
  elseif cmd == "remove" or cmd == "del" then
    for i, w in ipairs(db.find) do
      if strlower(w) == strlower(rest) then
        table.remove(db.find, i)
        resetButtons()
        tell("removed " .. w .. " from the find list.")
        return
      end
    end
    tell(rest .. " is not on the find list. /tkit list shows it.")
  elseif cmd == "list" then
    tell(#db.find == 0 and "the find list is empty. /tkit add <name> adds one."
      or ("find list: " .. table.concat(db.find, ", ")))
  elseif cmd == "clear" then
    db.find = {}
    resetButtons()
    tell("the find list is empty now.")
  elseif cmd == "macros" then
    if InCombatLockdown() then tell("not in combat: try again after it.") return end
    ensureMacros(true)
    tell("macros checked: TK Find, TK Pickpocket, TK Sap.")
  elseif cmd == "forget" then
    db.picked = {}
    tell("forgot which units you have pickpocketed: TK Pickpocket may try them again.")
  elseif cmd == "debug" then
    debug = not debug
    tell("debug " .. (debug and "on: each press prints what it chose and the macro it ran." or "off."))
  else
    tell(VERSION .. ". Macros: TK Find, TK Pickpocket, TK Sap (Escape > Macros, General tab; drag them to your bars).")
    tell("/tkit add <name>: put a name (or part of one) on the find list; /tkit add alone adds your target's name.")
    tell("/tkit remove <name>, /tkit list, /tkit clear: change or see the find list.")
    tell("/tkit macros: make the three macros again if you deleted them. /tkit forget: TK Pickpocket forgets whom it robbed.")
    tell("/tkit debug: print what each press chose and why.")
  end
end
