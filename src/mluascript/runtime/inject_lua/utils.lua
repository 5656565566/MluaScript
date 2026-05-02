function format_time(seconds)
    local s = math.floor(seconds)
    local h = math.floor(s / 3600)
    s = s % 3600
    local m = math.floor(s / 60)
    s = s % 60

    if h > 0 then
        return string.format("%dh %dm %ds", h, m, s)
    elseif m > 0 then
        return string.format("%dm %ds", m, s)
    else
        return string.format("%ds", s)
    end
end

function random_range(min, max)
    if min > max then
        min, max = max, min
    end
    if min == max then
        return min
    end
    return min + (max - min) * math.random()
end

function __json_escape_string(value)
    value = tostring(value or "")
    value = value:gsub('\\', '\\\\')
    value = value:gsub('"', '\\"')
    value = value:gsub('\n', '\\n')
    value = value:gsub('\r', '\\r')
    value = value:gsub('\t', '\\t')
    return value
end

function __split_targets(target)
    local list = {}
    local text = tostring(target or "")
    if text == "" then
        return list
    end
    for item in string.gmatch(text, "[^|]+") do
        local trimmed = item:gsub("^%s+", ""):gsub("%s+$", "")
        if trimmed ~= "" then
            table.insert(list, trimmed)
        end
    end
    return list
end
