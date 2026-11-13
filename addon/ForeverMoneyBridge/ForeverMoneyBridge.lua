-- ForeverMoneyBridge: feeds the WoW Forever Money desktop app.
-- Records a snapshot of the current character (level, gold, faction, professions) and a log of
-- every loot window by zone and activity (fishing, skinning, herbalism, mining, mob loot), with the
-- active time spent, so the app can compute real gold per hour, plus what containers you open contain.
-- WoW only writes SavedVariables to disk on logout or /reload; the app picks them up then.

local ADDON = ...
local VERSION = 3
local f = CreateFrame("Frame")

local ACTIVITY_SPELLS = {
  ["Fishing"] = "fishing", ["Skinning"] = "skinning", ["Herb Gathering"] = "herbalism",
  ["Mining"] = "mining", ["Disenchant"] = "disenchant",
}
local IDLE_GAP = 120      -- seconds; longer gaps between loots don't count as active time
local CAST_WINDOW = 15    -- loot within this many seconds of a gathering cast belongs to it
local FISHING_BOBBER = 35591   -- gameobject id of the fishing bobber (open-water catches)

local lastCast = { activity = nil, t = 0 }
local lastLoot = {}       -- activity -> time of previous loot (for active time)

local function charKey()
  return (UnitName("player") or "?") .. " - " .. (GetRealmName() or "?")
end

local function db()
  ForeverMoneyBridgeDB = ForeverMoneyBridgeDB or {}
  local d = ForeverMoneyBridgeDB
  d.version = VERSION
  d.characters = d.characters or {}
  d.activity = d.activity or {}
  return d
end

local function professions()
  local out = {}
  if GetNumSkillLines and GetSkillLineInfo then
    for i = 1, GetNumSkillLines() do
      local name, isHeader, _, rank, _, _, maxRank = GetSkillLineInfo(i)
      if name and not isHeader and maxRank and maxRank > 1 then
        out[name] = { rank = rank, max = maxRank }
      end
    end
  end
  if next(out) == nil and GetProfessions and GetProfessionInfo then
    for _, idx in pairs({ GetProfessions() }) do
      if idx then
        local name, _, rank, maxRank = GetProfessionInfo(idx)
        if name then out[name] = { rank = rank, max = maxRank } end
      end
    end
  end
  return out
end

local function snapshot()
  local d = db()
  local c = d.characters[charKey()] or {}
  c.name = UnitName("player")
  c.realm = GetRealmName()
  c.faction = UnitFactionGroup("player")
  c.level = UnitLevel("player")
  c.class = select(2, UnitClass("player"))
  c.money = GetMoney()
  local profs = professions()
  if next(profs) ~= nil then c.professions = profs end
  c.zone = GetRealZoneText and GetRealZoneText() or nil
  c.updated = time()
  d.characters[charKey()] = c
  d.lastCharacter = charKey()
end

local function itemIdFromLink(link)
  return link and tonumber(link:match("item:(%d+)"))
end

-- Containers opened from your bags (trunks, clams, crates): remember which bag item was used last, and
-- log what the loot window gave under that item, not as fishing or mob loot.
local lastUsed = { id = nil, t = 0 }
local USE_WINDOW = 3      -- seconds between right-clicking a bag item and its loot window

local function rememberUse(bag, slot)
  local id
  if C_Container and C_Container.GetContainerItemID then id = C_Container.GetContainerItemID(bag, slot)
  elseif GetContainerItemID then id = GetContainerItemID(bag, slot) end
  if id then lastUsed.id, lastUsed.t = id, GetTime() end
end
if C_Container and C_Container.UseContainerItem then hooksecurefunc(C_Container, "UseContainerItem", rememberUse) end
if UseContainerItem then hooksecurefunc("UseContainerItem", rememberUse) end

local function lootSourceKind()
  -- "Item" = a container from your bags, "GameObject" = bobber/node/chest, "Creature" = a mob
  if not GetLootSourceInfo then return nil end
  local guid = GetLootSourceInfo(1)
  return guid and (strsplit("-", guid)) or nil
