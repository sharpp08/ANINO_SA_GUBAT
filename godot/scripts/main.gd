extends Node3D

const PLAYER_SCRIPT = preload("res://scripts/player_view.gd")

var player: CharacterBody3D
var hud_layer: CanvasLayer
var menu_panel: PanelContainer
var pause_panel: PanelContainer
var stamina_bar: ProgressBar
var status_label: Label
var game_started := false
var paused := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_environment()
	_create_world()
	_create_player()
	_build_interface()
	_show_main_menu()

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
	var ground := MeshInstance3D.new()
	ground.name = "ForestGround"
	var plane := PlaneMesh.new()
	plane.size = Vector2(180.0, 180.0)
	ground.mesh = plane
	var ground_mat := StandardMaterial3D.new()
	ground_mat.albedo_color = Color(0.075, 0.085, 0.065)
	ground_mat.roughness = 1.0
	ground.material_override = ground_mat
	ground.position.y = -0.08
	add_child(ground)

	var ground_body := StaticBody3D.new()
	var ground_collision := CollisionShape3D.new()
	var ground_shape := BoxShape3D.new()
	ground_shape.size = Vector3(180.0, 0.2, 180.0)
	ground_collision.shape = ground_shape
	ground_collision.position.y = -0.1
	ground_body.add_child(ground_collision)
	add_child(ground_body)
	_create_forest()

func _create_forest() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261120
	var trunk_mat := StandardMaterial3D.new()
	trunk_mat.albedo_color = Color(0.105, 0.075, 0.052)
	trunk_mat.roughness = 1.0
	var canopy_mat := StandardMaterial3D.new()
	canopy_mat.albedo_color = Color(0.025, 0.075, 0.052)
	canopy_mat.roughness = 1.0

	for i in range(190):
		var x := rng.randf_range(-78.0, 78.0)
		var z := rng.randf_range(-78.0, 78.0)
		if Vector2(x, z).length() < 9.0:
			continue
		var height := rng.randf_range(5.0, 10.0)
		var trunk := MeshInstance3D.new()
		var trunk_mesh := CylinderMesh.new()
		trunk_mesh.top_radius = rng.randf_range(0.18, 0.34)
		trunk_mesh.bottom_radius = trunk_mesh.top_radius * 1.35
		trunk_mesh.height = height
		trunk.mesh = trunk_mesh
		trunk.material_override = trunk_mat
		trunk.position = Vector3(x, height * 0.5, z)
		add_child(trunk)

		var crown := MeshInstance3D.new()
		var crown_mesh := SphereMesh.new()
		crown_mesh.radius = rng.randf_range(1.5, 2.8)
		crown_mesh.height = crown_mesh.radius * 1.7
		crown.mesh = crown_mesh
		crown.material_override = canopy_mat
		crown.position = Vector3(x, height + crown_mesh.radius * 0.45, z)
		crown.scale = Vector3(1.0, 1.2, 1.0)
		add_child(crown)

func _create_player() -> void:
	player = CharacterBody3D.new()
	player.name = "FirstPersonPlayer"
	player.set_script(PLAYER_SCRIPT)
	player.process_mode = Node.PROCESS_MODE_PAUSABLE
	player.position = Vector3(0.0, 1.0, 0.0)
	add_child(player)

