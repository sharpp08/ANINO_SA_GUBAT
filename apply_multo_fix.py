"""
Run this ONCE from your game folder (the one with main.py):
    python apply_multo_fix.py
It patches enemies.py and main.py (backups saved as *.bak).
Then replace jumpscare.py with the new one and put multo_jumpscare.wav
into enemy_animations_pack/.
"""
import os, shutil, sys

def patch(path, pairs):
    if not os.path.exists(path):
        print(f"!! {path} not found - run this from the game folder"); sys.exit(1)
    s = open(path, encoding='utf-8').read()
    changed = False
    for name, old, new in pairs:
        if new in s:
            print(f"[skip] {path}: {name} already applied"); continue
        if s.count(old) != 1:
            print(f"!! {path}: could not find '{name}' (file differs from expected). Skipped."); continue
        s = s.replace(old, new); changed = True
        print(f"[ok]   {path}: {name}")
    if changed:
        shutil.copyfile(path, path + '.bak')
        open(path, 'w', encoding='utf-8').write(s)

patch('enemies.py', [('check_attacks fills last_attackers',
'''        total_damage = 0
        for enemy in self.enemies:
            if enemy.can_attack(player_x, player_y):
                total_damage += enemy.perform_attack()
        return total_damage''',
'''        total_damage = 0
        self.last_attackers = []
        for enemy in self.enemies:
            if enemy.can_attack(player_x, player_y):
                total_damage += enemy.perform_attack()
                self.last_attackers.append(enemy)
        return total_damage''')])

patch('main.py', [
('safe attack sound loop',
'''        for enemy in attackers:
            enemy_audio_mgr.play_spatial(
                enemy.type,
                'attack',
                p.x,
                p.y,
                p.angle,
                enemy.x,
                enemy.y,
                base_volume=1.0,
                max_dist=20.0,
            )
''',
'''        for enemy in attackers:
            try:
                enemy_audio_mgr.play_spatial(
                    enemy.type,
                    'attack',
                    p.x,
                    p.y,
                    p.angle,
                    enemy.x,
                    enemy.y,
                    base_volume=1.0,
                    max_dist=20.0,
                )
            except Exception as e:
                print(f"[Audio] attack sound failed for {enemy.type}: {e}")
'''),
('jumpscare error logging',
'''                        p.stunned = True
                        p.stun_timer = stun_duration
                except Exception:
                    pass
''',
'''                        p.stunned = True
                        p.stun_timer = stun_duration
                except Exception:
                    import traceback
                    print("[Jumpscare] trigger failed:")
                    traceback.print_exc()
''')])
print("\nDone. Now replace jumpscare.py and add enemy_animations_pack/multo_jumpscare.wav")
