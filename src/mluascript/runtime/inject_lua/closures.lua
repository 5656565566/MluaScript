-- 表和函数可能循环引用，多个闭包也可能共享同一个 upvalue cell。
-- 快照只传递值和引用编号，不让主运行时对象进入子运行时。
function capture_lua_functions(roots)
    local nodes, references, cells = {}, {}, {}
    local next_cell = 0
    local encode
    encode = function(value, location)
        local kind = type(value)
        if kind == "string" then
            local hex = value:gsub('.', function(c) return string.format('%02x', string.byte(c)) end)
            return {kind = "string", hex = hex}
        end
        if kind == "nil" or kind == "boolean" or kind == "number" then
            return {kind = "value", value = value}
        end
        if kind ~= "table" and kind ~= "function" then
            error("Cannot copy " .. location .. ": unsupported " .. kind, 0)
        end
        if references[value] then return {kind = "reference", id = references[value]} end

        local id = #nodes + 1
        local node = {kind = kind}
        nodes[id], references[value] = node, id
        if kind == "table" then
            if getmetatable(value) ~= nil then
                error("Cannot copy " .. location .. ": table with metatable", 0)
            end
            node.entries = {}
            for key, item in pairs(value) do
                table.insert(node.entries, {key = encode(key, location), value = encode(item, location)})
            end
        else
            local ok, bytecode = pcall(safe_dump, value)
            if not ok then error("Cannot copy " .. location .. ": non-Lua function", 0) end
            node.bytecode, node.upvalues = bytecode, {}
            local index = 1
            while true do
                local name, item = debug.getupvalue(value, index)
                if name == nil then break end
                if name == "_ENV" then
                    node.upvalues[index] = {environment = true}
                else
                    local cell = debug.upvalueid(value, index)
                    if not cells[cell] then
                        next_cell = next_cell + 1
                        cells[cell] = next_cell
                    end
                    node.upvalues[index] = {
                        cell = cells[cell],
                        value = encode(item, location .. " upvalue '" .. name .. "'"),
                    }
                end
                index = index + 1
            end
        end
        return {kind = "reference", id = id}
    end

    local encoded_roots = {}
    for name, value in pairs(roots) do
        encoded_roots[name] = encode(value, "function '" .. name .. "'")
    end
    return {nodes = nodes, roots = encoded_roots}
end

function restore_lua_functions(snapshot)
    local objects, cells = {}, {}
    -- 先创建全部对象，再恢复引用，保证循环表和递归函数可正确重建。
    for id, node in ipairs(snapshot.nodes) do
        if node.kind == "table" then
            objects[id] = {}
        else
            objects[id] = assert(safe_load(node.bytecode))
        end
    end
    local function decode(value)
        if value.kind == "reference" then return objects[value.id] end
        if value.kind == "string" then
            return (value.hex:gsub('%x%x', function(h) return string.char(tonumber(h, 16)) end))
        end
        return value.value
    end
    for id, node in ipairs(snapshot.nodes) do
        local object = objects[id]
        if node.kind == "table" then
            for _, entry in ipairs(node.entries) do
                object[decode(entry.key)] = decode(entry.value)
            end
        else
            for index, upvalue in ipairs(node.upvalues) do
                if upvalue.environment then
                    debug.setupvalue(object, index, _ENV)
                elseif cells[upvalue.cell] then
                    local other = cells[upvalue.cell]
                    debug.upvaluejoin(object, index, other.object, other.index)
                else
                    debug.setupvalue(object, index, decode(upvalue.value))
                    cells[upvalue.cell] = {object = object, index = index}
                end
            end
        end
    end
    local roots = {}
    for name, value in pairs(snapshot.roots) do roots[name] = decode(value) end
    return roots
end
