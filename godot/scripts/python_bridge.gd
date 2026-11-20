extends Node
## Transport only: Python owns all game rules and simulation state.
signal state_received(state: Dictionary)
signal bridge_error(message: String)

const PYTHON_HOST := "127.0.0.1"
const PYTHON_PORT := 4244
const GODOT_PORT := 4243
const PROTOCOL_VERSION := 1
const SEND_INTERVAL := 1.0 / 30.0

var socket := PacketPeerUDP.new()
var ready_to_send := false
var send_accumulator := 0.0
var mouse_delta := Vector2.ZERO
var mouse_wheel := 0
var queued_commands: Array[String] = []
var latest_state: Dictionary = {}
var packet_sequence := 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var error := socket.bind(GODOT_PORT, "127.0.0.1")
	if error != OK:
		bridge_error.emit("Cannot bind Godot UDP port %d (error %d)." % [GODOT_PORT, error])
		return
	socket.set_dest_address(PYTHON_HOST, PYTHON_PORT)
	ready_to_send = true
	print("[ANINO] Bridge listening on 127.0.0.1:%d; waiting for Python on %d." % [GODOT_PORT, PYTHON_PORT])

func send_command(command: String) -> void:
	if not queued_commands.has(command):
		queued_commands.append(command)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		mouse_delta += event.relative
	elif event is InputEventMouseButton:
		if event.pressed and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE and event.button_index == MOUSE_BUTTON_LEFT:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			mouse_wheel += 1
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			mouse_wheel -= 1
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		elif latest_state.get("game_state", "menu") == "playing":
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _process(delta: float) -> void:
	if not ready_to_send:
		return
	while socket.get_available_packet_count() > 0:
		var packet := socket.get_packet()
		var parsed: Variant = JSON.parse_string(packet.get_string_from_utf8())
		if parsed is Dictionary and parsed.get("protocol", 0) == PROTOCOL_VERSION and parsed.get("type", "") == "state":
			latest_state = parsed
			state_received.emit(latest_state)

	send_accumulator += delta
	if send_accumulator < SEND_INTERVAL:
		return
	send_accumulator = 0.0
	_send_input()

func _send_input() -> void:
	var keys: Array[String] = []
	var bindings := {
		"w": KEY_W, "a": KEY_A, "s": KEY_S, "d": KEY_D,
		"shift": KEY_SHIFT, "ctrl": KEY_CTRL, "f": KEY_F,
		"e": KEY_E, "g": KEY_G, "h": KEY_H, "v": KEY_V, "c": KEY_C,
		"1": KEY_1, "2": KEY_2, "3": KEY_3, "4": KEY_4, "5": KEY_5,
		"q": KEY_Q, "tab": KEY_TAB, "r": KEY_R, "escape": KEY_ESCAPE,
		"m": KEY_M, "f11": KEY_F11, "f3": KEY_F3, "enter": KEY_ENTER, "i": KEY_I
	}
	for key_name in bindings:
		if Input.is_key_pressed(bindings[key_name]):
			keys.append(key_name)
	var packet := {
		"protocol": PROTOCOL_VERSION,
		"type": "input",
		"sequence": packet_sequence,
		"keys": keys,
		"mouse_delta": [mouse_delta.x, mouse_delta.y],
		"mouse_wheel": mouse_wheel,
		"mouse_buttons": [Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)],
		"commands": queued_commands
	}
	packet_sequence += 1
	mouse_delta = Vector2.ZERO
	mouse_wheel = 0
	queued_commands.clear()
	socket.put_packet(JSON.stringify(packet).to_utf8_buffer())

func _exit_tree() -> void:
	socket.close()