func _build_interface() -> void:
	hud_layer = CanvasLayer.new()
	hud_layer.name = "GameInterface"
	add_child(hud_layer)

	var hud := Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud_layer.add_child(hud)

	var top_left := VBoxContainer.new()
	top_left.position = Vector2(28, 24)
	top_left.add_theme_constant_override("separation", 8)
	hud.add_child(top_left)

	var title := Label.new()
	title.text = "ANINO SA GUBAT"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color(0.78, 0.84, 0.82))
	top_left.add_child(title)

	status_label = Label.new()
	status_label.text = "SURVIVE THE FOREST  •  Find a way out"
	status_label.add_theme_font_size_override("font_size", 14)
	status_label.add_theme_color_override("font_color", Color(0.66, 0.75, 0.72))
	top_left.add_child(status_label)

	var bottom := VBoxContainer.new()
	bottom.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	bottom.position = Vector2(28, -78)
	bottom.add_theme_constant_override("separation", 5)
	hud.add_child(bottom)

	var stamina_title := Label.new()
	stamina_title.text = "STAMINA"
	stamina_title.add_theme_font_size_override("font_size", 12)
	bottom.add_child(stamina_title)

	stamina_bar = ProgressBar.new()
	stamina_bar.custom_minimum_size = Vector2(230, 14)
	stamina_bar.max_value = 100.0
	stamina_bar.value = 100.0
	stamina_bar.show_percentage = false
	bottom.add_child(stamina_bar)

	var controls := Label.new()
	controls.text = "WASD Move   SHIFT Sprint   CTRL Crouch   F Flashlight   ESC Pause"
	controls.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	controls.position = Vector2(-520, -34)
	controls.add_theme_font_size_override("font_size", 12)
	controls.add_theme_color_override("font_color", Color(0.68, 0.73, 0.72))
	hud.add_child(controls)

	menu_panel = _make_panel(hud, Vector2(0.5, 0.5), Vector2(520, 390))
	var menu_content := VBoxContainer.new()
	menu_content.alignment = BoxContainer.ALIGNMENT_CENTER
	menu_content.add_theme_constant_override("separation", 18)
	menu_panel.add_child(menu_content)

	var game_title := Label.new()
	game_title.text = "ANINO SA GUBAT"
	game_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	game_title.add_theme_font_size_override("font_size", 34)
	menu_content.add_child(game_title)

	var subtitle := Label.new()
	subtitle.text = "MGA BULONG NG DILIM"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_font_size_override("font_size", 15)
	menu_content.add_child(subtitle)

	var start_button := Button.new()
	start_button.text = "ENTER THE FOREST"
	start_button.custom_minimum_size = Vector2(280, 48)
	start_button.pressed.connect(_start_game)
	menu_content.add_child(start_button)

	var hint := Label.new()
	hint.text = "WASD  Move     SHIFT  Sprint     CTRL  Crouch\nF  Flashlight     ESC  Pause"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_font_size_override("font_size", 13)
	menu_content.add_child(hint)

	var quit_button := Button.new()
	quit_button.text = "QUIT"
	quit_button.custom_minimum_size = Vector2(280, 38)
	quit_button.pressed.connect(func(): get_tree().quit())
	menu_content.add_child(quit_button)

	pause_panel = _make_panel(hud, Vector2(0.5, 0.5), Vector2(420, 230))
	var pause_content := VBoxContainer.new()
	pause_content.alignment = BoxContainer.ALIGNMENT_CENTER
	pause_content.add_theme_constant_override("separation", 14)
	pause_panel.add_child(pause_content)

	var paused_title := Label.new()
	paused_title.text = "PAUSED"
	paused_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	paused_title.add_theme_font_size_override("font_size", 28)
	pause_content.add_child(paused_title)

	var resume_button := Button.new()
	resume_button.text = "RESUME"
	resume_button.pressed.connect(_resume_game)
	pause_content.add_child(resume_button)

	var menu_button := Button.new()
	menu_button.text = "MAIN MENU"
	menu_button.pressed.connect(_return_to_menu)
	pause_content.add_child(menu_button)
	pause_panel.hide()

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
	panel.add_theme_stylebox_override("panel", _panel_style())
	parent.add_child(panel)
	return panel

func _panel_style() -> StyleBox:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.018, 0.035, 0.038, 0.96)
	style.border_color = Color(0.30, 0.39, 0.37, 0.9)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.set_content_margin_all(28)
	return style

func _show_main_menu() -> void:
	menu_panel.show()
	pause_panel.hide()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_tree().paused = false

func _start_game() -> void:
	game_started = true
	paused = false
	menu_panel.hide()
	pause_panel.hide()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	status_label.text = "SURVIVE THE FOREST  •  Find a way out"
	survival.begin_run()
	survival.show_hud(true)

func _resume_game() -> void:
	paused = false
	get_tree().paused = false
	pause_panel.hide()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _return_to_menu() -> void:
	game_started = false
	paused = false
	get_tree().paused = false
	_show_main_menu()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and game_started:
		if paused:
			_resume_game()
		else:
			paused = true
			pause_panel.show()
			get_tree().paused = true
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _process(_delta: float) -> void:
	if player:
		stamina_bar.value = player.stamina
