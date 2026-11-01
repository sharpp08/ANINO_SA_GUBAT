"""TEMP offscreen capture of the compact top HUD panel + compass arrow (patch verification).

Run: .venv\Scripts\python.exe _hud_verify.py   (then delete this file)
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame
pygame.init()

from main import Game, STATE_PLAYING, STATE_PAUSED
from objective import next_objective, relative_bearing, direction_word
from settings import PAGES_REQUIRED_CH1, REQUIRE_PAGES_FOR_EXIT

game = Game()
# Under the dummy video driver self.screen is a 1x1 surface, but main.render()
# (line 935) scales self.internal into it in-place. Use a plain 1280x720
# surface instead - exactly what a real window would provide.
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
game.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

game.load_chapter(1)
game.state = STATE_PLAYING
game.player.pages_this_chapter = 2
game.player.survival_time_left = 6 * 60 + 23.4          # expect "SUNRISE 06:23"
game.notify("TEST NOTICE (centred under panel)", 5.0)

# What the panel's line 2 should say
needed = PAGES_REQUIRED_CH1
obj = next_objective(game.player.x, game.player.y, game.game_map.pickups,
                     game.game_map.exit_pos, 2, needed, REQUIRE_PAGES_FOR_EXIT)
if obj:
    rel = relative_bearing(game.player.x, game.player.y, game.player.angle,
                           obj["x"], obj["y"])
    print(f"Panel line2 should read: "
          f"{'NEAREST PAGE' if obj['kind'] == 'page' else 'EXIT'} "
          f"{int(obj['dist'])}m {direction_word(rel).upper()}  "
          f"(rel={rel:.3f} rad)")
else:
    print("No objective target found - panel line2 will be blank")

print("PageArrow frames:", len(game.page_arrow._frames),
      "(4 = sprite art, 1 = triangle fallback)")

out_dir = os.path.join(os.environ.get("TEMP", ROOT), "hud_verify")
os.makedirs(out_dir, exist_ok=True)

def save(name, scale=2):
    big = pygame.transform.scale(
        game.internal,
        (game.internal.get_width() * scale, game.internal.get_height() * scale))
    p = os.path.join(out_dir, name)
    pygame.image.save(big, p)
    print("SAVED", p)

# F3 debug cycle: compact (1) -> full (2) -> off (0)
for i, mode in enumerate((1, 2, 0)):
    game.renderer.debug_mode = mode
    game.update_playing(0.016, 0, 0)
    game.render(0.016)
    save(f"{i + 1}_playing_dbg{mode}.png")

# Paused path also renders the top panel now
game.state = STATE_PAUSED
game.render(0.016)
save("4_paused.png")

pygame.quit()
print("DONE")
