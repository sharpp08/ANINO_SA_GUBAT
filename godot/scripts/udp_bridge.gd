extends Node

signal python_state_received(state: Dictionary)
signal python_packet_error(message: String)

const PYTHON_HOST := "127.0.0.1"
const PYTHON_PORT := 4244
const GODOT_PORT := 4243

var socket := PacketPeerUDP.new()
var connected := false
var send_accumulator := 0.0
var last_state: Dictionary = {}

func _ready() -> void:
	var err := socket.bind(GODOT_PORT, "127.0.0.1")
	if err != OK:
		python_packet_error.emit("Could not bind UDP bridge port %d (error %d)" % [GODOT_PORT, err])
		return
	socket.set_dest_address(PYTHON_HOST, PYTHON_PORT)
	connected = true
	print("ANINO bridge listening on 127.0.0.1:%d; Python target %d" % [GODOT_PORT, PYTHON_PORT])

func _process(delta: float) -> void:
	if not connected:
		return
	while socket.get_available_packet_count() > 0:
		var packet := socket.get_packet()
		var parsed: Variant = JSON.parse_string(packet.get_string_from_utf8())
		if parsed is Dictionary:
			last_state = parsed
			python_state_received.emit(last_state)
		elif parsed == null:
			python_packet_error.emit("Received invalid JSON packet from Python")

	send_accumulator += delta
	if send_accumulator >= 1.0 / 30.0:
		send_accumulator = 0.0
		var input_packet := {
			"type": "godot_input",
			"timestamp_usec": Time.get_ticks_usec(),
			"move": Input.get_vector("move_left", "move_right", "move_forward", "move_back"),
			"sprint": Input.is_key_pressed(KEY_SHIFT),
			"crouch": Input.is_key_pressed(KEY_CTRL),
			"flashlight_toggle": Input.is_key_pressed(KEY_F)
		}
		socket.put_packet(JSON.stringify(input_packet).to_utf8_buffer())

func _exit_tree() -> void:
	socket.close()
