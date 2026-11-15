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
  lines[4]:SetText(string.format("Kills looted %d  ·  Fish %d  ·  Nodes %d", l.mobs or 0, l.fishing or 0, l.nodes or 0))
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
  lines[9]:SetText(age .. ((sources.tsm + sources.vendor + sources.none > 0) and string.format("; fallbacks: %d TSM, %d vendor, %d no price", sources.tsm, sources.vendor, sources.none) or ""))
end

local function makeWindow()
  if win then return win end
  win = CreateFrame("Frame", "ForeverMoneyBridgeMeter", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  win:SetSize(330, 190)
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
  for i = 1, 9 do
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
  session = { start = GetTime(), paused = false, pausedFor = 0, money = 0, items = {}, loots = {}, zone = GetRealZoneText and GetRealZoneText() or "?" }
  lastMoney = GetMoney()
  makeWindow():Show()
  win.pause:SetText("Pause")
  refresh()
  print("|cffe8c060Farm meter|r started. /fmb pause, /fmb stop.")
end

local function stop()
  if not session then return end
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

-- loot: count what the window shows (not from things opened from bags), and gold looted while it is open
local ev = CreateFrame("Frame")
ev:RegisterEvent("LOOT_OPENED")
ev:RegisterEvent("LOOT_CLOSED")
ev:RegisterEvent("PLAYER_MONEY")
ev:SetScript("OnEvent", function(_, event)
  if not session or session.paused then
    lastMoney = GetMoney()
    return
  end
  if event == "LOOT_OPENED" then
    local guid = GetLootSourceInfo and GetLootSourceInfo(1) or ""
    local kind = strsplit("-", guid or "")
    if kind == "Item" then return end                       -- opening a clam or a trunk from your bags
    local what = (IsFishingLoot and IsFishingLoot()) and "fishing" or (kind == "GameObject" and "nodes" or "mobs")
    session.loots[what] = (session.loots[what] or 0) + 1
    for slot = 1, (GetNumLootItems and GetNumLootItems() or 0) do
      local link = GetLootSlotLink and GetLootSlotLink(slot)
      local id = link and tonumber(link:match("item:(%d+)"))
      local _, _, quantity = GetLootSlotInfo(slot)
      if id then session.items[id] = (session.items[id] or 0) + (quantity or 1) end
    end
    lootOpenUntil = math.huge
  elseif event == "LOOT_CLOSED" then
    lootOpenUntil = GetTime() + 1
  elseif event == "PLAYER_MONEY" then
    local now = GetMoney()
    if lastMoney and now > lastMoney and GetTime() <= lootOpenUntil then
      session.money = session.money + (now - lastMoney)    -- gold from a loot window (not sales, mail or quests)
    end
    lastMoney = now
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
  elseif cmd == "resume" and session and session.paused then
    session.pausedFor = session.pausedFor + (GetTime() - session.pausedAt)
    session.paused = false
    lastMoney = GetMoney()
    win.pause:SetText("Pause")
    refresh()
  else
    if original then original(msg) end
    print("|cffe8c060Farm meter|r: /fmb start, /fmb pause, /fmb resume, /fmb stop.")
  end
end
