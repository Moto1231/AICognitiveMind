-- Axiom Halo Body V0.1
-- Device-side shell for Brilliant Labs Halo / halo-emulator.
-- Cognition and durable memory remain in Axiom; this app only exposes body events.

frame.display.clear(0)
frame.display.text("Axiom", 92, 112, 0xFFFFFF)

frame.button.single(function()
    frame.bluetooth.send("AXIOM:LOOK")
end)

frame.button.double(function()
    frame.bluetooth.send("AXIOM:LISTEN")
end)

frame.button.long(function()
    frame.bluetooth.send("AXIOM:STATUS")
end)

while true do
    frame.sleep(1.0)
end
