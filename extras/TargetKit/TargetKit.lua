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
-- the button's macro can only be changed out of combat. So each macro is "/click TKFind" (TKPick, TKSap). Just
-- before the click
-- runs (PreClick), out of combat, the addon looks at every unit it can see (nameplates, target, mouseover, soft
-- targets, focus, your group), ranks them and writes the button's macro: "/target nameplate7" and the spell. In combat,
-- or when it finds nothing, the button runs a fixed macro made only of the game's own targeting.
-- Distance: the game gives addons no distance to other units, only "in range" checks, so "closest" is the nearest of
-- these bands: Pick Pocket's range (5 yd), Sap's range, 10 yd (duel), 11 yd (trade), 28 yd (follow), further. Within a
-- band, the unit whose nameplate is lower on the screen (usually nearer the camera) comes first.

local VERSION = "1.1.0"
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
  { name = "TKFind", macro = "TK Find", icon = "INV_Misc_Spyglass_02", build = findBuild, fixed = findFixed },
  { name = "TKPick", macro = "TK Pickpocket", icon = "INV_Misc_QuestionMark", show = PICK_POCKET,
    build = pickBuild, fixed = pickFixed },
  { name = "TKSap", macro = "TK Sap", icon = "INV_Misc_QuestionMark", show = SAP, build = sapBuild, fixed = sapFixed },
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

