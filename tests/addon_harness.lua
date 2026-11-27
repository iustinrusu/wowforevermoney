-- Stand-ins for the WoW API, enough to run ForeverMoneyBridge.lua (the loot log) and Meter.lua and drive them
-- (tests/test_meter_lua.py; WoW cannot run in tests)
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
HOOKS = {}                                      -- hooksecurefunc(table, name, fn) or (name, fn): kept so a test can call it
function hooksecurefunc(a, b, c) if type(a) == "string" then HOOKS[a] = b else HOOKS[b] = c end end
-- the open loot window: each slot's source GUID (nil: none given) and { link, quantity } (a coins slot: no link)
LOOT_SOURCES = { "Creature-0-1-2-3-4-5" }
LOOT_SLOTS = {}
function GetLootSourceInfo(slot) return LOOT_SOURCES[slot] end
function GetNumLootItems() return math.max(#LOOT_SLOTS, 1) end
function GetLootSlotLink(slot) return LOOT_SLOTS[slot] and LOOT_SLOTS[slot][1] end
function GetLootSlotInfo(slot) return "icon", "name", LOOT_SLOTS[slot] and LOOT_SLOTS[slot][2] or 0 end
-- your bags: bag -> slot -> { id, guid, locked, hasLoot }
BAGS = { [0] = {} }
C_Container = {
  GetContainerNumSlots = function(bag) return BAGS[bag] and 16 or 0 end,
  GetContainerItemID = function(bag, slot) local i = BAGS[bag] and BAGS[bag][slot]; return i and i.id end,
  GetContainerItemInfo = function(bag, slot) local i = BAGS[bag] and BAGS[bag][slot]
    return i and { itemID = i.id, isLocked = i.locked or false, hasLoot = i.hasLoot or false } end,
  UseContainerItem = function() end,
}
ItemLocation = { CreateFromBagAndSlot = function(_, bag, slot) return { bag = bag, slot = slot } end }
C_Item = {
  GetItemGUID = function(loc) local i = BAGS[loc.bag] and BAGS[loc.bag][loc.slot]
    if not i then error("invalid item location") end return i.guid end,
  GetItemCount = function(id) local n = 0
    for _, b in pairs(BAGS) do for _, i in pairs(b) do if i.id == id then n = n + 1 end end end return n end,
}
function GetRealmName() return "" end
function UnitName() return "Testchar" end
function UnitFactionGroup() return "Horde" end
function UnitClass() return "Rogue", "ROGUE" end
function IsFishingLoot() return false end
LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM_SELF_MULTIPLE = "You receive loot: %sx%d."
ITEM_OPENABLE, LOCKED = "<Right Click to Open>", "Locked"
UIParent = {}
SlashCmdList = { FOREVERMONEYBRIDGE = function() end }
ITEMS = { [8150] = { "Deeprock Salt", 250 }, [8171] = { "Rugged Hide", 500 }, [6359] = { "Firefin Snapper", 2 },
          [7973] = { "Big-mouth Clam", 0 }, [999] = { "Soulbound Thing", 77 }, [16885] = { "Heavy Junkbox", 0 } }
function GetItemInfo(id) local i = ITEMS[id]; if not i then return nil end
  return i[1], "link", 1, 1, 1, "t", "s", 20, "", "icon", i[2] end
TSM_PRICES = { [8150] = 313, [8171] = 520, [6359] = 1000 }
TSM_API = { GetCustomPriceValue = function(str, itemString) return TSM_PRICES[tonumber(itemString:match("i:(%d+)"))] end }
TOOLTIPS = { [7973] = { "Big-mouth Clam", "<Right Click to Open>" }, [8150] = { "Deeprock Salt" },
             [16885] = { "Heavy Junkbox", "Locked" } }
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
