extends Node3D
## Standalone Godot survival layer for ANINO SA GUBAT.
## Uses procedural placeholder meshes so the game is playable before source art is converted.

const ENEMY_TYPES := [
	{"name":"Aswang","hp":70.0,"speed":3.15,"damage":13.0,"range":1.8,"cooldown":1.6,"color":Color(0.18,0.19,0.14),"scale":Vector3(0.82,1.75,0.82),"sanity":5.0},
	{"name":"Kapre","hp":180.0,"speed":1.25,"damage":24.0,"range":2.7,"cooldown":2.4,"color":Color(0.16,0.12,0.09),"scale":Vector3(1.55,2.6,1.4),"sanity":4.0},
	{"name":"Manananggal","hp":90.0,"speed":2.25,"damage":15.0,"range":2.2,"cooldown":2.0,"color":Color(0.25,0.12,0.16),"scale":Vector3(0.9,2.0,0.9),"sanity":5.0},
	{"name":"White Lady","hp":55.0,"speed":2.0,"damage":11.0,"range":1.8,"cooldown":1.8,"color":Color(0.72,0.72,0.68),"scale":Vector3(0.8,1.9,0.8),"sanity":8.0},
	{"name":"Sigbin","hp":28.0,"speed":4.2,"damage":9.0,"range":1.35,"cooldown":1.1,"color":Color(0.34,0.12,0.10),"scale":Vector3(0.65,0.85,0.65),"sanity":3.0},
	{"name":"Tikbalang","hp":110.0,"speed":2.7,"damage":17.0,"range":2.0,"cooldown":1.7,"color":Color(0.24,0.15,0.11),"scale":Vector3(0.95,2.2,0.95),"sanity":6.0},
	{"name":"Multo","hp":52.0,"speed":2.0,"damage":10.0,"range":1.8,"cooldown":1.8,"color":Color(0.45,0.48,0.52),"scale":Vector3(0.8,1.9,0.8),"sanity":9.0}
]

var player: CharacterBody3D
var camera: Camera3D
var hud: Control
var health_bar: ProgressBar
var sanity_bar: ProgressBar
var ammo_label: Label
var objective_label: Label
var prompt_label: Label
var message_label: Label
var weapon_viewmodel: TextureRect
var weapon_label: Label
var enemies: Array[Dictionary] = []
var pickups: Array[Dictionary] = []
var wards: Array[Dictionary] = []
var health := 100.0
var sanity := 100.0
var ammo := 12
var reserve_ammo := 48
var max_ammo := 12
var weapon_index := 0
var weapon_names := ["SERVICE PISTOL", "HUNTING SHOTGUN"]
var weapon_damage := [38.0, 82.0]
var weapon_capacity := [12, 4]
var weapon_reserve := [48, 20]
var frenzy := false
var game_active := false
var game_over := false
var kills := 0
var pages_found := 0
var ward_charges := 3
var shot_cooldown := 0.0
var reload_timer := 0.0
var message_timer := 0.0
var spawn_timer := 0.0
var objective_complete := false
var rng := RandomNumberGenerator.new()
var ambience_player: AudioStreamPlayer
var frenzy_player: AudioStreamPlayer
var weapon_player: AudioStreamPlayer
var reload_player: AudioStreamPlayer

func _ready() -> void:
	rng.seed = 20261120
	_setup_audio()
	set_process(true)
	_build_hud()

func configure(target_player: CharacterBody3D) -> void:
	player = target_player
	camera = player.get_node_or_null("FirstPersonCamera") as Camera3D

func begin_run() -> void:
	health = 100.0
	sanity = 100.0
	ammo = 12
	reserve_ammo = 48
	weapon_index = 0
	max_ammo = 12
	kills = 0
	pages_found = 0
	ward_charges = 3
	frenzy = false
	game_over = false
	objective_complete = false
	game_active = true
	if ambience_player and not ambience_player.playing: ambience_player.play()
	_clear_runtime_entities()
	_spawn_initial_enemies()
	_spawn_pickups()
	_show_message("Find the 5 torn pages. Do not let the forest take you.", 5.0)
	_update_hud()

func stop_run() -> void:
	game_active = false
	if ambience_player: ambience_player.stop()
	if frenzy_player: frenzy_player.stop()
	_clear_runtime_entities()

