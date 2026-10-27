# ANINO SA GUBAT: Prompts That Match Your Current Sprites

These prompts describe the sprites exactly as they look in your sprite sheet (top row = idle, bottom row = attack), so an image AI produces art in the same style.

**Best results:** upload your sprite sheet as a **style/image reference** (Midjourney `--sref`, Leonardo Image Guidance, Flux Redux, SDXL IP-Adapter) AND paste the prompt. The reference locks the look; the prompt locks the character.

## STYLE BLOCK (append to every prompt)

```
16-bit pixel art game sprite, chunky visible pixels, limited dark palette, dithered shading,
front view, full body, centered, single character, hard readable silhouette, thin dark outline,
glowing round eyes with soft halo, plain solid very dark green-black background, no ground,
no floor shadow, no text, no watermark
```

## NEGATIVE PROMPT

```
smooth gradients, realistic, 3D render, anime, cute, smiling, multiple characters, cropped,
blurry, background scenery, ground, text, logo, watermark, bright colors
```

---

## 1. ASWANG

**Idle**
```
Aswang ghoul pixel sprite, hunched figure with a bald pale grey-white skull-like crown and long
straight black hair falling down both sides of the face, two large glowing red round eyes,
small white fangs, long thin red tongue hanging straight down the chest, dark charcoal
torn-robe body, thin pale grey arms hanging at the sides ending in tiny white claw fingers
```
**Attack**
```
Same Aswang pixel sprite, both thin pale arms thrown up and outward with claws spread,
mouth stretched wide open with dripping white fangs, extra long red tongue hanging down to
the waist, red eyes glowing brighter
```

## 2. MANANANGGAL

**Idle**
```
Manananggal pixel sprite, floating upper torso only, pale pink-mauve skin, bald head with dark
hair at the temples, glowing red round eyes, small white fangs, thin arms with tiny claw
fingers, large purple bat wings spread to both sides with spiked tips, jagged red entrails
dangling below the waist
```
**Attack**
```
Same Manananggal pixel sprite, wings raised higher and angled up, arms spread wide with claws
open, mouth gaping with bloody fangs, red entrails whipping below, eyes glowing brighter
```

## 3. TIKBALANG

**Idle**
```
Tikbalang pixel sprite, hunched shaggy brown body with segmented ribbed chest, horse head with
a dark black mane, glowing yellow-amber round eyes, flat square bared white teeth, long
spindly bent arms and legs with small white claws, coarse brown fur texture
```
**Attack**
```
Same Tikbalang pixel sprite, both long arms raised up overhead with claws open, teeth bared
wide, eyes glowing bright amber, body leaning forward
```

## 4. KAPRE

**Idle**
```
Kapre pixel sprite, huge boxy hulking body made of rough brown bark-like fur with patches of
green moss, small head with dark shaggy hair on top, two glowing orange eyes, two small white
tusks in the mouth, a lit cigar with a glowing orange ember and a trail of grey smoke rising
from the mouth, wide imposing stance
```
**Attack**
```
Same Kapre pixel sprite, mouth open wider showing tusks, cigar ember burning brighter, larger
grey smoke puff, eyes glowing intensely, body hunched forward
```

## 5. WHITE LADY

**Idle**
```
White Lady pixel sprite, tall narrow ghost in a long pale grey-white dress that widens
slightly and ends in a jagged torn hem, white veil on top of the head, long straight black
hair framing the face on both sides, glowing pale blue-white eyes, small black open oval
mouth, thin pale arms hanging at the sides, thin blue rim outline
```
**Attack**
```
Same White Lady pixel sprite, both thin pale arms raised up and outstretched with long
fingers, mouth stretched into a wide black scream, eyes glowing brighter blue-white
```

## 6. MULTO

**Idle**
```
Multo pixel sprite, round-headed blob ghost in translucent grey-blue mist, two glowing
white-blue eyes, a zigzag jagged black mouth, body widening toward the bottom with a jagged
fraying hem, tiny stubby arms at the sides, soft blue rim outline
```
**Attack**
```
Same Multo pixel sprite, small clawed arms raised up on both sides, jagged mouth stretched
wide open, eyes glowing brighter, body slightly stretched upward
```

## 7. SIGBIN

**Idle**
```
Sigbin pixel sprite, low round fuzzy dark charcoal body covered in shaggy fur, two pale cream
horn-like ears on top, glowing orange-red round eyes, small mouth with white fangs and a
drip of blood, thin dark spindly legs underneath, wide fur silhouette
```
**Attack**
```
Same Sigbin pixel sprite, mouth open wide with long white fangs and blood dripping, eyes
blazing orange-red, body crouched lower and leaning forward
```

---

## Workflow tips

- Generate large (512 or 1024), then downscale to 64x64 with **nearest-neighbor** so the pixels stay crisp.
- Remove the dark background to get a transparent PNG.
- Keep idle and attack in the same canvas size and the same character position so frame swaps do not jump.
- Generate idle first, then use it as the image reference for the attack prompt to keep the design consistent.
