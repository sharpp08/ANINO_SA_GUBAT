# Main-menu soundtrack integration

## Project integration

- Asset path: `assets/audio/Hawig ng Buhay.mp3`
- Playback: streamed through `pygame.mixer.music`; the track loops continuously while the main menu or its Settings screen is open.
- Transitions: 1.8-second fade-in on menu entry and 1.2-second fade-out when leaving the menu.
- Volume: Master Volume × Music Volume × 0.55. The extra headroom keeps menu music behind UI and game audio.
- The supplied file measures about 119.97 seconds, stereo, with a peak near -1.34 dBFS. It is already at a healthy peak level; avoid normalizing it louder. If a future master is made, target roughly -16 to -14 LUFS integrated and keep true peak at or below -1 dBTP.
- Streaming avoids decoding the full two-minute MP3 into a large in-memory sound buffer. Keep the original file's sample rate/channel layout unless a target platform requires a conversion.
- The MP3 loops at its natural end. Listen to the end-to-start boundary; if there is an audible seam, make a seamless loop edit in an audio editor or use two audio sources with a 1–2 second equal-power crossfade. The current Pygame stream uses a fade for screen transitions, not a second overlapping track for loop-boundary crossfades.

## Unity recommendation

1. Import the MP3 into an AudioClip.
2. Set **Load Type** to Streaming, **Preload Audio Data** off if memory is tight, and **Load In Background** on.
3. Add an AudioSource to a persistent menu-audio object; enable **Loop**, disable **Play On Awake** if you want code-controlled entry, and set Spatial Blend to 0 (2D).
4. Set volume to about 0.45–0.55, then expose Master and Music multipliers through an AudioMixer.
5. On menu entry call `audioSource.Play()`; fade the AudioMixer Music parameter from -80 dB to its target over ~1.5–2 seconds. On menu exit fade to -80 dB over ~1–1.5 seconds before stopping or switching scenes. Use a second AudioSource for a true overlapping crossfade.

Example:
```csharp
using UnityEngine;
using System.Collections;

public class MenuMusic : MonoBehaviour
{
    [SerializeField] AudioSource source;
    [SerializeField] float targetVolume = 0.5f;
    Coroutine fade;

    public void EnterMenu() {
        if (!source.isPlaying) {
            source.volume = 0f;
            source.loop = true;
            source.Play();
        }
        FadeTo(targetVolume, 1.8f);
    }

    public void LeaveMenu() => FadeTo(0f, 1.2f);

    void FadeTo(float target, float seconds) {
        if (fade != null) StopCoroutine(fade);
        fade = StartCoroutine(FadeRoutine(target, seconds));
    }

    IEnumerator FadeRoutine(float target, float seconds) {
        float start = source.volume, elapsed = 0f;
        while (elapsed < seconds) {
            elapsed += Time.unscaledDeltaTime;
            source.volume = Mathf.Lerp(start, target, elapsed / seconds);
            yield return null;
        }
        source.volume = target;
        if (target <= 0f) source.Stop();
    }
}
```

## Unreal Engine recommendation

1. Import the MP3 as a Sound Wave and create a Sound Cue (or MetaSound) with a looping node.
2. Play it as a 2D sound, not spatialized. Use a Sound Class / Sound Mix for the Music bus.
3. Start it from the main menu widget's Construct event or Player Controller; keep the Audio Component alive across menu widget changes.
4. Use an Audio Component fade-in of ~1.5–2 seconds and fade-out of ~1–1.5 seconds when entering gameplay. Use two Audio Components and crossfade their volumes if transitioning directly to another music track.
5. Expose Master and Music controls separately, with the menu track initially around 0.5 of the Music bus gain.

## Asset placement

Copy the supplied file into the repository at:

```
assets/audio/Hawig ng Buhay.mp3
```

The runtime code logs a clear warning and continues normally if the file is not present.
