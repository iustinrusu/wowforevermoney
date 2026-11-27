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
function UnitName(t) return U(t) and U(t).name end
function UnitIsDeadOrGhost(t) return U(t) and U(t).dead or false end
function UnitIsPlayer(t) return U(t) and U(t).player or false end
function UnitCanAttack(_, t) return U(t) and U(t).enemy or false end
function UnitAffectingCombat(t) return U(t) and U(t).combat or false end
function UnitCreatureType(t) local u = U(t); if not u then return nil end
  return (u.type or 7) == 7 and "Humanoid" or "Beast", u.type or 7 end
function UnitReaction(t) return U(t) and U(t).reaction end
C_Spell = {
  GetSpellName = function(id) return ({ [921] = "Pick Pocket", [6770] = "Sap" })[id] end,
  IsSpellInRange = function(name, t) local u = U(t); if not u then return nil end
    if name == "Pick Pocket" then return u.reach <= 1 end
    if name == "Sap" then return u.reach <= 2 end end,
}
function CheckInteractDistance(t, i) local u = U(t); if not u then return false end
  return u.reach <= ({ [3] = 3, [2] = 4, [4] = 5 })[i] end
C_UnitAuras = { GetDebuffDataByIndex = function(t, i) local u = U(t)
  if u and u.sapped and i == 1 then return { spellId = 6770 } end end }
C_NamePlate = {
  GetNamePlates = function() local out = {} for _, tok in ipairs(PLATES) do out[#out + 1] = { namePlateUnitToken = tok } end return out end,
  GetNamePlateForUnit = function(t) local u = U(t)
    if u and u.y then return { GetCenter = function() return 500, u.y end } end end,
}

-- macros: { name, icon, body }
MACROS = {}
MAX_ACCOUNT_MACROS = 120
function GetMacroIndexByName(n) for i, m in ipairs(MACROS) do if m.name == n then return i end end return 0 end
function GetMacroInfo(i) local m = MACROS[i]; return m.name, m.icon, m.body end
function EditMacro(i, n, icon, body) if COMBAT then error("blocked in combat") end MACROS[i] = { name = n, icon = icon, body = body } end
function CreateMacro(n, icon, body) if COMBAT then error("blocked in combat") end
  MACROS[#MACROS + 1] = { name = n, icon = icon, body = body } return #MACROS end
function GetNumMacros() return #MACROS, 0 end

UIParent = {}
SlashCmdList = {}
frames = {}
function CreateFrame(kind, name)
  local f = { scripts = {}, attrs = {}, kind = kind, name = name, shown = true }
  function f:SetAttribute(k, v) if COMBAT then error("blocked in combat") end self.attrs[k] = v end
  function f:GetAttribute(k) return self.attrs[k] end
  function f:SetScript(n, fn) self.scripts[n] = fn end
  function f:GetName() return self.name end
  function f:Hide() self.shown = false end
  function f:RegisterForClicks() end
  function f:RegisterEvent() end
  if name then _G[name] = f end
  frames[#frames + 1] = f
  return f
end
