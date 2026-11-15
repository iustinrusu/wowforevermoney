-- ForeverMoneyBridge farm meter: /fmb start shows it and starts a session, /fmb stop saves it and hides it.
-- Prices: the WoW Forever Money app's own values (Prices.lua, the same as the app's My bags), so the meter and the
-- app agree. An item missing from that table falls back to TSM's price (lowest listing, else market, after the 5% AH
-- cut), then to the vendor price; the window says how many fallbacks were used. Counts what loot windows from mobs,
-- fishing and nodes show, plus gold looted; things opened from your bags are skipped (they'd count twice).

local CUT = 0.05
local session                       -- {start, paused, pausedAt, pausedFor, money, items = {id = count}, loots = {}}
local win, lines, lootOpenUntil, lastMoney = nil, {}, 0, nil

local function db()
  ForeverMoneyBridgeDB = ForeverMoneyBridgeDB or {}
  ForeverMoneyBridgeDB.meter = ForeverMoneyBridgeDB.meter or {}
  return ForeverMoneyBridgeDB.meter
end

-- what one item is worth, and where the number came from: "app", "tsm", "vendor" or "none"
local function price(id)
  local t = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.items
  local v = t and t[id]
  if v and v > 0 then return v, "app" end
  if TSM_API and TSM_API.GetCustomPriceValue then
    local ok, p = pcall(TSM_API.GetCustomPriceValue, "first(DBMinBuyout, DBMarket)", "i:" .. id)
    if ok and p and p > 0 then return math.floor(p * (1 - CUT)), "tsm" end
  end
  local sell = select(11, GetItemInfo(id))
  if sell and sell > 0 then return sell, "vendor" end
  return 0, "none"
end

local function elapsed()
  if not session then return 0 end
  local now = session.paused and session.pausedAt or GetTime()
  return math.max(0, now - session.start - session.pausedFor)
end

local function money(c)
  c = math.floor(c or 0)
  if GetCoinTextureString then return GetCoinTextureString(c) end
  return string.format("%dg %ds %dc", c / 10000, (c / 100) % 100, c % 100)
end

local function totals()
  local value, sources, rows = 0, { app = 0, tsm = 0, vendor = 0, none = 0 }, {}
  for id, n in pairs(session.items) do
    local p, src = price(id)
    value = value + p * n
    sources[src] = sources[src] + 1
    rows[#rows + 1] = { id = id, n = n, total = p * n }
  end
  table.sort(rows, function(a, b) return a.total > b.total end)
  return value, sources, rows
end

local function refresh()
  if not (win and session) then return end
  local secs = elapsed()
  local value, sources, rows = totals()
  local total = value + session.money
  local perHour = secs >= 60 and total / secs * 3600 or nil
  win.title:SetText(session.paused and "Farm meter (paused)" or "Farm meter")
  lines[1]:SetText(string.format("Time: %d:%02d", secs / 60, secs % 60))
  lines[2]:SetText("Items: " .. money(value) .. "   Gold looted: " .. money(session.money))
  lines[3]:SetText("Total: " .. money(total) .. "   Per hour: " .. (perHour and money(perHour) or "after 1 min"))
  local l = session.loots
  local parts = {}
  for _, k in ipairs(ORDER) do if (l[k] or 0) > 0 then parts[#parts + 1] = LABEL[k] .. " " .. l[k] end end
  lines[4]:SetText(#parts > 0 and table.concat(parts, "  ·  ") or "Nothing looted yet")
  for i = 1, 4 do
    local r = rows[i]
    if r then
      local name = GetItemInfo(r.id) or ("item " .. r.id)
      lines[4 + i]:SetText(string.format("  %dx %s  %s", r.n, name, money(r.total)))
    else
      lines[4 + i]:SetText("")
    end
  end
  local made = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.made or 0
  local age = made > 0 and string.format("app prices from %.1f h ago", (time() - made) / 3600) or "no app prices yet (start the app, then /reload)"
  local boxes, inside = 0, 0
  for id, n in pairs(session.unopened) do boxes = boxes + n; inside = inside + price(id) * n end
  lines[10]:SetText(boxes > 0 and string.format("|cffffd100Not opened yet: %d container%s (about %s inside): open them to count them|r",
    boxes, boxes == 1 and "" or "s", money(inside)) or "")
  lines[9]:SetText(age .. ((sources.tsm + sources.vendor + sources.none > 0) and string.format("; fallbacks: %d TSM, %d vendor, %d no price", sources.tsm, sources.vendor, sources.none) or ""))
end

local function makeWindow()
  if win then return win end
  win = CreateFrame("Frame", "ForeverMoneyBridgeMeter", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  win:SetSize(330, 205)
  local pos = db().pos
  if pos then win:SetPoint(pos[1], UIParent, pos[1], pos[2], pos[3]) else win:SetPoint("CENTER", UIParent, "CENTER", 300, 100) end
  if win.SetBackdrop then
    win:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                      tile = true, tileSize = 16, edgeSize = 12, insets = { left = 3, right = 3, top = 3, bottom = 3 } })
    win:SetBackdropColor(0.05, 0.06, 0.08, 0.9)
  end
  win:SetMovable(true)
  win:EnableMouse(true)
  win:RegisterForDrag("LeftButton")
  win:SetScript("OnDragStart", win.StartMoving)
  win:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    local p, _, _, x, y = self:GetPoint()
    db().pos = { p, x, y }
  end)
  win.title = win:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  win.title:SetPoint("TOPLEFT", 10, -8)
  for i = 1, 10 do
    local fs = win:CreateFontString(nil, "OVERLAY", i == 9 and "GameFontDisableSmall" or "GameFontHighlightSmall")
    fs:SetPoint("TOPLEFT", 10, -12 - i * 15)
    fs:SetWidth(310)
    fs:SetJustifyH("LEFT")
    lines[i] = fs
  end
  local function button(label, x, onClick)
    local b = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    b:SetSize(64, 18)
    b:SetPoint("TOPRIGHT", x, -6)
    b:SetText(label)
    b:SetScript("OnClick", onClick)
    return b
  end
  win.pause = button("Pause", -76, function() SlashCmdList.FOREVERMONEYBRIDGE(session and session.paused and "resume" or "pause") end)
  button("Stop", -8, function() SlashCmdList.FOREVERMONEYBRIDGE("stop") end)
  local acc = 0
  win:SetScript("OnUpdate", function(_, dt)
    acc = acc + dt
    if acc >= 1 then acc = 0; refresh() end
  end)
  return win
end

local function start()
  session = { start = GetTime(), paused = false, pausedFor = 0, money = 0, items = {}, unopened = {}, loots = {}, seen = {}, zone = GetRealZoneText and GetRealZoneText() or "?" }
  lastMoney = GetMoney()
  makeWindow():Show()
  win.pause:SetText("Pause")
  refresh()
  print("|cffe8c060Farm meter|r started. /fmb pause, /fmb stop.")
end

local function stop()
  if not session then return end
  local boxes = 0
  for _, n in pairs(session.unopened) do boxes = boxes + n end
  if boxes > 0 then
    print(string.format("|cffe8c060Farm meter|r: %d container%s not opened yet, so not counted. Open them and they count in your next session (or /fmb start again first).", boxes, boxes == 1 and "" or "s"))
  end
  local secs = elapsed()
  local value = totals()
  local total = value + session.money
  local m = db()
  m.sessions = m.sessions or {}
  table.insert(m.sessions, 1, { ended = time(), zone = session.zone, minutes = math.floor(secs / 6 + 0.5) / 10,
    items = session.items, money = session.money, value = value, total = total,
    perHour = secs > 0 and math.floor(total / secs * 3600) or 0, pricesMade = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.made or 0 })
  while #m.sessions > 50 do table.remove(m.sessions) end
  print(string.format("|cffe8c060Farm meter|r stopped: %s in %d min%s. Saved.", money(total), secs / 60,
    secs >= 60 and (" (" .. money(total / secs * 3600) .. " an hour)") or ""))
  session = nil
  if win then win:Hide() end
end

-- loot: your own "You receive loot: ..." chat messages (matched with the game's own templates, so any language),
-- gold from "You loot ..." money messages matched with the gold change, and loot windows only to tell what kind of
-- loot it was and to skip containers opened from your bags (with auto loot the window can be gone before it's read).
local debug = false
local function say(...) if debug then print("|cffe8c060Farm meter|r", ...) end end

local function pattern(fmt)            -- "You receive loot: %s." -> "^You receive loot: (.+)%.$"
  fmt = fmt:gsub("([%(%)%.%%%+%-%*%?%[%]%^%$])", "%%%1")
  fmt = fmt:gsub("%%%%s", "(.+)"):gsub("%%%%d", "(%%d+)")
  return "^" .. fmt .. "$"
end
local LOOT_ONE = LOOT_ITEM_SELF and pattern(LOOT_ITEM_SELF)
local LOOT_MANY = LOOT_ITEM_SELF_MULTIPLE and pattern(LOOT_ITEM_SELF_MULTIPLE)

local windowKind, windowCounted, skipUntil = nil, false, 0
local lastUsed = { id = nil, t = 0 }                   -- the item you last used from your bags (a container)
local function rememberUse(bag, slot)
  local id = C_Container and C_Container.GetContainerItemID and C_Container.GetContainerItemID(bag, slot)
    or (GetContainerItemID and GetContainerItemID(bag, slot))
  if id then lastUsed.id, lastUsed.t = id, GetTime() end
end
if C_Container and C_Container.UseContainerItem then hooksecurefunc(C_Container, "UseContainerItem", rememberUse) end
if UseContainerItem then hooksecurefunc("UseContainerItem", rememberUse) end
local moneyChatAt, moneyDelta = 0, nil

-- What kind of loot a window is: the loot source (a creature, an object, an item) plus the spell you just cast.
-- Spells by id (every rank), turned into this client's names too, so it works in any language.
local CAST_SPELLS = {
  skins = { 8613, 8617, 8618, 10768 },                               -- Skinning
  nodes = { 2366, 2368, 3570, 11993, 2575, 2576, 3564, 10248 },     -- Herb Gathering, Mining
  pickpocket = { 921 },                                              -- Pick Pocket
  disenchant = { 13262 },                                            -- Disenchant
}
local spellKind, nameKind = {}, { ["Skinning"] = "skins", ["Herb Gathering"] = "nodes", ["Mining"] = "nodes",
                                  ["Pick Pocket"] = "pickpocket", ["Disenchant"] = "disenchant" }
for kind, ids in pairs(CAST_SPELLS) do
  for _, id in ipairs(ids) do
    spellKind[id] = kind
    local name = GetSpellInfo and GetSpellInfo(id)
    if name then nameKind[name] = kind end
  end
end
local lastCast = { kind = nil, t = 0 }
local CAST_WINDOW = 10
local LABEL = { mobs = "Kills", skins = "Skins", pickpocket = "Picked", fishing = "Fish", nodes = "Nodes",
                chests = "Chests", containers = "Opened", disenchant = "Disenchanted" }
local ORDER = { "mobs", "skins", "pickpocket", "fishing", "nodes", "chests", "containers", "disenchant" }

local function noteWindow()
  if windowCounted then return end
  windowCounted = true
  local guid = GetLootSourceInfo and GetLootSourceInfo(1) or ""
  local kind = strsplit("-", guid or "")
  local cast = (GetTime() - lastCast.t <= CAST_WINDOW) and lastCast.kind or nil
  lastCast.kind = nil
  local what
  if IsFishingLoot and IsFishingLoot() then
    what = "fishing"
  elseif kind == "Item" then
    what = (cast == "disenchant") and "disenchant" or "containers"
  elseif kind == "GameObject" then
    what = (cast == "nodes") and "nodes" or "chests"
  else
    what = (cast == "skins" or cast == "pickpocket") and cast or "mobs"
  end
  windowKind = what
  -- the same corpse or chest opened again (loot left behind): not another kill
  if guid ~= "" and what ~= "containers" and what ~= "disenchant" then
    local key = guid .. "|" .. what
    if session.seen[key] then say("looted again (not counted twice):", what) return end
    session.seen[key] = true
  end
  session.loots[what] = (session.loots[what] or 0) + 1
  if what == "containers" then
    -- a container opened from your bags: its contents count; it leaves the "not opened yet" list
    local id = lastUsed.id and GetTime() - lastUsed.t <= 3 and lastUsed.id
    if id and (session.unopened[id] or 0) > 0 then
      session.unopened[id] = session.unopened[id] - 1
      if session.unopened[id] == 0 then session.unopened[id] = nil end
    end
  end
  say("loot window:", what)
end

local function addMoney(delta)
  session.money = session.money + delta
  say("gold looted:", money(delta))
end

local ev = CreateFrame("Frame")
for _, e in ipairs({ "LOOT_READY", "LOOT_OPENED", "LOOT_CLOSED", "CHAT_MSG_LOOT", "CHAT_MSG_MONEY", "PLAYER_MONEY" }) do
  pcall(ev.RegisterEvent, ev, e)
end
ev:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
ev:SetScript("OnEvent", function(_, event, msg, _, spellId)
  if event == "UNIT_SPELLCAST_SUCCEEDED" then
    if msg == "player" then
      local name = spellId and GetSpellInfo and GetSpellInfo(spellId)
      local k = (spellId and spellKind[spellId]) or (name and nameKind[name])
      if k then lastCast.kind, lastCast.t = k, GetTime() end
    end
    return
  end
  if not session or session.paused then
    lastMoney = GetMoney()
    return
  end
  if event == "LOOT_READY" or event == "LOOT_OPENED" then
    pcall(noteWindow)
  elseif event == "LOOT_CLOSED" then
    windowCounted = false
    windowKind = nil
  elseif event == "CHAT_MSG_LOOT" then
    if GetTime() <= skipUntil then return end
    local link, n = nil, 1
    if LOOT_MANY then link, n = msg:match(LOOT_MANY) end
    if not link and LOOT_ONE then link = msg:match(LOOT_ONE) end
    local id = link and tonumber(link:match("item:(%d+)"))
    if not id then return end                          -- someone else's loot, or a quest or crafted item
    n = tonumber(n) or 1
    local boxes = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.containers
    if boxes and boxes[id] then                        -- a container: worth 0 until you open it
      session.unopened[id] = (session.unopened[id] or 0) + n
      say("container looted (counts when opened):", link, "x" .. n)
      return
    end
    session.items[id] = (session.items[id] or 0) + n
    say("item:", link, "x" .. n, money(price(id) * n))
  elseif event == "CHAT_MSG_MONEY" then
    if moneyDelta then addMoney(moneyDelta); moneyDelta = nil else moneyChatAt = GetTime() end
  elseif event == "PLAYER_MONEY" then
    local now = GetMoney()
    local delta = lastMoney and now - lastMoney or 0
    lastMoney = now
    if delta <= 0 then return end
    if GetTime() - moneyChatAt <= 2 then addMoney(delta); moneyChatAt = 0 else moneyDelta = delta
      if C_Timer then C_Timer.After(2, function() moneyDelta = nil end) end end   -- not loot (a sale, mail, a quest) unless a message follows
  end
end)

-- /fmb start | stop | pause | resume; anything else goes to the addon's own /fmb (snapshot)
local original = SlashCmdList.FOREVERMONEYBRIDGE
SlashCmdList.FOREVERMONEYBRIDGE = function(msg)
  local cmd = strlower(strtrim(msg or ""))
  if cmd == "start" then
    start()
  elseif cmd == "stop" then
    if session then stop() else print("|cffe8c060Farm meter|r is not running. /fmb start") end
  elseif cmd == "pause" and session and not session.paused then
    session.paused, session.pausedAt = true, GetTime()
    win.pause:SetText("Resume")
    refresh()
  elseif cmd == "debug" then
    debug = not debug
    print("|cffe8c060Farm meter|r debug " .. (debug and "on: what the meter counts is printed here" or "off"))
  elseif cmd == "resume" and session and session.paused then
    session.pausedFor = session.pausedFor + (GetTime() - session.pausedAt)
    session.paused = false
    lastMoney = GetMoney()
    win.pause:SetText("Pause")
    refresh()
  else
    if original then original(msg) end
    print("|cffe8c060Farm meter|r: /fmb start, /fmb pause, /fmb resume, /fmb stop, /fmb debug.")
  end
end
