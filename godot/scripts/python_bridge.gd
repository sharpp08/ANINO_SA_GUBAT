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
var pending_keydowns: Array[String] = []
var pending_keyups: Array[String] = []
var pending_mouse_downs: Array[String] = []
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
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			mouse_wheel += 1
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			mouse_wheel -= 1
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if not pending_mouse_downs.has("left"):
			pending_mouse_downs.append("left")
	elif event is InputEventKey:
		var key_name := _key_name_for_code(event.keycode)
		if event.pressed and not event.echo:
			if key_name != "" and not pending_keydowns.has(key_name):
				pending_keydowns.append(key_name)
			if event.keycode == KEY_ESCAPE:
				if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
					Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
				elif latest_state.get("game_state", "menu") == "playing":
					Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		elif not event.pressed and key_name != "" and not pending_keyups.has(key_name):
			pending_keyups.append(key_name)

func _key_name_for_code(code: int) -> String:
	match code:
		KEY_W: return "w"
		KEY_A: return "a"
		KEY_S: return "s"
		KEY_D: return "d"
		KEY_SHIFT: return "shift"
		KEY_CTRL: return "ctrl"
		KEY_F: return "f"
		KEY_E: return "e"
		KEY_G: return "g"
		KEY_H: return "h"
		KEY_V: return "v"
		KEY_C: return "c"
		KEY_1: return "1"
		KEY_2: return "2"
		KEY_3: return "3"
		KEY_4: return "4"
		KEY_5: return "5"
		KEY_Q: return "q"
		KEY_TAB: return "tab"
		KEY_R: return "r"
		KEY_ESCAPE: return "escape"
		KEY_M: return "m"
		KEY_F11: return "f11"
		KEY_F3: return "f3"
		KEY_ENTER: return "enter"
		KEY_I: return "i"
	return ""

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
		"pressed": pending_keydowns,
		"released": pending_keyups,
		"mouse_pressed": pending_mouse_downs,
		"mouse_delta": [mouse_delta.x, mouse_delta.y],
		"mouse_wheel": mouse_wheel,
		"mouse_buttons": [Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)],
		"commands": queued_commands
	}
	packet_sequence += 1
	mouse_delta = Vector2.ZERO
	mouse_wheel = 0
	pending_keydowns.clear()
	pending_keyups.clear()
	pending_mouse_downs.clear()
	queued_commands.clear()
	socket.put_packet(JSON.stringify(packet).to_utf8_buffer())

func _exit_tree() -> void:
	socket.close()
