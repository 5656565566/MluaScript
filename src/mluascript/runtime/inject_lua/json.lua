function json_encode(value)
    local value_type = type(value)
    if value == nil then
        return "null"
    elseif value_type == "boolean" then
        return value and "true" or "false"
    elseif value_type == "number" then
        return tostring(value)
    elseif value_type == "string" then
        return '"' .. __json_escape_string(value) .. '"'
    elseif value_type == "table" then
        local is_array = true
        local max_index = 0
        for k, _ in pairs(value) do
            if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
                is_array = false
                break
            end
            if k > max_index then max_index = k end
        end

        if is_array then
            local items = {}
            for i = 1, max_index do
                table.insert(items, json_encode(value[i]))
            end
            return "[" .. table.concat(items, ",") .. "]"
        end

        local items = {}
        for k, v in pairs(value) do
            table.insert(items, json_encode(tostring(k)) .. ":" .. json_encode(v))
        end
        return "{" .. table.concat(items, ",") .. "}"
    end
    return json_encode(tostring(value))
end

function json_decode(raw)
    if type(raw) ~= "string" or raw == "" then
        return nil
    end
    local ok, result = pcall(function()
        return maa.json_decode(raw)
    end)
    return ok and result or nil
end

function safe_dump(func)
    local s = string.dump(func)
    return (s:gsub('.', function (c)
        return string.format('%02x', string.byte(c))
    end))
end

function safe_load(hex_str)
    local s = string.gsub(hex_str, '%x%x', function(h) 
        return string.char(tonumber(h, 16)) 
    end)
    return load(s)
end