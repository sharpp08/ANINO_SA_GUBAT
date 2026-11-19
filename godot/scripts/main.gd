extends Node3D

const PLAYER_SCRIPT = preload("res://scripts/player_view.gd")
const BRIDGE_SCRIPT = preload("res://scripts/udp_bridge.gd")

func _ready() -> void:
	_setup_environment()
	_create_world()
	_create_player()
	_create_bridge()

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

	for i in range(150):
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
	var player := CharacterBody3D.new()
	player.name = "FirstPersonView"
	player.set_script(PLAYER_SCRIPT)
	player.position = Vector3(0.0, 1.0, 0.0)
	add_child(player)

func _create_bridge() -> void:
	var bridge := Node.new()
	bridge.name = "PythonBridge"
	bridge.set_script(BRIDGE_SCRIPT)
	add_child(bridge)
