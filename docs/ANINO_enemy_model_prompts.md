# ANINO SA GUBAT: Enemy Models and Prompts (Aggressive Set)

All 7 enemies from your `enemies.py`. Each has:
- **Sprite prompt**: paste into an image AI (Midjourney, Leonardo, DALL-E, Flux, SDXL) for the main billboard.
- **Attack prompt**: same character, mid-attack, for the `attack` / `lunge` frames.
- **3D prompt**: paste into Meshy, Tripo, Rodin or similar if you want a real 3D model.

Your game draws enemies as 64x64 billboards with a jagged glowing rim and glowing eyes, so every prompt asks for a front-facing figure, a hard silhouette, and a dark background you can cut out.

---

## Paste this STYLE BLOCK at the end of every sprite prompt

```
front view, full body, centered, single character, aggressive threatening pose,
dark Philippine folklore horror, low-resolution pixel art look, limited color palette,
hard readable silhouette, jagged glowing rim light, glowing eyes, dark dripping edges,
plain solid black background, no ground, no shadow on floor, no text, no watermark
```

## Paste this into the NEGATIVE PROMPT box (if your tool has one)

```
cute, friendly, cartoon, smiling, multiple characters, cropped, blurry, text, logo,
watermark, background scenery, trees, ground, modern clothing, gun, bright colors
```

## Tips
- Generate at 512x512 or 1024x1024, then shrink to 64x64 with nearest-neighbor so it stays crisp.
- Remove the black background (remove.bg, Photoshop, GIMP) to get a transparent PNG.
- Rim colors below are the exact ones your game uses, so the new art blends with the glow effect.

---

## 1. ASWANG
**Role in game:** stalker. Circles you at medium range, then lunges. Retreats at low HP.
**Stats:** HP 80, damage 15, speed 2.0
**Eyes:** red `#DC1E1E` | **Rim:** crimson `#961923`

**Sprite prompt**
```
Aswang, Philippine shapeshifting ghoul, hunched emaciated humanoid with long matted black hair
hanging over a gaunt pale face, sunken glowing red eyes, mouth stretched open showing rows of
sharp yellow fangs and a long thin blood-slick tongue, torn dark rags, bony arms with long
clawed fingers spread wide, back arched like a predator about to pounce, dark maroon and
charcoal palette
```
**Attack prompt**
```
Aswang lunging forward, jaw unhinged wide, tongue whipping out, both clawed hands reaching
straight toward the viewer, hair flying back, eyes blazing bright red, body stretched in
mid-leap, motion-blur claws
```
**3D prompt**
```
Aswang Philippine ghoul, hunched emaciated humanoid, long matted black hair, gaunt pale skin,
glowing red eyes, fanged open mouth with long tongue, torn rags, elongated clawed hands,
aggressive predator crouch, game-ready low poly, T-pose friendly, PBR textures
```

---

## 2. MANANANGGAL
**Role in game:** flying hunter. Hovers, fast, strong against Bind. Dangles entrails below.
**Stats:** HP 100, damage 20, speed 2.5
**Eyes:** red `#FF2828` | **Rim:** magenta-crimson `#B42346`

**Sprite prompt**
```
Manananggal, Philippine self-segmenting vampire, upper torso of a woman severed at the waist
and floating in the air, huge black leathery bat wings fully spread, long wild black hair,
glowing red eyes, snarling fanged mouth, clawed hands raised, dark red entrails and a long
tongue trailing below the torso, deep purple, black and blood-red palette
```
**Attack prompt**
```
Manananggal swooping down at the viewer, wings folded back in a dive, mouth open in a
shriek showing fangs, long clawed arms and a thin proboscis-like tongue reaching forward,
entrails whipping behind, eyes blazing red
```
**3D prompt**
```
Manananggal Philippine vampire, floating upper torso only, large bat wings, long black hair,
glowing red eyes, fangs, clawed hands, dangling entrails below the waist cut, hovering
pose, game-ready, PBR textures
```

---

## 3. TIKBALANG
**Role in game:** heavy bruiser. Slow but hits hard. Weak to Shield, resists Repel.
**Stats:** HP 150, damage 30, speed 1.8
**Eyes:** amber `#FFB400` | **Rim:** amber-orange `#D28219`

**Sprite prompt**
```
Tikbalang, Philippine forest horse-demon, towering muscular humanoid body with a black horse
head, long bared teeth, flared nostrils, wild dark mane, glowing amber eyes, extremely long
spindly legs with knees bent backward, thick clawed hands clenched into fists, standing
tall and looming, chest forward, dark brown and black coarse fur
```
**Attack prompt**
```
Tikbalang rearing up and charging, front hooves and clawed fists raised overhead ready to
smash down, head thrown forward, mouth wide with teeth bared, mane whipping, eyes blazing amber
```
**3D prompt**
```
Tikbalang Philippine horse-headed demon, tall muscular humanoid, black horse head with bared
teeth, long mane, glowing amber eyes, very long thin legs with reversed knees, clawed hands,
aggressive looming stance, game-ready, PBR textures
```

---

