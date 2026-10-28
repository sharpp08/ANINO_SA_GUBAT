"""
Graphics Quality Manager for ANINO SA GUBAT: Mga Bulong ng Dilim.

Provides a runtime-mutable source of truth for all renderer feature flags.
Bridges settings.apply_quality_preset (module-level globals) with the
ShaderRenderer (GPU state) so quality can change without restarting.
"""

import settings as _s


class GraphicsManager:
    """Manages runtime graphics-quality transitions.

    Usage:
        gm = GraphicsManager(renderer)
        gm.apply_tier('high')
        gm.set_overrides({'enable_bloom': False})
    """

    _GLOBAL_MAP = {
        'internal_width': 'INTERNAL_WIDTH',
        'internal_height': 'INTERNAL_HEIGHT',
        'max_render_trees': 'MAX_RENDER_TREES',
        'enable_particles': 'ENABLE_PARTICLES',
        'enable_dynamic_lights': 'ENABLE_DYNAMIC_LIGHTS',
        'enable_bloom': 'ENABLE_BLOOM',
        'enable_hdr': 'ENABLE_HDR',
        'enable_pbr': 'ENABLE_PBR',
        'enable_ssao': 'ENABLE_SSAO',
        'enable_god_rays': 'ENABLE_GOD_RAYS',
        'bloom_threshold': 'BLOOM_THRESHOLD',
        'bloom_intensity': 'BLOOM_INTENSITY',
        'bloom_blur_passes': 'BLOOM_BLUR_PASSES',
        'god_ray_samples': 'GOD_RAY_SAMPLES',
        'god_ray_intensity': 'GOD_RAY_INTENSITY',
        'god_ray_decay': 'GOD_RAY_DECAY',
        'hdr_exposure': 'HDR_EXPOSURE',
        'tone_mapping': 'TONE_MAPPING',
        'ssao_samples': 'SSAO_SAMPLES',
        'ssao_radius': 'SSAO_RADIUS',
        'ssao_strength': 'SSAO_STRENGTH',
        'water_speed_multiplier': 'WATER_SPEED_MULTIPLIER',
    }

    def __init__(self, renderer=None):
        self.renderer = renderer
        self._tier = _s.QUALITY_TIER
        self._overrides = {}
        self._effective = dict(_s.QUALITY_PRESETS.get(self._tier, _s.QUALITY_PRESETS['medium']))
        self._pending = None
        self._log = []

    @property
    def tier(self):
        return self._tier

    @property
    def effective_config(self):
        return dict(self._effective)

    def get_effective(self, key, default=None):
        return self._effective.get(key, default)

    def set_overrides(self, overrides):
        self._overrides = dict(overrides) if overrides else {}
        self.stage_transition(self._tier)

    def apply_tier(self, tier):
        """Switch quality tier immediately at a safe frame boundary."""
        if not self.stage_transition(tier):
            return False
        return self.commit()

    def stage_transition(self, tier):
        """Validate and prepare a new tier without committing yet."""
        if tier not in _s.QUALITY_PRESETS:
            self._log_msg(f"Reject: unknown tier '{tier}'")
            return False
        cfg = _s.QUALITY_PRESETS[tier].copy()
        for k, v in self._overrides.items():
            if k in cfg:
                cfg[k] = v
        self._pending = (tier, cfg)
        return True

    def commit(self):
        """Apply the staged configuration. Returns True on success."""
        if self._pending is None:
            return False
        tier, cfg = self._pending
        prev_tier = self._tier
        prev_effective = dict(self._effective)

        self._apply_to_globals(cfg)

        if self.renderer is not None:
            try:
                self._rebuild_renderer(cfg)
            except Exception as e:
                self._log_msg(f"Renderer rebuild failed for '{tier}': {e}")
                if prev_effective:
                    self._apply_to_globals(prev_effective)
                    try:
                        self._rebuild_renderer(prev_effective)
                    except Exception:
                        pass
                self._pending = None
                return False

        self._tier = tier
        self._effective = cfg
        self._pending = None
        self._log_msg(
            f"Quality -> {tier}  bloom={cfg['enable_bloom']} "
            f"hdr={cfg['enable_hdr']} god_rays={cfg['enable_god_rays']} "
            f"res={cfg['internal_width']}x{cfg['internal_height']}"
        )
        return True

    def rollback(self):
        self._pending = None

    def _apply_to_globals(self, cfg):
        for key, glob_name in self._GLOBAL_MAP.items():
            if key in cfg:
                setattr(_s, glob_name, cfg[key])
        _s.NUM_RAYS = cfg['internal_width']
        _s.WALL_HEIGHT_SCALE = cfg['internal_height'] * _s.TILE_SIZE
        _s.QUALITY_TIER = cfg.get('_tier', self._tier)
        _s.ACTIVE_QUALITY = cfg.copy()

    def _rebuild_renderer(self, cfg):
        sr = getattr(self.renderer, 'shader_renderer', None)
        if sr is None or not getattr(sr, 'enabled', False):
            return
        new_w = cfg['internal_width']
        new_h = cfg['internal_height']
        if new_w != sr.width or new_h != sr.height:
            sr.resize(new_w, new_h)
        sr.update_feature_flags(cfg)

    def _log_msg(self, msg):
        self._log.append(msg)
        if len(self._log) > 20:
            self._log.pop(0)
        print(f"[GRAPHICS] {msg}")

    def get_log(self):
        return list(self._log)


_instance = None

def get_graphics_manager(renderer=None):
    global _instance
    if _instance is None:
        _instance = GraphicsManager(renderer)
    elif renderer is not None and _instance.renderer is None:
        _instance.renderer = renderer
    return _instance