func _clear_runtime_entities() -> void:
	for item in enemies:
		if is_instance_valid(item.get("node")): item.node.queue_free()
	for item in pickups:
		if is_instance_valid(item.get("node")): item.node.queue_free()
	for item in wards:
		if is_instance_valid(item.get("node")): item.node.queue_free()
	enemies.clear()
	pickups.clear()
	wards.clear()

func _process(delta: float) -> void:
	if not game_active or game_over or not is_instance_valid(player):
		return
	shot_cooldown = maxf(0.0, shot_cooldown - delta)
	message_timer = maxf(0.0, message_timer - delta)
	if message_timer <= 0.0:
		message_label.text = ""
	if reload_timer > 0.0:
		reload_timer -= delta
		if reload_timer <= 0.0:
			var needed := max_ammo - ammo
			var loaded: int = mini(needed, reserve_ammo)
			ammo += loaded
			reserve_ammo -= loaded
			_show_message("Reloaded", 1.0)
	_update_enemies(delta)
	_update_pickups()
	_update_wards(delta)
	_update_sanity(delta)
	if frenzy and frenzy_player and not frenzy_player.playing: frenzy_player.play()
	elif not frenzy and frenzy_player and frenzy_player.playing: frenzy_player.stop()
	_update_hud()

func _unhandled_input(event: InputEvent) -> void:
	if not game_active or game_over:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_fire_weapon()
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_R: _reload()
			KEY_Q: _place_ward()
			KEY_1: _switch_weapon(0)
			KEY_2: _switch_weapon(1)
			KEY_E: _interact()
			KEY_G: _use_sanity_tonic()

func _setup_audio() -> void:
	ambience_player = AudioStreamPlayer.new()
	ambience_player.name = "ForestRainAmbience"
	ambience_player.volume_db = -17.0
	var rain = load("res://assets/audio/rain_ambience.mp3") if ResourceLoader.exists("res://assets/audio/rain_ambience.mp3") else null
	if rain:
		rain.loop = true
		ambience_player.stream = rain
	add_child(ambience_player)
	frenzy_player = AudioStreamPlayer.new()
	frenzy_player.name = "FrenzyAmbience"
	frenzy_player.volume_db = -9.0
	var frenzy_stream = load("res://assets/audio/frenzy_mode_ambience.mp3") if ResourceLoader.exists("res://assets/audio/frenzy_mode_ambience.mp3") else null
	if frenzy_stream:
		frenzy_stream.loop = true
		frenzy_player.stream = frenzy_stream
	add_child(frenzy_player)
	weapon_player = AudioStreamPlayer.new()
	weapon_player.name = "WeaponSound"
	weapon_player.volume_db = -3.0
	add_child(weapon_player)
	reload_player = AudioStreamPlayer.new()
	reload_player.name = "ReloadSound"
	reload_player.volume_db = -6.0
	add_child(reload_player)
	_set_weapon_audio()

