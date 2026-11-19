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
  local fs = { text = "" }
  return setmetatable(fs, { __index = function(_, k)
    if k == "SetText" then return function(s, v) s.text = v end end
    return function() end
  end })
end
frames = {}
function CreateFrame()
  local f = { scripts = {} }
  setmetatable(f, { __index = function(_, k)
    if k == "SetScript" then return function(self, n, fn) self.scripts[n] = fn end end
    if k == "CreateFontString" then return function() return fontString() end end
    if k == "GetWidth" or k == "GetHeight" then return function() return 320 end end
    if k == "GetPoint" then return function() return "CENTER", nil, "CENTER", 0, 0 end end
    return function() end
  end })
  frames[#frames + 1] = f
  return f
end
