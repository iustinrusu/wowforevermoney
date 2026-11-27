-- Gold Ever After farm meter (in the ForeverMoneyBridge addon): /gea start shows it and starts a session, /gea stop saves it and hides it.
-- Prices (1.6.1, the user went with Claude's recommendation): the app's own values (Prices.lua, as its My bags shows
-- them: odd listings corrected, crafted worth counted) while they are under 12 hours old, else TSM in game, so the
-- meter also works without the app: the same TSM data the app reads (your realm's lowest listing, else its average,
-- else the region's, minus the 5% AH cut), or the vendor price when that is higher or TSM has none. Items the app did
-- not list always fall back to TSM and the vendor price. "/gea prices app" or "/gea prices tsm" fixes one source;
-- "/gea prices auto" goes back. Counts what loot windows from mobs, fishing and nodes show, gold looted and XP gained.
-- A container you loot (a clam, lockbox, junkbox) counts nothing until you open it; then what is inside counts, under
-- "Opened". 1.6.4: which box you opened comes from ns.bagItem (the hook on right-clicking a bag item stopped working
-- with the 25 Nov 2026 client patch), and a box that leaves your bags leaves the "not opened yet" reminder.
-- Fold (1.6.3, the user: "collapse feature / minimize feature"): the "–" button or /gea min folds the window to one
-- line (total, gold an hour, time) and "+" opens it again; remembered between sessions. /gea hide hides it completely,
-- /gea show brings it back. Folded or hidden, the session keeps counting.

local _, ns = ...                   -- the addon's shared table: ns.bagItem (ForeverMoneyBridge.lua), the box a loot
                                    -- window came from
ns = ns or {}
local CUT = 0.05
local TSM_PRICE = "first(DBMinBuyout, DBMarket, DBRegionMarketAvg)"
-- newer clients (WoW: Forever) moved these into C_Item / C_Spell; the old globals may not exist
local GetItemInfo = GetItemInfo or (C_Item and C_Item.GetItemInfo) or function() return nil end
local GetSpellInfo = GetSpellInfo or (C_Spell and C_Spell.GetSpellName) or function() return nil end
local session                       -- {start, paused, pausedAt, pausedFor, money, xp, items = {id = count}, loots = {}}
local win, lines, lootOpenUntil, lastMoney = nil, {}, 0, nil
local cache = {}                    -- item id -> {copper, source}: TSM's data only changes on login or /reload

local function db()
  ForeverMoneyBridgeDB = ForeverMoneyBridgeDB or {}
  ForeverMoneyBridgeDB.meter = ForeverMoneyBridgeDB.meter or {}
  return ForeverMoneyBridgeDB.meter
end

local APP_FRESH = 12 * 3600          -- the app's prices count while under 12 hours old (auto)
local function priceMode() local m = db().prices; return (m == "app" or m == "tsm") and m or "auto" end
local function hasTSM() return TSM_API and TSM_API.GetCustomPriceValue and true or false end
local function appAge()               -- seconds since the app wrote its prices, nil if it never did
  local made = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.made or 0
  return made > 0 and (time() - made) or nil
end
local function useApp()               -- price with the app's values? Decided at /gea start, kept for the session
  if session and session.app ~= nil then return session.app end
  local m = priceMode()
  if m ~= "auto" then return m == "app" end
  local age = appAge()
  return age ~= nil and age < APP_FRESH
end

local function vendorPrice(id)
  local sell = select(11, GetItemInfo(id))
  return (sell and sell > 0) and sell or 0
end

local function tsmPrice(id)
  if not hasTSM() then return 0 end
  local ok, p = pcall(TSM_API.GetCustomPriceValue, TSM_PRICE, "i:" .. id)
  return (ok and type(p) == "number" and p > 0) and math.floor(p * (1 - CUT)) or 0
end

-- what one item is worth, and where the number came from: "app", "tsm", "vendor" or "none"
local function price(id)
  local hit = cache[id]
  if hit then return hit[1], hit[2] end
  local v, src = 0, "none"
  if useApp() then
    local t = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.items
    local a = t and t[id]
    if a and a > 0 then v, src = a, "app" end
  end
  if src == "none" then
    local ah, sell = tsmPrice(id), vendorPrice(id)
    if ah > 0 and ah >= sell then v, src = ah, "tsm" elseif sell > 0 then v, src = sell, "vendor" end
  end
  if GetItemInfo(id) then cache[id] = { v, src } end   -- item data not loaded yet: ask again next time
  return v, src
end

-- Containers count 0 until opened: the app's list when there is one, else the item's tooltip says "<Right Click to
-- Open>" or "Locked" (the game's own strings, so any language)
local openable, scanTip = {}, nil
local function tooltipLines(id)
  local out = {}
  if C_TooltipInfo and C_TooltipInfo.GetItemByID then
    local data = C_TooltipInfo.GetItemByID(id)
    for _, l in ipairs(data and data.lines or {}) do if l.leftText then out[#out + 1] = l.leftText end end
  end
  if #out == 0 then
    scanTip = scanTip or CreateFrame("GameTooltip", "GoldEverAfterScanTip", nil, "GameTooltipTemplate")
    scanTip:SetOwner(UIParent, "ANCHOR_NONE")
    scanTip:SetHyperlink("item:" .. id)
    for i = 1, scanTip:NumLines() do
      local fs = _G["GoldEverAfterScanTipTextLeft" .. i]
      local t = fs and fs:GetText()
      if t then out[#out + 1] = t end
    end
    scanTip:Hide()
  end
  return out
end

local function isContainer(id)
  local boxes = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.containers
  if boxes and boxes[id] then return true end
  if openable[id] == nil then
    local ok, found = pcall(tooltipLines, id)
    if ok and #found > 0 then                          -- an empty tooltip: not loaded yet, look again next time
      openable[id] = false
      for _, t in ipairs(found) do
        if (ITEM_OPENABLE and t == ITEM_OPENABLE) or (LOCKED and t == LOCKED) then openable[id] = true end
      end
    end
  end
  return openable[id] == true
end

-- XP: what the XP bar gained while the meter runs (kills, quests, exploring); a level up in between counts the rest
-- of the old level plus the new one
local xpLast, xpMaxLast = nil, nil
local function atMaxLevel()
  local cap = (GetMaxLevelForPlayerExpansion and GetMaxLevelForPlayerExpansion())
    or (GetMaxPlayerLevel and GetMaxPlayerLevel()) or MAX_PLAYER_LEVEL or 60
  return (UnitLevel("player") or 0) >= cap
end
local function noteXP()
  local cur, max = UnitXP("player") or 0, UnitXPMax("player") or 0
  if xpLast and session and not session.paused then
    local gained = cur >= xpLast and (cur - xpLast) or ((xpMaxLast or 0) - xpLast + cur)
    if gained > 0 then session.xp = (session.xp or 0) + gained end
  end
  xpLast, xpMaxLast = cur, max
end

local function comma(n)
  n = math.floor(n or 0)
  if BreakUpLargeNumbers then return BreakUpLargeNumbers(n) end
  local s, k = tostring(n), 1
  while k > 0 do s, k = s:gsub("^(-?%d+)(%d%d%d)", "%1,%2") end
  return s
end

local function duration(mins)
  mins = math.floor(mins + 0.5)
  if mins < 60 then return mins .. " min" end
  return string.format("%d h %d min", mins / 60, mins % 60)
end

local function clock(secs)            -- the folded bar's time: "42 s", "23 min", "1 h 5 min"
  if secs < 60 then return math.floor(secs) .. " s" end
  return duration(math.floor(secs / 60))
end

local function elapsed()
  if not session then return 0 end
  local now = session.paused and session.pausedAt or GetTime()
  return math.max(0, now - session.start - session.pausedFor)
end

local function money(c, plain, coarse)  -- plain: no coin colours (for muted text); coarse: no copper once there is gold
  c = math.floor(c or 0)
  local g, si, co = math.floor(c / 10000), math.floor(c / 100) % 100, c % 100
  local parts = {}
  local function part(v, unit, colour) return plain and (v .. unit) or ("|cff" .. colour .. v .. unit .. "|r") end
  if g > 0 then parts[#parts + 1] = part(g, "g", "ffd700") end
  if si > 0 then parts[#parts + 1] = part(si, "s", "c7c7cf") end
  if (co > 0 and not (coarse and g > 0)) or #parts == 0 then parts[#parts + 1] = part(co, "c", "eda55f") end
  return table.concat(parts, " ")
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

local LABEL = { mobs = "Kills", skins = "Skins", pickpocket = "Picked", fishing = "Fish", nodes = "Nodes",
                chests = "Chests", containers = "Opened", disenchant = "Disenchanted" }
local ORDER = { "mobs", "skins", "pickpocket", "fishing", "nodes", "chests", "containers", "disenchant" }
local ROWS = 3            -- top items shown

local function refresh()
  if not (win and session) then return end
  local secs = elapsed()
  local value, sources, rows = totals()
  local total = value + session.money
  if db().collapsed then
    -- folded: one line with the total, gold an hour and the time (the window's tooltip says what they are)
    local parts = { money(total, false, true) }
    if secs >= 60 then parts[#parts + 1] = "|cffaaaaaa" .. money(total / secs * 3600, true, true) .. " an hour|r" end
    parts[#parts + 1] = "|cffaaaaaa" .. clock(secs) .. (session.paused and ", paused" or "") .. "|r"
    win.title:SetText(table.concat(parts, " |cff777777·|r "))
  else
    win.title:SetText("Gold Ever After")
  end
  -- headline: the session's total, big; gold an hour under it, muted (the user's choice)
  win.rate:SetText(money(total) .. " |cffaaaaaatotal|r")
  win.total:SetText(secs >= 60 and ("|cffaaaaaa" .. money(total / secs * 3600, true) .. " an hour|r")
    or "|cff888888Gold an hour after the first minute|r")
  win.kv[1]:SetText(string.format("%d:%02d", secs / 60, secs % 60) .. (session.paused and "  |cffffd100paused|r" or ""))
  win.kv[2]:SetText(money(value))
  win.kv[3]:SetText(money(session.money))
  -- XP gained, an hour, and when the next level comes at this pace
  local xp = session.xp or 0
  if atMaxLevel() then
    win.kv[4]:SetText("|cff888888max level|r")
    win.kv[5]:SetText("|cff888888–|r")
  else
    local perHour = secs >= 60 and xp / secs * 3600 or 0
    win.kv[4]:SetText(comma(xp) .. (perHour > 0 and ("  |cffaaaaaa(" .. comma(perHour) .. " an hour)|r") or ""))
    local left = (UnitXPMax("player") or 0) - (UnitXP("player") or 0)
    win.kv[5]:SetText(perHour > 0 and left > 0 and ("about " .. duration(left / perHour * 60) .. " at this pace")
      or "|cff888888after the first XP|r")
  end
  local l, parts = session.loots, {}
  for _, k in ipairs(ORDER) do if (l[k] or 0) > 0 then parts[#parts + 1] = LABEL[k] .. " " .. l[k] end end
  win.loots:SetText(#parts > 0 and table.concat(parts, "  ·  ") or "|cff999999Nothing looted yet|r")
  for i = 1, ROWS do
    local r = rows[i]
    local ok, err = pcall(function()
      if r then
        local name, _, quality = GetItemInfo(r.id)
        local color = quality and ITEM_QUALITY_COLORS and ITEM_QUALITY_COLORS[quality]
        local hex = (color and color.hex) or "|cffffffff"
        win.items[i]:SetText(string.format("%d. %s%s|r |cffaaaaaax%d|r:  %s", i, hex, name or ("item " .. r.id), r.n, money(r.total)))
      else
        win.items[i]:SetText(i == 1 and "|cff888888Nothing yet|r" or "")
      end
    end)
    if not ok then win.items[i]:SetText("|cffff6060" .. tostring(err) .. "|r") end
  end
  local boxes, inside = 0, 0
  for id, n in pairs(session.unopened) do boxes = boxes + n; inside = inside + price(id) * n end
  win.remind:SetText(boxes > 0 and string.format("|cffffd100%d container%s not opened yet%s: open them to count what is inside|r",
    boxes, boxes == 1 and "" or "s", inside > 0 and (" (about " .. money(inside) .. " as they are)") or "") or "")
  local note
  local age = appAge()
  if useApp() then
    note = age and string.format("Prices: the app's, from %.1f h ago", age / 3600)
      or "No app prices yet (start the app, then /reload): TSM and vendor prices"
    local fb = sources.tsm + sources.vendor + sources.none
    if fb > 0 then note = note .. string.format(" · %d by TSM, %d vendor, %d unpriced", sources.tsm, sources.vendor, sources.none) end
  else
    note = hasTSM() and ("Prices: TSM in game, after the AH cut (vendor price if higher)"
      .. (priceMode() == "auto" and (age and string.format(": the app's are %.0f h old", age / 3600) or ": no app prices") or ""))
      or "TSM is not loaded: vendor prices only"
    if sources.vendor + sources.none > 0 then
      note = note .. string.format(" · %d at vendor price, %d unpriced", sources.vendor, sources.none)
    end
  end
  win.note:SetText(note)
end

local function text(parent, font, justify)
  local fs = parent:CreateFontString(nil, "OVERLAY", font)
  fs:SetJustifyH(justify or "LEFT")
  fs:SetWordWrap(true)
  return fs
end

local MIN_W, MIN_H, MAX_W, MAX_H = 260, 290, 600, 600   -- resize bounds of the open window
local FOLDED_H = 34                                      -- the folded window: just the title bar

local function setBounds(minH, maxH)
  if win.SetResizeBounds then win:SetResizeBounds(MIN_W, minH, MAX_W, maxH)
  elseif win.SetMinResize then
    win:SetMinResize(MIN_W, minH)
    if win.SetMaxResize then win:SetMaxResize(MAX_W, maxH) end
  end
end

-- Anchor the window at its top left corner and remember that. WoW anchors a moved window at its nearest corner (the
-- user's was saved as BOTTOMRIGHT), so changing the height would move the title bar: folding would make it jump.
local function pinTopLeft()
  local left, top = win:GetLeft(), win:GetTop()
  if not (left and top) then return end                -- not laid out yet: keep the anchor it has
  win:ClearAllPoints()
  win:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", left, top)
  db().pos = { "TOPLEFT", left, top, "BOTTOMLEFT" }
end

-- folded: only the title bar, with the total, gold an hour and time on it, and "+" to open it again
local function applyFolded()
  if not win then return end
  local folded = db().collapsed and true or false
  pinTopLeft()
  if folded then
    setBounds(FOLDED_H, FOLDED_H)
    win:SetHeight(FOLDED_H)
  else
    setBounds(MIN_H, MAX_H)
    win:SetHeight(math.max(MIN_H, db().h or 340))
  end
  for _, part in ipairs({ win.body, win.pause, win.stop }) do
    if folded then part:Hide() else part:Show() end
  end
  win.fold:SetText(folded and "+" or "–")
  win.layout()
  refresh()
end

local function tip(frame, textOf)     -- a hover explanation; textOf() returns nil for none
  frame:SetScript("OnEnter", function(self)
    local t = GameTooltip and textOf()
    if not t then return end
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    GameTooltip:SetText(t, 1, 1, 1, 1, true)
    GameTooltip:Show()
  end)
  frame:SetScript("OnLeave", function(self)
    if GameTooltip and GameTooltip:GetOwner() == self then GameTooltip:Hide() end
  end)
end

local function makeWindow()
  if win then return win end
  win = CreateFrame("Frame", "ForeverMoneyBridgeMeter", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  local m = db()
  win:SetSize(m.w or 320, m.collapsed and FOLDED_H or (m.h or 340))
  local p = m.pos                                       -- { point, x, y, relative point } (before 1.6.3: no 4th)
  if p then win:SetPoint(p[1], UIParent, p[4] or p[1], p[2], p[3]) else win:SetPoint("CENTER", UIParent, "CENTER", 300, 100) end
  if win.SetBackdrop then
    win:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                      tile = true, tileSize = 16, edgeSize = 12, insets = { left = 3, right = 3, top = 3, bottom = 3 } })
    win:SetBackdropColor(0.04, 0.05, 0.07, 0.92)
    win:SetBackdropBorderColor(0.91, 0.75, 0.38, 0.8)
  end
  win:SetMovable(true)
  win:SetResizable(true)
  setBounds(MIN_H, MAX_H)
  win:SetClampedToScreen(true)
  win:EnableMouse(true)
  win:RegisterForDrag("LeftButton")
  win:SetScript("OnDragStart", win.StartMoving)
  win:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    pinTopLeft()
  end)
  tip(win, function()
    return db().collapsed and ("Gold Ever After, folded to one line: the session's total (items and gold looted), gold an"
      .. " hour, and the time so far. It keeps counting. Click + to open it in full; drag to move it.") or nil
  end)

  -- title bar: the title (or, folded, the one-line summary), Pause, Stop, and the fold button at the far right
  win.title = text(win, "GameFontNormal")
  win.title:SetPoint("TOPLEFT", 12, -10)
  win.title:SetWordWrap(false)                         -- too long for the bar: cut short with "..."
  local function button(label, x, w, onClick)
    local b = CreateFrame("Button", nil, win, "UIPanelButtonTemplate")
    b:SetSize(w, 20)
    b:SetPoint("TOPRIGHT", x, -7)
    b:SetText(label)
    b:SetScript("OnClick", onClick)
    return b
  end
  win.fold = button("–", -8, 22, function() SlashCmdList.FOREVERMONEYBRIDGE("min") end)
  tip(win.fold, function()
    return db().collapsed and "Open the meter in full." or
      "Fold the meter to one line: total, gold an hour and time. It keeps counting (/gea min does the same)."
  end)
  win.stop = button("Stop", -36, 54, function() SlashCmdList.FOREVERMONEYBRIDGE("stop") end)
  win.pause = button("Pause", -94, 54, function() SlashCmdList.FOREVERMONEYBRIDGE(session and session.paused and "resume" or "pause") end)

  -- everything under the title bar sits on one frame, so folding hides it in one go
  local body = CreateFrame("Frame", nil, win)
  body:SetAllPoints(win)
  win.body = body

  -- headline: the total, big; gold an hour under it
  win.rate = text(body, "GameFontNormalHuge")
  win.rate:SetPoint("TOPLEFT", 12, -36)
  win.total = text(body, "GameFontHighlight")
  win.total:SetPoint("TOPLEFT", win.rate, "BOTTOMLEFT", 0, -4)

  -- labelled figures
  win.kv = {}
  local labels = { "Time", "Items", "Gold looted", "XP gained", "Next level" }
  local prev = win.total
  for i, label in ipairs(labels) do
    local k = text(body, "GameFontDisableSmall")
    k:SetPoint("TOPLEFT", prev, "BOTTOMLEFT", 0, i == 1 and -10 or -4)
    k:SetText(label)
    local v = text(body, "GameFontHighlightSmall", "RIGHT")
    v:SetPoint("TOPLEFT", k, "TOPLEFT", 0, 0)            -- full width, right-aligned (layout sets the width)
    win.kv[i] = v
    prev = k
  end
  win.loots = text(body, "GameFontHighlightSmall")
  win.loots:SetPoint("TOPLEFT", prev, "BOTTOMLEFT", 0, -8)

  -- top items
  local head = text(body, "GameFontDisableSmall")
  head:SetPoint("TOPLEFT", win.loots, "BOTTOMLEFT", 0, -8)
  head:SetText("Top items (count, total)")
  win.items = {}
  prev = head
  for i = 1, ROWS do
    local line = text(body, "GameFontHighlightSmall")
    line:SetPoint("TOPLEFT", prev, "BOTTOMLEFT", 0, -3)
    line:SetWordWrap(false)
    win.items[i] = line
    prev = line
  end

  -- bottom: the container reminder and where the prices came from
  win.note = text(body, "GameFontDisableSmall")
  win.note:SetPoint("BOTTOMLEFT", 12, 10)
  win.remind = text(body, "GameFontHighlightSmall")
  win.remind:SetPoint("BOTTOMLEFT", win.note, "TOPLEFT", 0, 4)

  -- resize grip (bottom right, hidden with the rest when folded); the size is remembered
  local grip = CreateFrame("Button", nil, body)
  grip:SetSize(14, 14)
  grip:SetPoint("BOTTOMRIGHT", -4, 4)
  grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
  grip:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
  grip:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
  grip:SetScript("OnMouseDown", function() win:StartSizing("BOTTOMRIGHT") end)
  grip:SetScript("OnMouseUp", function()
    win:StopMovingOrSizing()
    db().w = win:GetWidth()
    if not db().collapsed then db().h = win:GetHeight() end
    pinTopLeft()
  end)
  win.grip = grip

  -- widths follow the window (resizing included); the title stops short of the buttons
  function win.layout()
    local w = win:GetWidth() - 24
    win.title:SetWidth(win:GetWidth() - (db().collapsed and 46 or 164))
    for _, fs in ipairs({ win.rate, win.total, win.loots, win.remind }) do fs:SetWidth(w) end
    win.note:SetWidth(w - 12)
    for _, v in ipairs(win.kv) do v:SetWidth(w) end
    for _, line in ipairs(win.items) do line:SetWidth(w) end
  end
  win:SetScript("OnSizeChanged", win.layout)

  local acc = 0
  win:SetScript("OnUpdate", function(_, dt)
    acc = acc + dt
    if acc >= 1 then acc = 0; refresh() end
  end)
  applyFolded()                                       -- as it was left (folded or not), anchored at the top left
  return win
end

local function start()
  session = { start = GetTime(), paused = false, pausedFor = 0, money = 0, xp = 0, items = {}, unopened = {}, loots = {}, seen = {}, zone = GetRealZoneText and GetRealZoneText() or "?" }
  lastMoney = GetMoney()
  for k in pairs(cache) do cache[k] = nil end         -- prices as of now (a /reload may have brought new TSM data)
  session.app = useApp()                              -- the price source stays the same for the whole session
  xpLast, xpMaxLast = nil, nil
  noteXP()                                            -- the XP bar now: only what comes after counts
  makeWindow():Show()
  win.pause:SetText("Pause")
  refresh()
  print("|cffe8c060Gold Ever After|r started. /gea pause, /gea min (one line), /gea stop.")
end

local function stop()
  if not session then return end
  local boxes = 0
  for _, n in pairs(session.unopened) do boxes = boxes + n end
  if boxes > 0 then
    print(string.format("|cffe8c060Gold Ever After|r: %d container%s not opened yet, so not counted. Open them and they count in your next session (or /gea start again first).", boxes, boxes == 1 and "" or "s"))
  end
  local secs = elapsed()
  local value = totals()
  local total = value + session.money
  local m = db()
  m.sessions = m.sessions or {}
  local xp = session.xp or 0
  table.insert(m.sessions, 1, { ended = time(), zone = session.zone, minutes = math.floor(secs / 6 + 0.5) / 10,
    items = session.items, money = session.money, value = value, total = total,
    perHour = secs > 0 and math.floor(total / secs * 3600) or 0, prices = session.app and "app" or "tsm",
    pricesMade = ForeverMoneyBridge_Prices and ForeverMoneyBridge_Prices.made or 0,
    xp = xp, xpPerHour = secs > 0 and math.floor(xp / secs * 3600) or 0, level = UnitLevel("player") })
  while #m.sessions > 50 do table.remove(m.sessions) end
  print(string.format("|cffe8c060Gold Ever After|r stopped: %s in %d min%s%s. Saved.", money(total), secs / 60,
    secs >= 60 and (" (" .. money(total / secs * 3600) .. " an hour)") or "",
    xp > 0 and (", " .. comma(xp) .. " XP" .. (secs >= 60 and (" (" .. comma(xp / secs * 3600) .. " an hour)") or "")) or ""))
  session = nil
  if win then win:Hide() end
end

-- loot: your own "You receive loot: ..." chat messages (matched with the game's own templates, so any language),
-- gold from "You loot ..." money messages matched with the gold change, and loot windows only to tell what kind of
-- loot it was and to tell containers opened from your bags (which box: ns.bagItem) from mob, chest and fishing loot
-- (with auto loot the window can be gone before it's read).
local debug = false
local function say(...) if debug then print("|cffe8c060Gold Ever After|r", ...) end end

local function pattern(fmt)            -- "You receive loot: %s." -> "^You receive loot: (.+)%.$"
  fmt = fmt:gsub("([%(%)%.%%%+%-%*%?%[%]%^%$])", "%%%1")
  fmt = fmt:gsub("%%%%s", "(.+)"):gsub("%%%%d", "(%%d+)")
  return "^" .. fmt .. "$"
end
local LOOT_ONE = LOOT_ITEM_SELF and pattern(LOOT_ITEM_SELF)
local LOOT_MANY = LOOT_ITEM_SELF_MULTIPLE and pattern(LOOT_ITEM_SELF_MULTIPLE)

local windowKind, windowCounted, skipUntil = nil, false, 0
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

local function noteWindow()
  if windowCounted then return end
  windowCounted = true
  local guid = (ns.lootSource and ns.lootSource()) or (GetLootSourceInfo and GetLootSourceInfo(1)) or ""   -- the first
  -- slot with a source (slot 1 is often the coins)
  local kind = strsplit("-", guid)
  local cast = (GetTime() - lastCast.t <= CAST_WINDOW) and lastCast.kind or nil
  lastCast.kind = nil
  local what, box, how
  if IsFishingLoot and IsFishingLoot() then
    what = "fishing"
  elseif cast == "disenchant" and (kind == "Item" or guid == "") then
    what = "disenchant"
  elseif kind == "Item" or guid == "" then
    -- from your bags: which box (an unknown source counts only when a bag item turns up)
    if ns.bagItem then box, how = ns.bagItem(guid) end
    what = (kind == "Item" or box) and "containers" or "mobs"
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
    if box and (session.unopened[box] or 0) > 0 then
      session.unopened[box] = session.unopened[box] - 1
      if session.unopened[box] == 0 then session.unopened[box] = nil end
    end
  end
  say("loot window:", what, box and ("from item " .. box .. " (found by " .. how .. ")") or (what == "containers" and "(which box: not found)" or ""))
end

-- A box that left your bags (opened, sold, banked, destroyed) is no longer "not opened yet", even when the loot window
-- didn't tell which box it was. Not within 2 s of looting one: the bag may not hold it yet.
local function bagCount(id)
  local count = (C_Item and C_Item.GetItemCount) or GetItemCount
  return count and count(id) or nil
end
local function reconcileBoxes()
  if GetTime() - (session.boxAt or 0) < 2 then return end
  for id, n in pairs(session.unopened) do
    local have = bagCount(id)
    if have and have < n then session.unopened[id] = have > 0 and have or nil end
  end
end

local function addMoney(delta)
  session.money = session.money + delta
  say("gold looted:", money(delta))
end

local ev = CreateFrame("Frame")
for _, e in ipairs({ "LOOT_READY", "LOOT_OPENED", "LOOT_CLOSED", "CHAT_MSG_LOOT", "CHAT_MSG_MONEY", "PLAYER_MONEY",
                    "PLAYER_XP_UPDATE", "PLAYER_LEVEL_UP", "BAG_UPDATE_DELAYED" }) do
  pcall(ev.RegisterEvent, ev, e)
end
ev:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
ev:SetScript("OnEvent", function(_, event, msg, _, spellId)
  if event == "PLAYER_XP_UPDATE" or event == "PLAYER_LEVEL_UP" then
    if session then pcall(noteXP) end                  -- paused: the bar moves on, nothing is counted
    return
  end
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
  elseif event == "BAG_UPDATE_DELAYED" then
    pcall(reconcileBoxes)
  elseif event == "CHAT_MSG_LOOT" then
    if GetTime() <= skipUntil then return end
    local link, n = nil, 1
    if LOOT_MANY then link, n = msg:match(LOOT_MANY) end
    if not link and LOOT_ONE then link = msg:match(LOOT_ONE) end
    local id = link and tonumber(link:match("item:(%d+)"))
    if not id then return end                          -- someone else's loot, or a quest or crafted item
    n = tonumber(n) or 1
    if isContainer(id) then                            -- a container: worth 0 until you open it
      session.unopened[id] = (session.unopened[id] or 0) + n
      session.boxAt = GetTime()
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

-- /gea start | stop | pause | resume | min | hide | show | prices | debug; anything else goes to the addon's own /gea
-- (snapshot)
local NOT_RUNNING = "|cffe8c060Gold Ever After|r is not running. /gea start"
local original = SlashCmdList.FOREVERMONEYBRIDGE
SlashCmdList.FOREVERMONEYBRIDGE = function(msg)
  local cmd = strlower(strtrim(msg or ""))
  if cmd == "start" then
    start()
  elseif cmd == "stop" then
    if session then stop() else print(NOT_RUNNING) end
  elseif cmd == "min" then                             -- fold to one line and back; remembered
    db().collapsed = not db().collapsed
    applyFolded()
    if not (win and win:IsShown()) then
      print("|cffe8c060Gold Ever After|r opens " .. (db().collapsed and "folded to one line" or "in full") .. " from now on.")
    end
  elseif cmd == "hide" then                            -- out of sight; the session keeps counting
    if session and win then
      win:Hide()
      print("|cffe8c060Gold Ever After|r hidden. It keeps counting: /gea show brings it back, /gea stop ends the session.")
    else
      print(NOT_RUNNING)
    end
  elseif cmd == "show" then
    if session then makeWindow():Show(); refresh() else print(NOT_RUNNING) end
  elseif cmd == "pause" and session and not session.paused then
    session.paused, session.pausedAt = true, GetTime()
    win.pause:SetText("Resume")
    refresh()
  elseif cmd == "debug" then
    debug = not debug
    print("|cffe8c060Gold Ever After|r debug " .. (debug and "on: what the meter counts is printed here" or "off"))
  elseif cmd == "prices tsm" or cmd == "prices app" or cmd == "prices auto" then
    db().prices = cmd:sub(8)
    for k in pairs(cache) do cache[k] = nil end
    if session then session.app = nil; session.app = useApp() end
    local m = priceMode()
    print("|cffe8c060Gold Ever After|r prices: " .. (m == "app" and "the app's values (TSM and vendor prices for the rest)"
      or m == "tsm" and "TSM in game (vendor price when higher)"
      or "the app's while they are under 12 hours old, else TSM in game"))
    refresh()
  elseif cmd == "prices" then
    local m, age = priceMode(), appAge()
    print("|cffe8c060Gold Ever After|r prices now: " .. (m == "auto" and "auto, so " or "")
      .. (useApp() and "the app's" or "TSM in game")
      .. (age and string.format(" (the app's are %.1f h old)", age / 3600) or " (no app prices yet)") .. ".")
    print("  /gea prices auto (the default): the app's values while they are under 12 hours old, else TSM in game.")
    print("  /gea prices app: always the WoW Forever Money app's values, as its My bags shows them (it corrects odd"
      .. " listings and counts what crafting adds); TSM and vendor prices for items it did not list.")
    print("  /gea prices tsm: always TSM in game, so the app is not needed. Each item at your realm's lowest listing in"
      .. " TSM's data (else its average there, else the region's), minus the 5% AH cut, or the vendor price when that"
      .. " is higher. TSM's data is as new as your last login or /reload.")
  elseif cmd == "resume" and session and session.paused then
    session.pausedFor = session.pausedFor + (GetTime() - session.pausedAt)
    session.paused = false
    lastMoney = GetMoney()
    win.pause:SetText("Pause")
    refresh()
  else
    if original then original(msg) end
    print("|cffe8c060Gold Ever After|r: /gea start, /gea pause, /gea resume, /gea stop, /gea min (fold the window to"
      .. " one line and back), /gea hide, /gea show (it keeps counting while hidden), /gea prices, /gea debug.")
  end
end
