extends Node3D
## Godot is the renderer. Python/Pygame remains the sole gameplay authority.

const BRIDGE_SCRIPT := preload("res://scripts/python_bridge.gd")
const PLAYER_VIEW_SCRIPT := preload("res://scripts/player_view.gd")

var bridge: Node
var player_view: Node3D
var world_root: Node3D
var ground: MeshInstance3D
var enemy_root: Node3D
var pickup_root: Node3D
var hud_layer: CanvasLayer
var menu_panel: PanelContainer
var pause_panel: PanelContainer
var stats_label: Label
var objective_label: Label
var notification_label: Label
var connection_label: Label
var enemy_nodes: Dictionary = {}
var pickup_nodes: Dictionary = {}
var current_world_key := ""
var last_snapshot_sequence := -1

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_environment()
	_create_world()
	_create_player()
	_create_bridge()
	_build_interface()
	_show_menu()

func _create_bridge() -> void:
	bridge = BRIDGE_SCRIPT.new()
	bridge.name = "PythonBridge"
	bridge.connect("state_received", Callable(self, "_on_python_state"))
	bridge.connect("bridge_error", Callable(self, "_on_bridge_error"))
	add_child(bridge)

func _setup_environment() -> void:
	var world_env := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(0.012, 0.025, 0.04)
	sky_material.sky_horizon_color = Color(0.075, 0.09, 0.095)
	sky_material.ground_bottom_color = Color(0.008, 0.012, 0.012)
	sky_material.ground_horizon_color = Color(0.035, 0.045, 0.04)
	sky.sky_material = sky_material
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.19, 0.23, 0.28)
	environment.ambient_light_energy = 0.32
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.fog_enabled = true
	environment.fog_light_color = Color(0.10, 0.14, 0.15)
	environment.fog_density = 0.028
	environment.fog_sky_affect = 0.7
	world_env.environment = environment
	add_child(world_env)
	var moonlight := DirectionalLight3D.new()
	moonlight.rotation_degrees = Vector3(-42.0, -28.0, 0.0)
	moonlight.light_color = Color(0.48, 0.58, 0.72)
	moonlight.light_energy = 0.22
	moonlight.shadow_enabled = true
	add_child(moonlight)

func _create_world() -> void:
	world_root = Node3D.new()
	world_root.name = "PythonWorldGeometry"
	add_child(world_root)
	enemy_root = Node3D.new()
	enemy_root.name = "PythonEnemyVisuals"
	add_child(enemy_root)
	pickup_root = Node3D.new()
	pickup_root.name = "PythonPickupVisuals"
	add_child(pickup_root)
	ground = MeshInstance3D.new()
	ground.name = "ForestGround"
	var plane := PlaneMesh.new()
	plane.size = Vector2(260.0, 260.0)
	ground.mesh = plane
	var ground_mat := StandardMaterial3D.new()
	ground_mat.albedo_color = Color(0.075, 0.085, 0.065)
	ground_mat.roughness = 1.0
	ground.material_override = ground_mat
	world_root.add_child(ground)

func _create_player() -> void:
	player_view = Node3D.new()
	player_view.name = "PythonDrivenPlayerView"
	player_view.set_script(PLAYER_VIEW_SCRIPT)
	add_child(player_view)

func _build_interface() -> void:
	hud_layer = CanvasLayer.new()
	hud_layer.layer = 5
	add_child(hud_layer)
	var hud := Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud_layer.add_child(hud)
	var top := VBoxContainer.new()
	top.position = Vector2(26, 22)
	top.add_theme_constant_override("separation", 5)
	hud.add_child(top)
	var title := _label("ANINO SA GUBAT", 20)
	top.add_child(title)
	connection_label = _label("WAITING FOR PYTHON GAME...", 12)
	top.add_child(connection_label)
	stats_label = _label("HP --   SAN --   STM --   BAT --", 14)
	top.add_child(stats_label)
	objective_label = _label("Waiting for authoritative game state.", 13)
	top.add_child(objective_label)
	notification_label = _label("", 16)
	notification_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	notification_label.position = Vector2(-300, 70)
	notification_label.custom_minimum_size = Vector2(600, 35)
	notification_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hud.add_child(notification_label)
	var controls := _label("WASD MOVE   SHIFT SPRINT   CTRL CROUCH   F FLASHLIGHT   LMB FIRE   R RELOAD   ESC PAUSE", 11)
	controls.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	controls.position = Vector2(24, -28)
	hud.add_child(controls)

	menu_panel = _make_panel(hud, Vector2(0.5, 0.5), Vector2(500, 330))
	var menu_box := VBoxContainer.new()
	menu_box.alignment = BoxContainer.ALIGNMENT_CENTER
	menu_box.add_theme_constant_override("separation", 15)
	menu_panel.add_child(menu_box)
	var heading := _label("ANINO SA GUBAT", 32)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	menu_box.add_child(heading)
	var sub := _label("MGA BULONG NG DILIM", 14)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	menu_box.add_child(sub)
	var start := Button.new()
	start.text = "ENTER THE FOREST"
	start.custom_minimum_size = Vector2(270, 48)
	start.pressed.connect(_start_game)
	menu_box.add_child(start)
	var hint := _label("Python owns gameplay. Godot renders the world.", 12)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	menu_box.add_child(hint)
	var quit := Button.new()
	quit.text = "QUIT GODOT VIEWER"
	quit.pressed.connect(func(): get_tree().quit())
	menu_box.add_child(quit)

	pause_panel = _make_panel(hud, Vector2(0.5, 0.5), Vector2(360, 190))
	var pause_box := VBoxContainer.new()
	pause_box.alignment = BoxContainer.ALIGNMENT_CENTER
	pause_box.add_theme_constant_override("separation", 12)
	pause_panel.add_child(pause_box)
	var pause_title := _label("PAUSED", 28)
	pause_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pause_box.add_child(pause_title)
	var resume := Button.new()
	resume.text = "RESUME"
	resume.pressed.connect(_resume_game)
	pause_box.add_child(resume)
	pause_panel.hide()

