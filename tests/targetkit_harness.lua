-- Stand-ins for the WoW API, enough to run extras/TargetKit/TargetKit.lua and press its buttons
-- (tests/test_targetkit_lua.py; WoW cannot run in tests)
NOW, WALL = 1000, 1795000000
function GetTime() return NOW end
function time() return WALL end
printed = {}
function print(...) local t = {} for i = 1, select("#", ...) do t[#t + 1] = tostring(select(i, ...)) end printed[#printed + 1] = table.concat(t, " ") end
function strlower(s) return string.lower(s) end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
COMBAT = false
function InCombatLockdown() return COMBAT end
KEYDOWN = true
function GetCVarBool(name) if name == "ActionButtonUseKeyDown" then return KEYDOWN end end
function IsInRaid() return false end
-- secret values, as in battlegrounds on Forever (TargetKit 1.4.8): a unit field set to SECRET reads as a hidden value
SECRET = setmetatable({}, { __tostring = function() return "<secret>" end })
function issecretvalue(v) return v == SECRET end
-- what a secure macro calls (tests/test_targetkit_lua.py runs macro lines through these); hooksecurefunc as in WoW
-- A token, or a name (part of one; exact: the whole name): the closest unit of that name. As on Forever (TargetKit
-- 1.4.3's log), a nameplate's token is refused.
function TargetUnit(what, exact)
  if tostring(what):match("^nameplate%d+$") then return end
  if UNITS[what] then UNITS.target = UNITS[what] return end
  local w = tostring(what):lower()
  local best
  for tok, u in pairs(UNITS) do
    local n = u.name and u.name:lower()
    local full = n and u.realm and (n .. " " .. u.realm:lower())             -- "First Last" (Forever)
    if tok ~= "target" and n and ((exact and (n == w or full == w)) or (not exact and n:find(w, 1, true))) then
      local r, br = u.reach or 9, best and (best.reach or 9)
      if not best or r < br or (r == br and tostring(u.guid) < tostring(best.guid)) then best = u end
    end
  end
  if best then UNITS.target = best end
end
function ClearTarget() UNITS.target = nil end
NEAREST_ENEMY, NEAREST_PLAYER = nil, nil          -- what the game's own Tab targeting would find (nil: nobody)
TAB, FTAB = {}, {}                                -- or the game's Tab order, enemies and friendly units: the next one
local function tabNext(order)
  if #order == 0 then return end
  for i, u in ipairs(order) do
    if u == UNITS.target then UNITS.target = order[i % #order + 1] return end
  end
  UNITS.target = order[1]
end
function TargetNearestEnemy() if NEAREST_ENEMY then UNITS.target = NEAREST_ENEMY return end tabNext(TAB) end
function TargetNearestFriend() tabNext(FTAB) end
function TargetNearestEnemyPlayer() if NEAREST_PLAYER then UNITS.target = NEAREST_PLAYER end end
function TargetLastTarget() end
function CastSpellByName() end
function hooksecurefunc(a, b, c)                -- (name, hook) on a global, or (table, name, hook)
  local t, name, fn = _G, a, b
  if type(a) == "table" then t, name, fn = a, b, c end
  local orig = t[name]
  t[name] = function(...) local r = orig(...); fn(...); return r end
end
TIMERS = {}                                     -- C_Timer.After; RUN_TIMERS() runs those due by NOW, in order
C_Timer = { After = function(delay, f) TIMERS[#TIMERS + 1] = { at = NOW + delay, f = f } end }
function RUN_TIMERS()
  local due = {}
  for i = #TIMERS, 1, -1 do if TIMERS[i].at <= NOW then table.insert(due, table.remove(TIMERS, i)) end end
  table.sort(due, function(x, y) return x.at < y.at end)
  for _, t in ipairs(due) do t.f() end
end
CVARS = { ActionButtonUseKeyDown = "1", nameplateShowEnemies = "1", nameplateShowFriends = "0", SoftTargetEnemy = "1",
          nameplateMaxDistance = "41" }
function GetCVar(name) return CVARS[name] end
SPELL_FAILED_TARGET_NO_POCKETS = "No pockets to pick"

-- units by token: { guid, name, reach (1 Pick Pocket range, 2 Sap range, 3 duel, 4 trade, 5 follow, 6 further),
-- y (its nameplate's height on screen; nil: no nameplate), enemy, player, dead, combat, sapped, type, reaction }.
-- Two tokens can share one table (the target is also a nameplate).
UNITS = {}
PLATES = {}                                     -- tokens that have a nameplate, in the game's order
local function U(t) return UNITS[t] end
function UnitExists(t) return U(t) ~= nil end
function UnitIsUnit(a, b) local x, y = U(a), U(b); return x ~= nil and x == y end
function UnitGUID(t) return U(t) and U(t).guid end
function UnitName(t) local u = U(t); if not u then return nil end return u.name, u.realm end   -- realm: Forever's last name
function UnitIsDeadOrGhost(t) return U(t) and U(t).dead or false end
function UnitIsPlayer(t) return U(t) and U(t).player or false end
function UnitCanAttack(_, t) return U(t) and U(t).enemy or false end
function UnitAffectingCombat(t) return U(t) and U(t).combat or false end
function UnitCreatureType(t) local u = U(t); if not u then return nil end
  return (u.type or 7) == 7 and "Humanoid" or "Beast", u.type or 7 end
function UnitReaction(t) return U(t) and U(t).reaction end
C_Spell = {
  GetSpellName = function(id) return ({ [921] = "Pick Pocket", [6770] = "Sap", [1752] = "Sinister Strike" })[id] end,
  IsSpellInRange = function(name, t) local u = U(t); if not u then return nil end
    if name == "Pick Pocket" then if u.player then return nil end return u.reach <= 1 end   -- NPCs only: no answer
    if name == "Sinister Strike" then return u.reach <= 1 end                               -- melee range
    if name == "Sap" then return u.reach <= 2 end end,
}
PROFILE_MS = 0                                  -- debugprofilestop: a look takes PROFILE_STEP ms
PROFILE_STEP = 0.4
function debugprofilestop() PROFILE_MS = PROFILE_MS + PROFILE_STEP return PROFILE_MS end
function CheckInteractDistance(t, i) local u = U(t); if not u then return false end
  return u.reach <= ({ [3] = 3, [2] = 4, [4] = 5 })[i] end
C_UnitAuras = { GetDebuffDataByIndex = function(t, i) local u = U(t)
  if u and u.sapped and i == 1 then return { spellId = 6770 } end end,
  GetBuffDataByIndex = function(t, i) local u = U(t)                       -- stealthed: Stealth on the unit
    if u and u.stealthed and i == 1 then return { spellId = 1784, name = "Stealth" } end end }
C_NamePlate = {
  GetNamePlates = function() local out = {} for _, tok in ipairs(PLATES) do out[#out + 1] = { namePlateUnitToken = tok } end return out end,
  GetNamePlateForUnit = function(t) local u = U(t)
    if u and u.y then return { GetCenter = function() return 500, u.y end } end end,
}

-- macros: { name, icon, body }
MACROS = {}
MAX_ACCOUNT_MACROS = 120
function GetMacroIndexByName(n) for i, m in ipairs(MACROS) do if m.name == n then return i end end return 0 end
function GetMacroInfo(i) local m = MACROS[i]; if not m then return nil end return m.name, m.icon, m.body end
EDITS = 0
function EditMacro(i, n, icon, body)            -- icon nil: keep it
  if COMBAT then error("blocked in combat") end
  if #body > 255 then error("a macro takes 255 characters") end
  EDITS = EDITS + 1
  MACROS[i] = { name = n, icon = icon or MACROS[i].icon, body = body }
end
function CreateMacro(n, icon, body) if COMBAT then error("blocked in combat") end
  MACROS[#MACROS + 1] = { name = n, icon = icon, body = body } return #MACROS end
function GetNumMacros() return #MACROS, 0 end

UIParent = {}
SlashCmdList = {}
Minimap = { GetWidth = function() return 140 end, GetCenter = function() return 1800, 950 end,
            GetEffectiveScale = function() return 1 end }
CURSOR = { 0, 0 }
function GetCursorPosition() return CURSOR[1], CURSOR[2] end
TOOLTIP = nil
GameTooltip = { SetOwner = function() end, SetText = function(_, t) TOOLTIP = t end, Show = function() end,
                Hide = function() TOOLTIP = nil end }
MODS = { alt = false, ctrl = false, shift = false }      -- the modifier keys held down
function IsAltKeyDown() return MODS.alt end
function IsControlKeyDown() return MODS.ctrl end
function IsShiftKeyDown() return MODS.shift end
-- key bindings: the user's own (BINDINGS) and the override bindings addons set (OVERRIDES)
BINDINGS = { ["SHIFT-F"] = "MOVEFORWARD" }
BINDING_NAME_MOVEFORWARD = "Move Forward"
OVERRIDES = {}
function SetOverrideBindingMacro(owner, priority, key, macro)
  if COMBAT then error("blocked in combat") end
  OVERRIDES[key] = { macro = macro, priority = priority }
end
function ClearOverrideBindings() if COMBAT then error("blocked in combat") end OVERRIDES = {} end
function GetBindingAction(key, checkOverride)
  if checkOverride and OVERRIDES[key] then return "MACRO " .. OVERRIDES[key].macro end
  return BINDINGS[key] or ""
end
function GetBindingText(key) return (key:gsub("SHIFT%-", "Shift-"):gsub("CTRL%-", "Ctrl-"):gsub("ALT%-", "Alt-")) end

local function widget()                         -- font strings and textures: they keep their text and shown state
  return setmetatable({ text = "", shown = true }, { __index = function(_, k)
    if k == "SetText" then return function(w, v) w.text = v end end
    if k == "GetText" then return function(w) return w.text end end
    if k == "Show" then return function(w) w.shown = true end end
    if k == "Hide" then return function(w) w.shown = false end end
    return function() end
  end })
end

-- frames keep what the addon and the tests look at; any other method does nothing
local frameMethods = {
  SetAttribute = function(self, k, v) if COMBAT then error("blocked in combat") end self.attrs[k] = v end,
  GetAttribute = function(self, k) return self.attrs[k] end,
  SetScript = function(self, n, fn) self.scripts[n] = fn end,
  GetName = function(self) return self.name end,
  Show = function(self) self.shown = true; if self.scripts.OnShow then self.scripts.OnShow(self) end end,
  Hide = function(self)
    local was = self.shown
    self.shown = false
    if was and self.scripts.OnHide then self.scripts.OnHide(self) end
  end,
  IsShown = function(self) return self.shown end,
  SetText = function(self, t) self.text = t end,
  GetText = function(self) return self.text end,
  Enable = function(self) self.enabled = true end,
  Disable = function(self) self.enabled = false end,
  EnableKeyboard = function(self, on) self.keyboard = on end,
  CreateFontString = function() return widget() end,
  CreateTexture = function() return widget() end,
  GetFrameLevel = function() return 1 end,
  SetPoint = function(self, ...) self.point = { ... } end,
  GetCenter = function(self) return rawget(self, "cx"), rawget(self, "cy") end,
  Click = function(self, ...) if self.scripts.OnClick then self.scripts.OnClick(self, ...) end end,
}
frames = {}
function CreateFrame(kind, name, parent, template)
  local f = { scripts = {}, attrs = {}, kind = kind, name = name, shown = true, text = "", enabled = true,
              template = template }
  setmetatable(f, { __index = function(_, k) return frameMethods[k] or function() end end })
  if name then _G[name] = f end
  frames[#frames + 1] = f
  return f
end
