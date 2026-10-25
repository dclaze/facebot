# Speech mouth rendering review

The Android mouth uses supplied audio-clock phoneme shapes, not a repeating speech oscillator. `MouthRenderer` owns only vector drawing and finite pose interpolation; audio epochs, interruption and phoneme scheduling remain the client's responsibility.

## Design

Nine poses share the same four-cubic contour topology. Closed M/B/P and rest have zero aperture; the resting right corner lifts into a small knowing smile. Stretched E, open A, rounded O, pursed U/W, F/V lip contact, raised tongue and narrow consonants change contour, teeth exposure and tongue position together. Dental detail follows the upper arch rather than floating as a rectangular plate. Tongue color stays subdued within the mint palette. No tooth grid, individual fangs or skin-colored lip shapes.

Transitions finish in 45 ms, with 30 ms closures. A new target starts at the current interpolated pose. Preview renders the target directly without advancing or changing live animation state. No per-frame paths, paints, arrays, bitmaps or assets are allocated.

## Evidence and limits

- Reviewed all nine original native ghost-only screenshots: open pose was an ellipse with a large isolated tongue oval; narrow/teeth poses had conspicuous straight dental bars; rest and closure were visually almost identical.
- Standalone compilation against Android 36 succeeds with local JDK 17.
- Reviewed the first integrated set of nine native renders. Closed M/B/P is visibly sealed and separate from rest; O/U and stretched vowels read differently. Found and corrected a detached lower highlight, overly pinched open-jaw corners, and gray-looking semi-transparent teeth. The highlight now follows the actual lower contour and opening corners become vertical as aperture increases. These corrections compile; regenerated native stills are required to confirm them.
- Moving speech/interruption review remains required. Native stills cannot establish coarticulation quality, audible alignment, natural speech or a bar-raising finished result.
- Face canvas scales X and Y separately: review on the tablet's actual aspect ratio, not only a square preview. Existing cheek marks and eyes remain outside this renderer's scope.
- Closure must be driven by playback completion/interrupt, not arrival of a network packet. Accurate visible phoneme timing requires correctly indexed audio sample timings upstream.
