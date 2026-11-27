-- ForeverMoneyBridge: feeds the WoW Forever Money desktop app.
-- Records a snapshot of the current character (level, gold, faction, professions) and a log of
-- every loot window by zone and activity (fishing, skinning, herbalism, mining, mob loot), with the
-- active time spent, so the app can compute real gold per hour, plus what containers you open contain.
-- WoW only writes SavedVariables to disk on logout or /reload; the app picks them up then.

local ADDON, ns = ...      -- ns: the table WoW gives every file of this addon (Meter.lua uses ns.bagItem)
ns = ns or {}

-- Which bag item a loot window came from (a clam, lockbox, junkbox, trunk, sack...), shared through `ns` by the
-- loot log below and the farm meter (Meter.lua). Kept in this file, not a new one: WoW may only find a new addon
-- file after a full restart, where this one updates with a /reload.
-- Until the WoW Forever client patch of 25 Nov 2026 both learned it from a hook on UseContainerItem (right-clicking a
-- bag item). Since that patch not one opened container was logged (21 kinds before it), so the hook seems to have
-- stopped firing, and it can't be the only way any more.
-- In order:
--   1. the loot window's own source: an "Item-..." GUID (looked for on every slot, since slot 1 is often the coins),
--      turned into the item: C_Item.GetItemIDByGUID, else the bag slot holding the item with that GUID;
--   2. the bag item last used through UseContainerItem, within 3 seconds (the old way, in case it still fires);
--   3. the item in your bags the game has locked right now: a container stays locked while its loot window is open
--      (an openable one first, when more than one is locked; only an openable one when the window gave no source,
--      so a mob's loot is never filed under an item you happen to be moving).
-- Each step runs in pcall: an API this client lacks, or one that errors, just skips that step.

local USE_WINDOW = 3      -- seconds between right-clicking a bag item and its loot window
local lastUsed = { id = nil, t = 0 }

local function itemAt(bag, slot)
  if C_Container and C_Container.GetContainerItemID then return C_Container.GetContainerItemID(bag, slot) end
  if GetContainerItemID then return GetContainerItemID(bag, slot) end
end

local function rememberUse(bag, slot)
  local id = itemAt(bag, slot)
  if id then lastUsed.id, lastUsed.t = id, GetTime() end
end
if C_Container and C_Container.UseContainerItem then hooksecurefunc(C_Container, "UseContainerItem", rememberUse) end
if UseContainerItem then hooksecurefunc("UseContainerItem", rememberUse) end

local function lastBag()
  return NUM_TOTAL_EQUIPPED_BAG_SLOTS or NUM_BAG_SLOTS or 4
end

local function slots(bag)
  if C_Container and C_Container.GetContainerNumSlots then return C_Container.GetContainerNumSlots(bag) or 0 end
  return GetContainerNumSlots and GetContainerNumSlots(bag) or 0
end

-- locked, and whether the game says it can be opened (hasLoot), for one bag slot
local function slotState(bag, slot)
  if C_Container and C_Container.GetContainerItemInfo then
    local info = C_Container.GetContainerItemInfo(bag, slot)
    if info then return info.isLocked, info.hasLoot end
    return nil
  end
  if GetContainerItemInfo then
    local _, _, locked, _, _, lootable = GetContainerItemInfo(bag, slot)
    return locked, lootable
  end
end

-- The loot window's source GUID: the first slot that has one (a coins slot can come without one)
function ns.lootSource()
  if not GetLootSourceInfo then return "" end
  local n = (GetNumLootItems and GetNumLootItems()) or 1
  for slot = 1, math.max(n, 1) do
    local ok, guid = pcall(GetLootSourceInfo, slot)
    if ok and type(guid) == "string" and guid ~= "" then return guid end
  end
  return ""
end

local function byGuid(guid)
  if C_Item and C_Item.GetItemIDByGUID then
    local ok, id = pcall(C_Item.GetItemIDByGUID, guid)
    if ok and id then return id end
  end
  if not (C_Item and C_Item.GetItemGUID and ItemLocation and ItemLocation.CreateFromBagAndSlot) then return nil end
  for bag = 0, lastBag() do
    for slot = 1, slots(bag) do
      local id = itemAt(bag, slot)                    -- an empty slot has no GUID to ask for
      if id then
        local ok, g = pcall(C_Item.GetItemGUID, ItemLocation:CreateFromBagAndSlot(bag, slot))
        if ok and g == guid then return id end
      end
    end
  end
end

local function lockedItem(openableOnly)
  local first, openable
  for bag = 0, lastBag() do
    for slot = 1, slots(bag) do
      local ok, locked, hasLoot = pcall(slotState, bag, slot)
      if ok and locked then
        local id = itemAt(bag, slot)
        if id then
          first = first or id
          if hasLoot and not openable then openable = id end
        end
      end
    end
  end
  if openableOnly then return openable end
  return openable or first
end

-- The bag item this loot window came from, and how it was found ("source", "used", "locked"), or nil.
-- guid: the window's source (ns.lootSource()). Only call it for a window whose source is an item or unknown ("").
function ns.bagItem(guid)
  guid = guid or ""
  if guid:match("^Item%-") then
    local ok, id = pcall(byGuid, guid)
    if ok and id then return id, "source" end
  end
  if lastUsed.id and GetTime() - lastUsed.t <= USE_WINDOW then return lastUsed.id, "used" end
  local ok, id = pcall(lockedItem, guid == "")
  if ok and id then return id, "locked" end
end

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

local function snapshot(event)
  local d = db()
  local c = d.characters[charKey()] or {}
  c.name = UnitName("player")
  c.realm = GetRealmName()
  c.faction = UnitFactionGroup("player")
  c.level = UnitLevel("player")
  c.class = select(2, UnitClass("player"))
  -- while logging out (also on /reload) the game can report 0 gold: keep the last real figure then
  if event ~= "PLAYER_LOGOUT" or c.money == nil then c.money = GetMoney() end
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

-- Containers opened from your bags (trunks, clams, crates, lockboxes, junkboxes): which one a loot window came from
-- (ns.bagItem above: the window's own source, else the bag item last used, else the one the game has locked), so what it
-- gave is logged under that item, not as fishing or mob loot.
local function lootSourceKind()
  -- "Item" = a container from your bags, "GameObject" = bobber/node/chest, "Creature" = a mob; nil = no source given
  local guid = ns.lootSource()
  if guid == "" then return nil, "" end
  return (strsplit("-", guid)), guid
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
  local kind, guid = lootSourceKind()
  local fishing = IsFishingLoot and IsFishingLoot()
  local box = (kind == "Item" or (kind == nil and not fishing)) and ns.bagItem(guid) or nil
  if kind == "Item" or box then
    if box then recordContainer(box) end
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

-- TSM's own vendor prices (1.6.2, the user: "TSM should be the king when it comes to pricing data"): VendorSell (what a
-- vendor pays you; TSM takes it from the game client) and VendorBuy (what a vendor charges; TSM's merchant records),
-- for every item the app prices (Prices.lua) and wants checked (Checks.lua). Saved in ForeverMoneyBridgeDB.tsmVendor;
-- the app prefers them to the game files. A few hundred a tick after login, so the game doesn't stutter.
local function tsmVendor()
  if not (TSM_API and TSM_API.GetCustomPriceValue and C_Timer) then return end
  local ids, seen = {}, {}
  local function add(id) id = tonumber(id); if id and not seen[id] then seen[id] = true; ids[#ids + 1] = id end end
  for id in pairs((ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.items) or {}) do add(id) end
  for _, id in ipairs(ForeverMoneyBridge_Checks or {}) do add(id) end
  if #ids == 0 then return end
  local d = db()
  d.tsmVendor = d.tsmVendor or {}
  local out = d.tsmVendor
  out.sell, out.buy = out.sell or {}, out.buy or {}
  local function value(src, id)
    local ok, v = pcall(TSM_API.GetCustomPriceValue, src, "i:" .. id)
    return (ok and type(v) == "number" and v > 0) and math.floor(v + 0.5) or nil
  end
  local i, ticker = 0, nil
  ticker = C_Timer.NewTicker(0.1, function()
    for _ = 1, 250 do
      i = i + 1
      local id = ids[i]
      if not id then out.at = time(); ticker:Cancel() return end
      local s, b = value("VendorSell", id), value("VendorBuy", id)
      if s then out.sell[id] = s end
      if b then out.buy[id] = b end
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
    pcall(snapshot, event)
    if C_Timer then C_Timer.After(5, function() pcall(snapshot, "DELAYED_LOGIN") end) end   -- gold is loaded by then
    if C_Timer then C_Timer.After(15, function() pcall(checkItems) end) end   -- after the login rush
    if C_Timer then C_Timer.After(30, function() pcall(tsmVendor) end) end    -- TSM's vendor prices, once it has loaded
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
    pcall(snapshot, event)
  end
end)

SLASH_FOREVERMONEYBRIDGE1 = "/gea"     -- Gold Ever After
SLASH_FOREVERMONEYBRIDGE2 = "/fmb"     -- the old name, still works
SlashCmdList.FOREVERMONEYBRIDGE = function()
  snapshot()
  print("|cffe8c060Gold Ever After|r: snapshot taken. Type /reload to write it to disk for the app.")
end
