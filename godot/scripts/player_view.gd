extends Node3D
## Presentation-only camera. Position, facing and flashlight state come from Python.

var camera: Camera3D
var flashlight: SpotLight3D
var target_position := Vector3.ZERO
var target_yaw := 0.0
var target_pitch := 0.0
var target_camera_height := 1.62
var has_received_state := false

func _ready() -> void:
	camera = Camera3D.new()
	camera.name = "PythonCamera"
	camera.position = Vector3(0.0, 1.62, 0.0)
	camera.fov = 78.0
	camera.current = true
	add_child(camera)

	flashlight = SpotLight3D.new()
	flashlight.name = "PythonFlashlight"
	flashlight.position = Vector3(0.12, -0.08, -0.18)
	flashlight.rotation_degrees.x = -3.0
	flashlight.light_color = Color(0.82, 0.9, 1.0)
	flashlight.light_energy = 2.6
	flashlight.spot_range = 22.0
	flashlight.spot_angle = 34.0
	flashlight.spot_angle_attenuation = 0.8
	flashlight.shadow_enabled = true
	camera.add_child(flashlight)

func _process(delta: float) -> void:
	if not has_received_state:
		return
	var blend := minf(1.0, delta * 18.0)
	global_position = global_position.lerp(target_position, blend)
	rotation.y = lerp_angle(rotation.y, target_yaw, blend)
	camera.rotation.x = lerpf(camera.rotation.x, target_pitch, blend)
	camera.position.y = lerpf(camera.position.y, target_camera_height, blend)

func apply_python_state(data: Dictionary) -> void:
	var px := float(data.get("x", 0.0))
	var py := float(data.get("y", 0.0))
	var angle := float(data.get("angle", 0.0))
	var pitch := float(data.get("pitch", 0.0))
	target_position = Vector3(px, 0.0, -py)
	target_yaw = angle - PI * 0.5
	target_pitch = pitch
	target_camera_height = 1.05 if bool(data.get("is_crouching", false)) else 1.62
	if not has_received_state:
		global_position = target_position
		rotation.y = target_yaw
		camera.rotation.x = target_pitch
		camera.position.y = target_camera_height
		has_received_state = true
	flashlight.visible = bool(data.get("flashlight_on", true)) and float(data.get("flashlight_battery", 0.0)) > 0.0
