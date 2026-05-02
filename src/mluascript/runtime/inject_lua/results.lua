local function __result_items(value)
    if type(value) ~= "table" then
        return nil
    end
    if type(value.items) == "table" then
        return value.items
    end
    if type(value.results) == "table" then
        return value.results
    end
    if type(value.text) == "string" or type(value.box) == "table" or value.score ~= nil then
        return { value }
    end
    return value
end

function result_items(value)
    return __result_items(value) or {}
end

function result_count(value)
    local items = __result_items(value)
    if type(items) ~= "table" then
        return 0
    end
    return #items
end

function result_first(value)
    local items = __result_items(value)
    if type(items) ~= "table" then
        return nil
    end
    return items[1]
end

function result_get(value, index)
    local items = __result_items(value)
    if type(items) ~= "table" then
        return nil
    end
    local i = tonumber(index)
    if not i then
        return nil
    end
    i = math.floor(i)
    if i < 1 or i > #items then
        return nil
    end
    return items[i]
end

function item_text(item)
    if type(item) ~= "table" then
        return ""
    end
    return tostring(item["text"] or "")
end

function item_score(item)
    if type(item) ~= "table" then
        return 0
    end
    local score = tonumber(item["score"])
    return score or 0
end

function item_box(item)
    if type(item) ~= "table" then
        return nil
    end
    local box = item["box"]
    if type(box) ~= "table" then
        return nil
    end
    local x = tonumber(box[1])
    local y = tonumber(box[2])
    local w = tonumber(box[3])
    local h = tonumber(box[4])
    if not x or not y or not w or not h then
        return nil
    end
    return { x, y, w, h }
end

function item_center(item)
    local box = item_box(item)
    if not box then
        return nil
    end
    return {
        box[1] + box[3] / 2,
        box[2] + box[4] / 2,
    }
end

function result_box(value)
    if type(value) ~= "table" then
        return nil
    end
    if type(value.box) == "table" then
        return item_box(value)
    end
    return item_box(result_first(value))
end

function click_result(value, offset_x, offset_y)
    local box = result_box(value)
    if not box then
        return false
    end
    local dx = tonumber(offset_x) or 0
    local dy = tonumber(offset_y) or -5
    return maa.click(box[1] + box[3] / 2 + dx, box[2] + box[4] / 2 + dy)
end

function find_text_in_items(items_list, target)
    local items = __result_items(items_list)
    if type(items) ~= "table" then return nil end
    local targets = __split_targets(target)
    if #targets == 0 then return nil end
    for i = 1, #items do
        local item = items[i]
        local itemText = item_text(item)
        if itemText ~= "" then
            for j = 1, #targets do
                if string.find(itemText, targets[j], 1, true) then
                    return item
                end
            end
        end
    end
    return nil
end

function find_text_in_items_fuzzy(items_list, target)
    local items = __result_items(items_list)
    if type(items) ~= "table" then
        return { hit = false, item = {}, items = {} }
    end
    local targets = __split_targets(target)
    if #targets == 0 then
        return { hit = false, item = {}, items = {} }
    end
    local text_parts = {}
    for i = 1, #items do
        local item = items[i]
        local itemText = item_text(item)
        if itemText ~= "" then
            table.insert(text_parts, itemText)
        end
    end
    local merged = table.concat(text_parts)
    for i = 1, #targets do
        if string.find(merged, targets[i], 1, true) then
            local matched = { text = merged, hit = true }
            return { hit = true, item = matched, items = { matched } }
        end
    end
    return { hit = false, item = {}, items = {} }
end

function result_contains_text(items_list, target)
    return find_text_in_items(items_list, target) ~= nil
end

function result_contains_text_fuzzy(items_list, target)
    local result = find_text_in_items_fuzzy(items_list, target)
    return type(result) == "table" and result.hit == true
end
