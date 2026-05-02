function log_trace(message)
    log_message("TRACE", tostring(message or ""))
end

function log_debug(message)
    log_message("DEBUG", tostring(message or ""))
end

function log_info(message)
    log_message("INFO", tostring(message or ""))
end

function log_warn(message)
    log_message("WARNING", tostring(message or ""))
end

function log_error(message)
    log_message("ERROR", tostring(message or ""))
end