end

local function recordContainer(id)
  local d = db()
  d.containers = d.containers or {}
  local c = d.containers[id] or { opened = 0, items = {} }
  d.containers[id] = c
  c.opened = c.opened + 1
  c.lastSeen = time()
  for slot = 1, (GetNumLootItems and GetNumLootItems() or 0) do
    local got = itemIdFromLink(GetLootSlotLink and GetLootSlotLink(slot))
    local _, _, quantity = GetLootSlotInfo(slot)
    if got then c.items[got] = (c.items[got] or 0) + (quantity or 1) end
  end
end

local function recordLoot()
  local now = GetTime()
  local fromBag = lastUsed.id and now - lastUsed.t <= USE_WINDOW
  local kind = lootSourceKind()
  if kind == "Item" or (kind == nil and fromBag and not (IsFishingLoot and IsFishingLoot())) then
    if fromBag then recordContainer(lastUsed.id) end
    lastUsed.id = nil
    return                    -- never count container contents as fishing or mob loot
  end
  local activity
  if IsFishingLoot and IsFishingLoot() then
    activity = "fishing"
  elseif lastCast.activity and now - lastCast.t <= CAST_WINDOW then
    activity = lastCast.activity
  else
    activity = "mobs"
  end
  lastCast.activity = nil
  local zone = (GetRealZoneText and GetRealZoneText()) or "?"
  local d = db()
  d.activity[zone] = d.activity[zone] or {}
  local a = d.activity[zone][activity] or { loots = 0, seconds = 0, items = {}, money = 0 }
  d.activity[zone][activity] = a
  a.loots = a.loots + 1
  local prev = lastLoot[activity]
  if prev and now - prev <= IDLE_GAP then
    a.seconds = a.seconds + (now - prev)
  end
  lastLoot[activity] = now
  a.lastSeen = time()
  -- Fishing: which object the catch came from. The bobber = open water; another object = a pool (Floating
  -- Wreckage, a school...). Lets the app measure how much of your fishing is pools instead of assuming it.
  local pool
  if activity == "fishing" and GetLootSourceInfo then
    local guid = GetLootSourceInfo(1)
    local gkind, _, _, _, _, oid = strsplit("-", guid or "")
    oid = (gkind == "GameObject") and tonumber(oid) or 0
    a.sources = a.sources or {}
    a.sources[oid] = (a.sources[oid] or 0) + 1
    if oid ~= 0 and oid ~= FISHING_BOBBER then
      a.pools = a.pools or {}
      pool = a.pools[oid] or { loots = 0, items = {}, firstSeen = time() }
      a.pools[oid] = pool
      pool.loots = pool.loots + 1
      pool.lastSeen = time()
    end
  end
  for slot = 1, (GetNumLootItems and GetNumLootItems() or 0) do
    local id = itemIdFromLink(GetLootSlotLink and GetLootSlotLink(slot))
    local _, _, quantity = GetLootSlotInfo(slot)
    if id then
      a.items[id] = (a.items[id] or 0) + (quantity or 1)
      if pool then pool.items[id] = (pool.items[id] or 0) + (quantity or 1) end
    end
  end
end