func _set_weapon_audio() -> void:
	if not weapon_player or not reload_player: return
	var view_path := "res://assets/sprites/weapons/revolver/revolver_hero.png" if weapon_index == 0 else "res://assets/sprites/weapons/shotgun/shotgun_hero.png"
	if weapon_viewmodel and ResourceLoader.exists(view_path): weapon_viewmodel.texture = load(view_path)
	var fire_path := "res://assets/audio/revolver_gunshot.mp3" if weapon_index == 0 else "res://assets/audio/shotgun_fire.mp3"
	var reload_path := "res://assets/audio/revolver_reload.mp3" if weapon_index == 0 else "res://assets/audio/shotgun_reload.mp3"
	if ResourceLoader.exists(fire_path): weapon_player.stream = load(fire_path)
	if ResourceLoader.exists(reload_path): reload_player.stream = load(reload_path)

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "SurvivalHUD"
	layer.layer = 5
	add_child(layer)
	hud = Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(hud)

	var top := VBoxContainer.new()
	top.position = Vector2(28, 104)
	top.add_theme_constant_override("separation", 5)
	hud.add_child(top)
	var health_title := _label("VITAL SIGNS", 12)
	top.add_child(health_title)
	health_bar = ProgressBar.new()
	health_bar.custom_minimum_size = Vector2(210, 13)
	health_bar.max_value = 100
	health_bar.show_percentage = false
	top.add_child(health_bar)
	var sanity_title := _label("SANITY", 12)
	top.add_child(sanity_title)
	sanity_bar = ProgressBar.new()
	sanity_bar.custom_minimum_size = Vector2(210, 13)
	sanity_bar.max_value = 100
	sanity_bar.show_percentage = false
	top.add_child(sanity_bar)

	objective_label = _label("OBJECTIVE  •  Find the torn pages", 15)
	objective_label.position = Vector2(28, 210)
	hud.add_child(objective_label)

	var bottom := VBoxContainer.new()
	bottom.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	bottom.position = Vector2(-270, -100)
	bottom.add_theme_constant_override("separation", 4)
	hud.add_child(bottom)
	weapon_viewmodel = TextureRect.new()
	weapon_viewmodel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	weapon_viewmodel.position = Vector2(-350, -300)
	weapon_viewmodel.custom_minimum_size = Vector2(330, 270)
	weapon_viewmodel.size = Vector2(330, 270)
	weapon_viewmodel.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	weapon_viewmodel.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	weapon_viewmodel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(weapon_viewmodel)
	weapon_label = _label("SERVICE PISTOL", 13)
	weapon_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	bottom.add_child(weapon_label)
	ammo_label = _label("12 / 48", 25)
	ammo_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	bottom.add_child(ammo_label)

	prompt_label = _label("", 15)
	prompt_label.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	prompt_label.position = Vector2(-230, -105)
	prompt_label.custom_minimum_size = Vector2(460, 32)
	prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hud.add_child(prompt_label)

	message_label = _label("", 17)
	message_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	message_label.position = Vector2(-380, 75)
	message_label.custom_minimum_size = Vector2(760, 40)
	message_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hud.add_child(message_label)

	var help := _label("LMB FIRE   R RELOAD   1/2 WEAPON   Q SALT WARD   E INTERACT   G TONIC", 11)
	help.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	help.position = Vector2(28, -28)
	hud.add_child(help)
	hud.hide()

func _label(value: String, size: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", Color(0.82, 0.86, 0.82))
	return label

func show_hud(value: bool) -> void:
	hud.visible = value

func _update_hud() -> void:
	health_bar.value = health
	sanity_bar.value = sanity
	ammo_label.text = "%d / %d" % [ammo, reserve_ammo]
	weapon_label.text = weapon_names[weapon_index] + ("  •  FRENZY" if frenzy else "")
	objective_label.text = "PAGES %d / 5     |     ENTITIES BANISHED %d     |     SALT WARDS %d" % [pages_found, kills, ward_charges]
	if health <= 25.0:
		health_bar.modulate = Color(1.0, 0.25, 0.2)
	else:
		health_bar.modulate = Color(0.75, 0.85, 0.78)
	if sanity <= 30.0:
		sanity_bar.modulate = Color(0.8, 0.25, 0.55)
	else:
		sanity_bar.modulate = Color(0.65, 0.78, 0.9)

func _spawn_initial_enemies() -> void:
	for i in range(7):
		_spawn_enemy(i, _random_forest_position(18.0, 42.0))

func _spawn_enemy(type_index: int, at: Vector3) -> void:
	var data: Dictionary = ENEMY_TYPES[clampi(type_index, 0, 6)].duplicate(true)
	var root := Node3D.new()
	root.name = String(data.name).strip_edges().replace(" ", "_")
	root.position = at
	var body := MeshInstance3D.new()
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.42
	mesh.height = 1.7
	body.mesh = mesh
	body.scale = data.scale
	var material := StandardMaterial3D.new()
	material.albedo_color = data.color
	material.roughness = 1.0
	material.metallic = 0.0
	body.material_override = material
	root.add_child(body)
	var sprite_path := "res://assets/sprites/enemies/%s_idle.png" % String(data.name).to_lower().replace(" ", "_")
	if ResourceLoader.exists(sprite_path):
		var enemy_sprite := Sprite3D.new()
		enemy_sprite.texture = load(sprite_path)
		enemy_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		enemy_sprite.pixel_size = 0.012
		enemy_sprite.position.y = 1.0
		enemy_sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
		root.add_child(enemy_sprite)
		body.visible = false
	var eye := MeshInstance3D.new()
	var eye_mesh := SphereMesh.new()
	eye_mesh.radius = 0.075
	eye_mesh.height = 0.15
	eye.mesh = eye_mesh
	var eye_mat := StandardMaterial3D.new()
	eye_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	eye_mat.albedo_color = Color(0.85, 0.04, 0.025)
	eye.material_override = eye_mat
	eye.position = Vector3(0, 0.42, -0.37)
	root.add_child(eye)
	add_child(root)
	enemies.append({"node":root,"data":data,"hp":float(data.hp),"attack":0.0,"type":type_index})

func _spawn_pickups() -> void:
	for i in range(5):
		_spawn_pickup("page", _random_forest_position(10.0, 60.0))
	for i in range(4):
		_spawn_pickup("ammo", _random_forest_position(8.0, 52.0))
	for i in range(3):
		_spawn_pickup("medkit", _random_forest_position(8.0, 48.0))
	for i in range(3):
		_spawn_pickup("tonic", _random_forest_position(8.0, 55.0))

func _spawn_pickup(kind: String, at: Vector3) -> void:
	var node := Node3D.new()
	node.position = at + Vector3.UP * 0.45
	var mesh_node := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.42, 0.42, 0.42)
	mesh_node.mesh = mesh
	var mat := StandardMaterial3D.new()
	match kind:
		"page": mat.albedo_color = Color(0.75,0.68,0.43)
		"ammo": mat.albedo_color = Color(0.75,0.62,0.22)
		"medkit": mat.albedo_color = Color(0.65,0.12,0.12)
		_: mat.albedo_color = Color(0.22,0.55,0.72)
	mat.emission_enabled = true
	mat.emission = mat.albedo_color * 0.25
	mesh_node.material_override = mat
	node.add_child(mesh_node)
	add_child(node)
	pickups.append({"node":node,"kind":kind})