-- The line a macro needs to press one of the buttons. An addon's own slash command can't target or cast (WoW blocks
-- addon code from that), so /click on the secure button is the only way, in our macros and in your own (1.1.0, the
-- user: "being able to create a macro to /use_addon_target, /use_addon_pickpocket, /use_addon_sap ... so I can have
-- them on my action bars"). With "act on key down" on (the game's default), the /click must say so ("LeftButton 1"),
-- or the secure button ignores it.
local function clickLine(name)
  local down = GetCVarBool and GetCVarBool("ActionButtonUseKeyDown")
  return "/click " .. name .. (down and " LeftButton 1" or "")
end

local function macroBody(b)
  local show = b.show and spellName(b.show)
  return (show and ("#showtooltip " .. show .. "\n") or "") .. clickLine(b.name)
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
  resetButtons()
  return true, "added " .. name .. " to the find list (" .. #db.find .. " on it). TK Find targets it, closest first."
end

local function removeName(name)
  for i, w in ipairs(db.find) do
    if strlower(w) == strlower(name or "") then
      table.remove(db.find, i)
      resetButtons()
      return true, "removed " .. w .. " from the find list."
    end
  end
  return false, (name or "?") .. " is not on the find list."
end

-- ---------- keys ----------
-- 1.1.0 (the user: "a minimap button would be nice too, for rebinding the macros (key combinations, key + key, should
-- be accepted)"). A key for each macro, saved in TargetKitDB and set again at every login as an override binding. It
-- clicks the macro's button directly (no macro on a bar needed), it wins over the key's other uses while TargetKit is
-- loaded, and your own key bindings stay as they were underneath: clear the key, or turn TargetKit off, and the key
-- does what it did before. WoW binds one key plus any of Shift, Ctrl and Alt, or mouse button 3 to 5 or the wheel; no
-- addon can bind two ordinary keys pressed together. Keys can't change in combat (the game forbids it).
local pendingKeys = false
local function applyKeys()
  if InCombatLockdown() then pendingKeys = true return end
  if not (ClearOverrideBindings and SetOverrideBindingClick) then return end
  ClearOverrideBindings(ev)
  for _, b in ipairs(BUTTONS) do
    local key = db.keys[b.name]
    if key then SetOverrideBindingClick(ev, true, key, b.name, "LeftButton") end
  end
end

local function keyText(key)
  if not key then return "|cff888888no key|r" end
  return (GetBindingText and GetBindingText(key)) or key
end

local function actionName(action)            -- what a key did before, in words; nil for nothing or one of ours
  if not action or action == "" then return nil end
  local clicked = action:match("^CLICK ([^:]+)")
  for _, b in ipairs(BUTTONS) do if clicked == b.name then return nil end end
  return _G["BINDING_NAME_" .. action] or action
end

local function setKey(b, key)
  if InCombatLockdown() then return false, "keys can't change in combat; try again after it." end
  local before = GetBindingAction and actionName(GetBindingAction(key, true))
  for _, o in ipairs(BUTTONS) do if db.keys[o.name] == key then db.keys[o.name] = nil end end   -- one key, one macro
  db.keys[b.name] = key
  applyKeys()
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

local function report(_, msg)
  tell(msg)
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
  if b then report(setKey(b, key)) end
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
  b:SetScript("OnClick", onClick)
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
  input:SetScript("OnEnterPressed", addTyped)
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
  panel.bars:SetText("On your bars: drag TK Find, TK Pickpocket or TK Sap from Escape > Macros (General tab), or"
    .. " put this line in a macro of your own: " .. clickLine("TKSap") .. " (or TKPick, TKFind).")
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
  mmButton:SetScript("OnClick", togglePanel)
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
    db.keys = db.keys or {}
    db.minimap = db.minimap or {}
    for g, t in pairs(db.picked) do if time() - t >= KEEP_PICKED then db.picked[g] = nil end end
    makeButtons()
    if InCombatLockdown() then pendingMacros = true else ensureMacros(not db.macrosMade); db.macrosMade = true end
    applyKeys()
    pcall(makeMinimapButton)
  elseif event == "PLAYER_REGEN_DISABLED" then
    resetButtons()
  elseif event == "PLAYER_REGEN_ENABLED" then
    resetButtons()                                       -- a find list changed in combat
    if pendingMacros then pendingMacros = false; ensureMacros(not db.macrosMade); db.macrosMade = true end
    if pendingKeys then pendingKeys = false; applyKeys() end
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
  if cmd == "" then
    togglePanel()
  elseif cmd == "add" then
    local name = rest ~= "" and rest or UnitName("target")
    if not name then tell("type /tkit add <name>, or target something first.") return end
    report(addName(name))
  elseif cmd == "remove" or cmd == "del" then
    report(removeName(rest))
  elseif cmd == "list" then
    tell(#db.find == 0 and "the find list is empty. /tkit add <name> adds one."
      or ("find list: " .. table.concat(db.find, ", ")))
  elseif cmd == "clear" then
    db.find = {}
    resetButtons()
    report(true, "the find list is empty now.")
  elseif cmd == "macros" then
    if InCombatLockdown() then tell("not in combat: try again after it.") return end
    ensureMacros(true)
    tell("macros checked: TK Find, TK Pickpocket, TK Sap. In a macro of your own, these lines press them: "
      .. clickLine("TKFind") .. ", " .. clickLine("TKPick") .. ", " .. clickLine("TKSap") .. ".")
  elseif cmd == "forget" then
    db.picked = {}
    tell("forgot which units you have pickpocketed: TK Pickpocket may try them again.")
  elseif cmd == "debug" then
    debug = not debug
    tell("debug " .. (debug and "on: each press prints what it chose and the macro it ran." or "off."))
  elseif cmd == "minimap" then
    db.minimap.hide = not db.minimap.hide
    if not mmButton then pcall(makeMinimapButton) end
    if mmButton then if db.minimap.hide then mmButton:Hide() else mmButton:Show() end end
    tell("minimap button " .. (db.minimap.hide and "hidden. /tkit minimap brings it back." or "shown."))
  else
    tell(VERSION .. ". /tkit alone (or the minimap button) opens the window: keys for the macros and the find list.")
    tell("Macros: TK Find, TK Pickpocket, TK Sap (Escape > Macros, General tab), or give them keys in the window.")
    tell("In a macro of your own: " .. clickLine("TKFind") .. ", " .. clickLine("TKPick") .. " or " .. clickLine("TKSap")
      .. " (an addon's own /command can't target or cast; /click on its button can).")
    tell("/tkit add <name>: put a name (or part of one) on the find list; /tkit add alone adds your target's name.")
    tell("/tkit remove <name>, /tkit list, /tkit clear: change or see the find list.")
    tell("/tkit macros: make the three macros again if you deleted them. /tkit forget: TK Pickpocket forgets whom it robbed.")
    tell("/tkit debug: print what each press chose and why. /tkit minimap: hide or bring back the minimap button.")
  end
end
