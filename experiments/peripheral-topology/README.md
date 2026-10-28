# Audio preflight

`audio-preflight.py` collects read-only information about ALSA devices, driver
metadata and the audio-related live device tree. It does not load drivers,
probe buses, record audio or play sound. It can help diagnose the still-untested
headphone jack and saves its report under a new `/var/tmp` directory.

Speaker output remains disabled; see the [speaker-safety assessment](../../docs/j614s-speaker-safety-investigation.md).