func _random_forest_position(min_radius: float, max_radius: float) -> Vector3:
	var angle := rng.randf_range(0.0, TAU)
	var radius := rng.randf_range(min_radius, max_radius)
	return Vector3(cos(angle)*radius, 0.0, sin(angle)*radius)

func _update_enemies(delta: float) -> void:
	for i in range(enemies.size()-1, -1, -1):
		var item: Dictionary = enemies[i]
		var node: Node3D = item.node
		if not is_instance_valid(node):
			enemies.remove_at(i)
			continue
		var offset := player.global_position - node.global_position
		offset.y = 0.0
		var distance := offset.length()
		var data: Dictionary = item.data
		if distance < 45.0 and distance > float(data.range) * 0.72:
			var direction := offset.normalized()
			node.global_position += direction * float(data.speed) * (1.35 if frenzy else 1.0) * delta
			node.look_at(Vector3(player.global_position.x, node.global_position.y, player.global_position.z), Vector3.UP)
		item.attack = maxf(0.0, float(item.attack) - delta)
		if distance <= float(data.range) and float(item.attack) <= 0.0:
			_damage_player(float(data.damage))
			item.attack = float(data.cooldown)
		if distance < 22.0:
			sanity = maxf(0.0, sanity - float(data.sanity) * delta * 0.35)

func _fire_weapon() -> void:
	if shot_cooldown > 0.0 or reload_timer > 0.0:
		return
	if ammo <= 0:
		_show_message("Empty. Press R to reload.", 1.2)
		return
	ammo -= 1
	if weapon_player: weapon_player.play()
	shot_cooldown = 0.48 if weapon_index == 0 else 0.9
	var from := camera.global_position
	var direction := -camera.global_transform.basis.z
	var best: Dictionary = {}
	var best_distance := 55.0
	for item in enemies:
		var node: Node3D = item.node
		if not is_instance_valid(node): continue
		var target := node.global_position + Vector3.UP * 0.9
		var to_target := target - from
		var distance := to_target.length()
		if distance < best_distance and direction.dot(to_target.normalized()) > 0.965:
			var query := PhysicsRayQueryParameters3D.create(from, target)
			query.exclude = [player]
			var hit := get_world_3d().direct_space_state.intersect_ray(query)
			if hit.is_empty() or hit.collider == node:
				best = item
				best_distance = distance
	if not best.is_empty():
		best.hp = float(best.hp) - weapon_damage[weapon_index]
		var target_node: Node3D = best.node
		target_node.scale *= 0.97
		if float(best.hp) <= 0.0:
			target_node.queue_free()
			enemies.erase(best)
			kills += 1
			_show_message("Entity banished: %s" % best.data.name, 1.8)
	else:
		_show_message("The shot disappears into the fog.", 0.6)