## 4. KAPRE
**Role in game:** giant tank. Slowest, most HP, longest reach. Weak to Banish. (Not placed in chapters yet.)
**Stats:** HP 200, damage 35, speed 1.2
**Eyes:** burning orange `#C86400` | **Rim:** burnt orange `#B45F19`

**Sprite prompt**
```
Kapre, Philippine giant tree spirit, enormous hulking dark brown humanoid covered in coarse
fur and bark-like skin, mossy shoulders, huge shoulders and thick arms, glowing orange eyes
under a heavy brow, tusked snarling mouth, smoking cigar glowing in its mouth with drifting
smoke, gnarled fists clenched, standing wide and imposing, dark brown and ember orange palette
```
**Attack prompt**
```
Kapre swinging one massive fist down toward the viewer, other arm braced, mouth roaring
open with tusks bared, cigar embers flying, eyes blazing orange, shoulders hunched forward
```
**3D prompt**
```
Kapre Philippine giant tree dweller, huge hairy dark humanoid with bark-textured skin,
glowing orange eyes, tusks, lit cigar in mouth, massive clenched fists, wide imposing
stance, game-ready, PBR textures
```

---

## 5. WHITE LADY
**Role in game:** long-range ghost. Biggest detect and attack range (12 / 3.0). Weak to Bind, resists Banish. (Not placed in chapters yet.)
**Stats:** HP 60, damage 10, speed 1.5
**Eyes:** hollow black | **Rim:** pale blue `#C8DCFF`

**Sprite prompt**
```
White Lady, Philippine vengeful ghost, floating woman in a long tattered white dress that
fades into mist at the hem, long black hair hanging over her face, hollow pitch-black eye
sockets, cracked pale grey skin, mouth stretched in a silent scream, arms outstretched with
long pale fingers reaching forward, faint ghostly translucency, pale blue and white palette
```
**Attack prompt**
```
White Lady surging toward the viewer, face distorted into a wide screaming skull-like
expression, hair streaming back, both pale clawed hands grasping forward, dress whipping
like smoke, black eye sockets deep and empty
```
**3D prompt**
```
White Lady Philippine ghost, floating woman in a torn white dress fading to mist, long black
hair, hollow black eyes, pale cracked skin, screaming mouth, reaching hands, translucent
ghostly look, game-ready, PBR textures
```

---

## 6. MULTO
**Role in game:** weak but common spirit. Hovers and drifts. Weak to Banish.
**Stats:** HP 50, damage 12, speed 2.0
**Eyes:** dim blue-grey `#646478` | **Rim:** soft blue `#A0B4EB`

**Sprite prompt**
```
Multo, Filipino restless ghost, tall shapeless shroud-like spirit made of layered translucent
grey-blue mist, vague gaunt face with two glowing pale eyes and a jagged hollow mouth, long
wispy arms ending in clawed tendrils, edges fraying into smoke, hovering above the ground,
cold spectral blue and grey palette
```
**Attack prompt**
```
Multo lunging forward, mist body stretched and warped toward the viewer, mouth gaping wide and
jagged, tendril arms reaching out like claws, eyes glowing brighter, smoke trailing behind
```
**3D prompt**
```
Multo Filipino ghost, shroud-shaped translucent spirit, gaunt hollow face, glowing pale eyes,
wispy clawed tendril arms, floating, frayed smoky edges, game-ready, semi-transparent
material
```

---

## 7. SIGBIN
**Role in game:** fastest enemy. Crawls low, attacks very quickly. Weak to Bind.
**Stats:** HP 70, damage 18, speed 3.5
**Eyes:** orange-red `#FF3C00` | **Rim:** fiery orange `#D2460F`

**Sprite prompt**
```
Sigbin, Philippine blood-drinking creature, low hunched hornless goat-hound beast with
shaggy dark charcoal fur, hind legs raised and head lowered near the ground, long clawed
paws, ribs showing, glowing orange-red eyes, snarling muzzle full of jagged teeth with blood
dripping, thin tail whipping, ready to spring, dark grey and ember palette
```
**Attack prompt**
```
Sigbin mid-pounce leaping at the viewer, jaws open wide with long fangs, front claws
extended, fur bristling, eyes blazing orange-red, body stretched and fast
```
**3D prompt**
```
Sigbin Philippine creature, hunched goat-hound beast with shaggy charcoal fur, raised hind legs,
low head, long claws, jagged teeth, glowing orange eyes, crouched predator pose, game-ready,
PBR textures
```

---

## Which game frames each prompt covers

Your game picks a sprite per animation state. Generate one **sprite prompt** image for the resting states and one **attack prompt** image for the aggressive states:

| Game states | Use |
|---|---|
| idle, walk, stalk, crawl, crouch, hover, stagger | Sprite prompt |
| attack, lunge, run, sprint | Attack prompt |
| death | Sprite prompt image, flattened or tilted on the ground |

Right now `asset_generator.py` draws these sprites with code (`generate_enemy_sprite`), so PNGs you generate here will not appear in the game until a small loader is added. That is a short change if you want it.