func _label(value: String, size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", Color(0.82, 0.86, 0.82))
	return label

func _make_panel(parent: Control, anchor: Vector2, panel_size: Vector2) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.anchor_left = anchor.x
	panel.anchor_top = anchor.y
	panel.anchor_right = anchor.x
	panel.anchor_bottom = anchor.y
	panel.custom_minimum_size = panel_size
	panel.offset_left = -panel_size.x * 0.5
	panel.offset_top = -panel_size.y * 0.5
	panel.offset_right = panel_size.x * 0.5
	panel.offset_bottom = panel_size.y * 0.5
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.018, 0.035, 0.038, 0.96)
	style.border_color = Color(0.30, 0.39, 0.37, 0.9)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.set_content_margin_all(25)
	panel.add_theme_stylebox_override("panel", style)
	parent.add_child(panel)
	return panel

func _show_menu() -> void:
	menu_panel.show()
	pause_panel.hide()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _start_game() -> void:
	menu_panel.hide()
	pause_panel.hide()
	bridge.call("send_command", "start_game")
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	connection_label.text = "START REQUEST SENT TO PYTHON"

func _resume_game() -> void:
	bridge.call("send_command", "resume_game")
	pause_panel.hide()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _on_bridge_error(message: String) -> void:
	connection_label.text = message

func _on_python_state(state: Dictionary) -> void:
	last_snapshot_sequence = int(state.get("sequence", last_snapshot_sequence))
	var game_state := str(state.get("game_state", "menu"))
	var player_data: Dictionary = state.get("player", {})
	if player_view and player_view.has_method("apply_python_state"):
		player_view.call("apply_python_state", player_data)
	if state.has("world"):
		_apply_world(state["world"])
	_sync_enemies(state.get("enemies", []))
	_sync_pickups(state.get("pickups", []))
	_update_hud(player_data, state)
	connection_label.text = "PYTHON CONNECTED  •  %s  •  SNAPSHOT %d" % [game_state.to_upper(), last_snapshot_sequence]
	if game_state == "playing":
		menu_panel.hide()
		pause_panel.hide()
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif game_state == "paused":
		menu_panel.hide()
		pause_panel.show()
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif game_state in ["menu", "gameover", "win"]:
		pause_panel.hide()
		menu_panel.show()
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif game_state == "intro" or game_state == "settings":
		menu_panel.hide()
		pause_panel.hide()
	if state.has("notification"):
		notification_label.text = str(state.get("notification", ""))

func _update_hud(p: Dictionary, state: Dictionary) -> void:
	stats_label.text = "HP %d   SAN %d   STM %d   BAT %d%%" % [
		int(p.get("health", 0)), int(p.get("sanity", 0)),
		int(p.get("stamina", 0)), int(p.get("flashlight_battery", 0))
	]
	var time_left := maxf(0.0, float(p.get("survival_time", 0.0)))
	objective_label.text = "CHAPTER %d   PAGES %d/5   SALT %d   GARLIC %d   TIME %d:%02d" % [
		int(state.get("chapter", 1)), int(p.get("pages", 0)),
		int(p.get("salt", 0)), int(p.get("garlic", 0)),
		int(time_left / 60.0), int(time_left) % 60
	]

