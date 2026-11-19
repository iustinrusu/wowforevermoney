-- Stand-ins for the WoW API, enough to run Meter.lua and drive a session (tests/test_meter_lua.py; WoW cannot run in tests)
NOW, MONEY, XP, XPMAX, LEVEL = 1000, 50000, 1000, 50000, 40
printed = {}
function print(...) local t = {} for i = 1, select("#", ...) do t[#t + 1] = tostring(select(i, ...)) end printed[#printed + 1] = table.concat(t, " ") end
function GetTime() return NOW end
function time() return 1795000000 end
function GetMoney() return MONEY end
function UnitXP() return XP end
function UnitXPMax() return XPMAX end
function UnitLevel() return LEVEL end
function GetMaxPlayerLevel() return 60 end
function GetRealZoneText() return "Tanaris" end
function strlower(s) return string.lower(s) end
function strtrim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function strsplit(sep, s) local a = s:find(sep, 1, true); if a then return s:sub(1, a - 1), s:sub(a + 1) end return s end
function hooksecurefunc() end
function GetLootSourceInfo() return "Creature-0-1-2-3-4-5" end
function IsFishingLoot() return false end
LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM_SELF_MULTIPLE = "You receive loot: %sx%d."
ITEM_OPENABLE, LOCKED = "<Right Click to Open>", "Locked"
UIParent = {}
SlashCmdList = { FOREVERMONEYBRIDGE = function() end }
ITEMS = { [8150] = { "Deeprock Salt", 250 }, [8171] = { "Rugged Hide", 500 }, [6359] = { "Firefin Snapper", 2 },
          [7973] = { "Big-mouth Clam", 0 }, [999] = { "Soulbound Thing", 77 } }
function GetItemInfo(id) local i = ITEMS[id]; if not i then return nil end
  return i[1], "link", 1, 1, 1, "t", "s", 20, "", "icon", i[2] end
TSM_PRICES = { [8150] = 313, [8171] = 520, [6359] = 1000 }
TSM_API = { GetCustomPriceValue = function(str, itemString) return TSM_PRICES[tonumber(itemString:match("i:(%d+)"))] end }
TOOLTIPS = { [7973] = { "Big-mouth Clam", "<Right Click to Open>" }, [8150] = { "Deeprock Salt" } }
C_TooltipInfo = { GetItemByID = function(id) local l = {} for _, t in ipairs(TOOLTIPS[id] or {}) do l[#l + 1] = { leftText = t } end return { lines = l } end }
C_Timer = { After = function() end }

local function fontString()
  local fs = { text = "", shown = true }
  return setmetatable(fs, { __index = function(_, k)
    if k == "SetText" then return function(s, v) s.text = v end end
    if k == "SetWidth" then return function(s, v) s.width = v end end
    return function() end
  end })
end

-- frames remember what the meter's window code sets: size, shown, text, anchors (all of them, in order), resize
-- bounds. GetLeft / GetTop follow a TOPLEFT-to-BOTTOMLEFT anchor; any other anchor leaves them as they were.
local frameMethods = {
  SetScript = function(self, n, fn) self.scripts[n] = fn end,
  CreateFontString = function() return fontString() end,
  GetWidth = function(self) return self.w end,
  GetHeight = function(self) return self.h end,
  SetSize = function(self, w, h) self.w, self.h = w, h end,
  SetWidth = function(self, w) self.w = w end,
  SetHeight = function(self, h) self.h = h end,
  Show = function(self) self.shown = true end,
  Hide = function(self) self.shown = false end,
  IsShown = function(self) return self.shown end,
  SetText = function(self, t) self.text = t end,
  GetLeft = function(self) return self.left end,
  GetTop = function(self) return self.top end,
  ClearAllPoints = function(self) self.point = nil end,
  SetPoint = function(self, ...)
    self.point = { ... }
    self.points[#self.points + 1] = self.point
    local p, rel, relPoint, x, y = ...
    if p == "TOPLEFT" and rel == UIParent and relPoint == "BOTTOMLEFT" then self.left, self.top = x, y end
  end,
  GetPoint = function() return "CENTER", nil, "CENTER", 0, 0 end,
  SetResizeBounds = function(self, ...) self.bounds = { ... } end,
}
frames = {}
function CreateFrame()
  local f = { scripts = {}, shown = true, w = 320, h = 340, left = 500, top = 700, points = {} }
  setmetatable(f, { __index = function(_, k) return frameMethods[k] or function() end end })
  frames[#frames + 1] = f
  return f
end