-- Real vendor prices and stock (game files don't know vendor-specific markups, e.g. Black Market agents)
local function npcIdFromGuid(guid)
  if not guid then return nil end
  local kind, _, _, _, _, id = strsplit("-", guid)
  if kind == "Creature" or kind == "Vehicle" then return tonumber(id) end
  return nil
end

local function recordMerchant()
  local npc = npcIdFromGuid(UnitGUID("npc"))
  if not npc or not GetMerchantNumItems then return end
  local d = db()
  d.vendors = d.vendors or {}
  local v = { name = UnitName("npc"), zone = GetRealZoneText and GetRealZoneText() or nil, seen = time(), items = {} }
  for i = 1, GetMerchantNumItems() do
    local price, quantity, numAvailable, extendedCost
    if C_MerchantFrame and C_MerchantFrame.GetItemInfo then      -- newer client API
      local info = C_MerchantFrame.GetItemInfo(i)
      if info then
        price, quantity, numAvailable, extendedCost = info.price, info.stackCount, info.numAvailable, info.hasExtendedCost
      end
    else                                                         -- classic API
      local _
      _, _, price, quantity, numAvailable, _, _, extendedCost = GetMerchantItemInfo(i)
    end
    local id = itemIdFromLink(GetMerchantItemLink(i))
    if id and price then
      v.items[id] = { price = price, qty = quantity or 1, stock = numAvailable or -1,
                      ext = extendedCost and true or nil }
    end
  end
  d.vendors[npc] = v
end

-- Item checks: the app lists item ids in Checks.lua (ForeverMoneyBridge_Checks). What your own game client says
-- about each (sell price, quality, levels, stack size, binding) is the ground truth the app's item data is
-- verified against. Uncached items are fetched from the server; GET_ITEM_INFO_RECEIVED fires when they arrive.
local pendingInfo = {}
local function storeItemInfo(id)
  local getInfo = (C_Item and C_Item.GetItemInfo) or GetItemInfo
  if not getInfo then return true end
  local name, _, quality, ilvl, minLevel, _, _, stack, _, _, sell, classID, subclassID, bind = getInfo(id)
  if not name then return false end
  local d = db()
  d.itemInfo = d.itemInfo or {}
  d.itemInfo[id] = { n = name, q = quality, l = ilvl, r = minLevel, k = stack, s = sell, c = classID,
                     sc = subclassID, b = bind, t = time() }
  return true
end

local function checkItems()
  local ids = ForeverMoneyBridge_Checks
  if type(ids) ~= "table" or #ids == 0 or not C_Timer then return end
  local i = 0
  local ticker
  ticker = C_Timer.NewTicker(0.1, function()
    for _ = 1, 4 do                       -- ~40 items a second: gentle on the server
      i = i + 1
      local id = ids[i]
      if not id then ticker:Cancel() return end
      if not storeItemInfo(id) then pendingInfo[id] = true end
    end
  end)
end

f:RegisterEvent("GET_ITEM_INFO_RECEIVED")
f:RegisterEvent("MERCHANT_SHOW")
f:RegisterEvent("MERCHANT_UPDATE")
f:RegisterEvent("PLAYER_LOGIN")
f:RegisterEvent("PLAYER_LOGOUT")
f:RegisterEvent("PLAYER_MONEY")
f:RegisterEvent("PLAYER_LEVEL_UP")
f:RegisterEvent("SKILL_LINES_CHANGED")
f:RegisterEvent("ZONE_CHANGED_NEW_AREA")
f:RegisterEvent("LOOT_OPENED")
f:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
f:SetScript("OnEvent", function(_, event, arg1, arg2, arg3)
  if event == "LOOT_OPENED" then
    pcall(recordLoot)
  elseif event == "GET_ITEM_INFO_RECEIVED" then
    if arg1 and pendingInfo[arg1] then
      local ok, done = pcall(storeItemInfo, arg1)
      if ok and done then pendingInfo[arg1] = nil end
    end
  elseif event == "PLAYER_LOGIN" then
    pcall(snapshot)
    if C_Timer then C_Timer.After(15, function() pcall(checkItems) end) end   -- after the login rush
  elseif event == "MERCHANT_SHOW" or event == "MERCHANT_UPDATE" then
    pcall(recordMerchant)
  elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
    if arg1 == "player" then
      local name = arg3 and ((C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(arg3))
        or (GetSpellInfo and GetSpellInfo(arg3)))
      local activity = name and ACTIVITY_SPELLS[name]
      if activity then lastCast.activity, lastCast.t = activity, GetTime() end
    end
  else
    pcall(snapshot)
  end
end)

SLASH_FOREVERMONEYBRIDGE1 = "/fmb"
SlashCmdList.FOREVERMONEYBRIDGE = function()
  snapshot()
  print("|cffe8c060ForeverMoneyBridge|r: snapshot taken. Type /reload to write it to disk for the app.")
end
