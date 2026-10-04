-- Axiom Halo Body V0.1
-- Device-side shell for Brilliant Labs Halo / halo-emulator.
-- Cognition and durable memory remain in Axiom; this app only exposes body events.

local function show_message(message)
    frame.display.clear(0)

    local line_num = 0
    local line_height = 32
    local max_lines = 6
    local max_chars = 30

    for source_line in (message .. "\n"):gmatch("(.-)\n") do
        if source_line == "" then
            source_line = " "
        end

        while #source_line > 0 and line_num < max_lines do
            frame.display.text(string.sub(source_line, 1, max_chars), 8, 24 + line_num * line_height, 0xFFFFFF)
            source_line = string.sub(source_line, max_chars + 1)
            line_num = line_num + 1
        end

        if line_num >= max_lines then
            break
        end
    end
end

show_message("Axiom\nReady")

-- Host replies are plain UTF-8 text sent over the same BLE connection.
frame.bluetooth.receive_callback(function(data)
    show_message(data)
end)

frame.button.single(function()
    frame.bluetooth.send("AXIOM:LOOK")
    show_message("Axiom\nLooking...")
end)

frame.button.double(function()
    frame.bluetooth.send("AXIOM:LISTEN")
    show_message("Axiom\nListening...")
end)

frame.button.long(function()
    frame.bluetooth.send("AXIOM:STATUS")
    show_message("Axiom\nChecking status...")
end)

while true do
    frame.sleep(1.0)
end