func _reload() -> void:
	if reload_timer > 0.0 or ammo >= max_ammo or reserve_ammo <= 0: return
	reload_timer = 1.25 if weapon_index == 0 else 1.8
	if reload_player: reload_player.play()
	_show_message("Reloading...", reload_timer)

func _switch_weapon(index: int) -> void:
	if index < 0 or index > 1 or index == weapon_index: return
	weapon_index = index
	_set_weapon_audio()
	max_ammo = weapon_capacity[index]
	ammo = mini(ammo, max_ammo)
	reserve_ammo = weapon_reserve[index]
	_show_message("Equipped %s" % weapon_names[index], 1.2)

func _place_ward() -> void:
	if ward_charges <= 0:
		_show_message("No salt wards remaining.", 1.4)
		return
	ward_charges -= 1
	var ward := Node3D.new()
	ward.position = player.global_position
	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 1.15
	torus.outer_radius = 1.32
	ring.mesh = torus
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.85,0.82,0.68)
	mat.emission_enabled = true
	mat.emission = Color(0.45,0.38,0.22)
	ring.material_override = mat
	ring.position.y = 0.08
	ward.add_child(ring)
	add_child(ward)
	wards.append({"node":ward,"time":18.0})
	_show_message("Salt ward placed. Stay inside its circle.", 2.0)

func _update_wards(delta: float) -> void:
	for i in range(wards.size()-1,-1,-1):
		var ward: Dictionary = wards[i]
		ward.time = float(ward.time) - delta
		if float(ward.time) <= 0.0:
			ward.node.queue_free()
			wards.remove_at(i)
			continue
		for enemy in enemies:
			if is_instance_valid(enemy.node) and enemy.node.global_position.distance_to(ward.node.global_position) < 2.0:
				enemy.hp = float(enemy.hp) - 18.0 * delta
				if float(enemy.hp) <= 0.0:
					enemy.node.queue_free()
					enemies.erase(enemy)
					kills += 1

func _update_pickups() -> void:
	prompt_label.text = ""
	for i in range(pickups.size()-1,-1,-1):
		var item: Dictionary = pickups[i]
		var node: Node3D = item.node
		if not is_instance_valid(node):
			pickups.remove_at(i)
			continue
		node.rotate_y(0.8 * get_process_delta_time())
		if node.global_position.distance_to(player.global_position) < 1.7:
			match item.kind:
				"page":
					pages_found += 1
					sanity = minf(100.0, sanity + 8.0)
					_show_message("Torn page recovered (%d/5)." % pages_found, 2.0)
					if pages_found >= 5: objective_complete = true
				"ammo":
					reserve_ammo += 12
					_show_message("Ammunition recovered.", 1.2)
				"medkit":
					health = minf(100.0, health + 35.0)
					_show_message("First aid used. Health restored.", 1.5)
				"tonic":
					sanity = minf(100.0, sanity + 30.0)
					_show_message("Herbal tonic. Sanity restored.", 1.5)
			node.queue_free()
			pickups.remove_at(i)
	if objective_complete and not game_over:
		objective_label.text = "ALL PAGES FOUND  •  Find the forest exit"

func _interact() -> void:
	if objective_complete:
		_show_message("The path opens. You escaped the forest.", 5.0)
		game_active = false
		_show_end_panel(true)
	else:
		_show_message("Search the forest for the five torn pages.", 2.0)

func _use_sanity_tonic() -> void:
	_show_message("Collect a blue herbal tonic first; walk over it to use it.", 1.5)

func _update_sanity(delta: float) -> void:
	frenzy = sanity <= 30.0
	if frenzy:
		sanity = maxf(0.0, sanity - 0.35 * delta)
	if sanity <= 0.0:
		_damage_player(8.0 * delta)
	if health <= 0.0 and not game_over:
		game_over = true
		game_active = false
		_show_end_panel(false)

func _damage_player(amount: float) -> void:
	health = maxf(0.0, health - amount)
	if health <= 0.0 and not game_over:
		game_over = true
		game_active = false
		_show_end_panel(false)

func _show_message(value: String, duration: float) -> void:
	message_label.text = value
	message_timer = duration

func _show_end_panel(won: bool) -> void:
	_show_message("YOU ESCAPED THE FOREST" if won else "THE FOREST CLAIMS YOU", 999.0)
	prompt_label.text = "Press ESC to return to the main menu"
