extends CharacterBody3D

signal stats_changed(stamina: float, flashlight_active: bool)

@export var walk_speed: float = 4.0
@export var sprint_speed: float = 6.2
@export var mouse_sensitivity: float = 0.0018
@export var standing_height: float = 1.7
@export var crouch_height: float = 1.05
@export var max_stamina: float = 100.0
@export var stamina_drain: float = 25.0
@export var stamina_recovery: float = 17.0

var stamina: float = 100.0
var look_pitch: float = 0.0
var flashlight_on: bool = true
var is_crouching: bool = false
var camera: Camera3D
var flashlight: SpotLight3D
var collision: CollisionShape3D

func _ready() -> void:
	stamina = max_stamina
	_setup_input_actions()
	_build_collision()
	_build_camera_and_light()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _setup_input_actions() -> void:
	var bindings := {
		"move_forward": KEY_W,
		"move_back": KEY_S,
		"move_left": KEY_A,
		"move_right": KEY_D
	}
	for action_name in bindings:
		if not InputMap.has_action(action_name):
			InputMap.add_action(action_name)
		var event := InputEventKey.new()
		event.physical_keycode = bindings[action_name]
		InputMap.action_add_event(action_name, event)

func _build_collision() -> void:
	collision = CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.32
	capsule.height = standing_height
	collision.shape = capsule
	collision.position.y = standing_height * 0.5
	add_child(collision)

func _build_camera_and_light() -> void:
	camera = Camera3D.new()
	camera.name = "FirstPersonCamera"
	camera.position.y = standing_height - 0.12
	camera.fov = 78.0
	camera.current = true
	add_child(camera)

	flashlight = SpotLight3D.new()
	flashlight.name = "PlayerFlashlight"
	flashlight.position = Vector3(0.12, -0.08, -0.18)
	flashlight.rotation_degrees.x = -3.0
	flashlight.light_color = Color(0.82, 0.9, 1.0)
	flashlight.light_energy = 2.6
	flashlight.spot_range = 22.0
	flashlight.spot_angle = 34.0
	flashlight.spot_angle_attenuation = 0.8
	flashlight.shadow_enabled = true
	camera.add_child(flashlight)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * mouse_sensitivity)
		look_pitch = clamp(look_pitch - event.relative.y * mouse_sensitivity, deg_to_rad(-82.0), deg_to_rad(82.0))
		camera.rotation.x = look_pitch
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F:
		flashlight_on = not flashlight_on
		flashlight.visible = flashlight_on
		stats_changed.emit(stamina, flashlight_on)

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= 9.8 * delta
	else:
		velocity.y = 0.0

	var input_vector := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var wants_crouch := Input.is_key_pressed(KEY_CTRL)
	var wants_sprint := Input.is_key_pressed(KEY_SHIFT) and input_vector.length() > 0.1 and not wants_crouch and stamina > 0.5
	is_crouching = wants_crouch

	var speed := walk_speed
	if wants_sprint:
		speed = sprint_speed
		stamina = maxf(0.0, stamina - stamina_drain * delta)
	else:
		stamina = minf(max_stamina, stamina + stamina_recovery * delta)

	var target_height := crouch_height if is_crouching else standing_height
	camera.position.y = lerpf(camera.position.y, target_height - 0.12, delta * 12.0)
	var capsule := collision.shape as CapsuleShape3D
	capsule.height = target_height
	collision.position.y = target_height * 0.5

	var direction := (transform.basis * Vector3(input_vector.x, 0.0, input_vector.y)).normalized()
	if direction.length() > 0.0:
		velocity.x = direction.x * speed * (0.52 if is_crouching else 1.0)
		velocity.z = direction.z * speed * (0.52 if is_crouching else 1.0)
	else:
		velocity.x = move_toward(velocity.x, 0.0, walk_speed * 7.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, walk_speed * 7.0 * delta)
	move_and_slide()
	stats_changed.emit(stamina, flashlight_on)