func _apply_world(world: Dictionary) -> void:
	var key := "%s:%s" % [str(world.get("chapter", 1)), str(world.get("revision", 0))]
	if key == current_world_key:
		return
	current_world_key = key
	var map_width := maxf(16.0, float(world.get("width", 256)))
	var map_height := maxf(16.0, float(world.get("height", 256)))
	var ground_plane := ground.mesh as PlaneMesh
	if ground_plane:
		ground_plane.size = Vector2(map_width, map_height)
	ground.position = Vector3(map_width * 0.5, -0.08, -map_height * 0.5)
	for child in world_root.get_children():
		if child.name != "ForestGround":
			child.queue_free()
	var trunk_mat := StandardMaterial3D.new()
	trunk_mat.albedo_color = Color(0.105, 0.075, 0.052)
	trunk_mat.roughness = 1.0
	var canopy_mat := StandardMaterial3D.new()
	canopy_mat.albedo_color = Color(0.025, 0.075, 0.052)
	canopy_mat.roughness = 1.0
	for tree_data in world.get("trees", []):
		if not tree_data is Dictionary:
			continue
		var x := float(tree_data.get("x", 0.0))
		var z := -float(tree_data.get("y", 0.0))
		var scale := clampf(float(tree_data.get("scale", 1.0)), 0.55, 2.4)
		var height := 5.5 * scale
		var trunk := MeshInstance3D.new()
		var trunk_mesh := CylinderMesh.new()
		trunk_mesh.top_radius = 0.22 * scale
		trunk_mesh.bottom_radius = 0.34 * scale
		trunk_mesh.height = height
		trunk.mesh = trunk_mesh
		trunk.material_override = trunk_mat
		trunk.position = Vector3(x, height * 0.5, z)
		world_root.add_child(trunk)
		var crown := MeshInstance3D.new()
		var crown_mesh := SphereMesh.new()
		crown_mesh.radius = 1.7 * scale
		crown_mesh.height = 3.0 * scale
		crown.mesh = crown_mesh
		crown.material_override = canopy_mat
		crown.position = Vector3(x, height + 0.8 * scale, z)
		world_root.add_child(crown)

func _sync_enemies(items: Array) -> void:
	var seen: Dictionary = {}
	for item in items:
		if not item is Dictionary:
			continue
		var id := str(item.get("id", ""))
		seen[id] = true
		var node: Node3D = enemy_nodes.get(id)
		if not is_instance_valid(node):
			node = _make_enemy_visual(str(item.get("type", "aswang")))
			enemy_root.add_child(node)
			enemy_nodes[id] = node
		var target_position := Vector3(float(item.get("x", 0.0)), float(item.get("flight_lift", 0.0)), -float(item.get("y", 0.0)))
		var target_yaw := float(item.get("angle", 0.0)) - PI * 0.5
		node.visible = bool(item.get("alive", true))
		if node.position == Vector3.ZERO:
			node.position = target_position
		else:
			node.position = node.position.lerp(target_position, 0.55)
		node.rotation.y = lerp_angle(node.rotation.y, target_yaw, 0.55)
	for id in enemy_nodes.keys():
		if not seen.has(id):
			enemy_nodes[id].queue_free()
			enemy_nodes.erase(id)

func _make_enemy_visual(enemy_type: String) -> Node3D:
	var root := Node3D.new()
	root.name = "PythonEnemy_" + enemy_type
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.38
	capsule.height = 1.8
	body.mesh = capsule
	var material := StandardMaterial3D.new()
	material.roughness = 1.0
	match enemy_type:
		"white_lady": material.albedo_color = Color(0.72, 0.72, 0.68)
		"kapre": material.albedo_color = Color(0.16, 0.12, 0.09)
		"manananggal": material.albedo_color = Color(0.25, 0.12, 0.16)
		"multo": material.albedo_color = Color(0.45, 0.48, 0.52)
		_: material.albedo_color = Color(0.18, 0.19, 0.14)
	body.material_override = material
	body.position.y = 0.9
	root.add_child(body)
	var eyes := MeshInstance3D.new()
	var eye_mesh := SphereMesh.new()
	eye_mesh.radius = 0.07
	eye_mesh.height = 0.14
	eyes.mesh = eye_mesh
	var eye_mat := StandardMaterial3D.new()
	eye_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	eye_mat.albedo_color = Color(0.85, 0.025, 0.015)
	eyes.material_override = eye_mat
	eyes.position = Vector3(0.0, 1.25, -0.32)
	root.add_child(eyes)
	return root

func _sync_pickups(items: Array) -> void:
	var seen: Dictionary = {}
	for item in items:
		if not item is Dictionary:
			continue
		var id := str(item.get("id", ""))
		seen[id] = true
		var node: MeshInstance3D = pickup_nodes.get(id)
		if not is_instance_valid(node):
			node = MeshInstance3D.new()
			var mesh := BoxMesh.new()
			mesh.size = Vector3(0.35, 0.35, 0.35)
			node.mesh = mesh
			var mat := StandardMaterial3D.new()
			mat.albedo_color = Color(0.72, 0.58, 0.28)
			mat.emission_enabled = true
			mat.emission = Color(0.18, 0.12, 0.035)
			node.material_override = mat
			pickup_root.add_child(node)
			pickup_nodes[id] = node
		node.position = Vector3(float(item.get("x", 0.0)), 0.45, -float(item.get("y", 0.0)))
	for id in pickup_nodes.keys():
		if not seen.has(id):
			pickup_nodes[id].queue_free()
			pickup_nodes.erase(id)
