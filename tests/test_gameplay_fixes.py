"""
Test suite for gameplay fixes (Rosary, Cross, Page-gated exit, Signature moves).
"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import sys
import pygame
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import Game, STATE_PLAYING
from player import Player
from enemies import Enemy, EnemyState

def test_rosary_cross():
    print("--- Testing Rosary & Cross ---")
    game = Game()
    p = game.player
    p.sanity = 50.0
    p.rosary_cooldown = 0.0
    p.cross_cooldown = 0.0
    
    assert p.use_rosary() == True
    assert p.sanity > 50.0
    assert p.rosary_cooldown > 0.0
    assert p.use_rosary() == False # Cooldown active
    
    assert p.use_cross() == True
    assert p.cross_cooldown > 0.0
    assert p.use_cross() == False # Cooldown active
    print("[PASS] Rosary & Cross Verified")

def test_page_gated_exit():
    print("--- Testing Page-Gated Exit ---")
    game = Game()
    game.load_chapter(1)
    game.state = STATE_PLAYING
    p = game.player
    p.pages_this_chapter = 0
    
    # Try reaching exit without pages
    ex, ey = game.game_map.exit_pos
    p.x, p.y = ex, ey
    game.update_playing(0.016, 0.0, 0.0)
    assert game.chapter == 1, "Chapter should remain 1 when pages are insufficient"
    
    # Collect enough pages
    p.pages_this_chapter = 3
    game.update_playing(0.016, 0.0, 0.0)
    assert game.chapter == 2, "Chapter should advance to 2 when page requirement is met"
    print("[PASS] Page-Gated Exit Verified")

def test_signature_moves():
    print("--- Testing Enemy Signature Moves ---")
    game = Game()
    gm = game.game_map
    e_aswang = Enemy('aswang', 10.0, 10.0)
    e_aswang.state = EnemyState.STALK
    e_aswang.just_entered_chase = True
    e_aswang.update(0.016, 1.0, 1.0, gm)
    assert e_aswang.animation_state == 'transform'
    
    e_tikbalang = Enemy('tikbalang', 10.0, 10.0)
    e_tikbalang.state = EnemyState.INVESTIGATE
    e_tikbalang.just_entered_chase = True
    e_tikbalang.update(0.016, 1.0, 1.0, gm)
    assert e_tikbalang.animation_state == 'rear'
    print("[PASS] Signature Moves Verified")

if __name__ == '__main__':
    print("=== STARTING GAMEPLAY FIXES TEST SUITE ===")
    test_rosary_cross()
    test_page_gated_exit()
    test_signature_moves()
    print("=== GAMEPLAY FIXES TEST SUITE COMPLETE: ALL PASSED ===")
