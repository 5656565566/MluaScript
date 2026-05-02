local original_io_write = io.write
local original_io_output = io.output
local original_default_output = original_io_output()

os.exit = exit

function io.output(file)
    if file then
        return original_io_output(file)
    else
        return original_io_output()
    end
end

function io.write(...)
    local current_output = io.output()

    if current_output == original_default_output then
        local data = table.concat({...})
        python_buffer_file:write(data)
        return true
    else
        return original_io_write(...)
    end
end
