# Saved reserved DATA capture review

The one-shot capture passed the independent saved-file audit: its receipt and all 13 input files match their sizes and SHA256 pins. The full `0x138000`-byte reserved DATA output has SHA256 `7204e27e9cc9fd5f5a145378b050a062f5f33dc20ed651e7d3d2090ba30caded`. The selected loader and sampler exactly match the reviewed artifacts, and the capture records one successful load and normal sampler-only unload.

The exclusive intent precedes loading in the pinned source; its files and directory are fsynced. The complete DATA output is closed and fsynced before sampler cleanup. State-before, state-after and the current saved resident state are byte identical, with both management intents consumed, uncertainty/failure preserved, no in-flight operation and no submit. Fresh checks of the owner note, reference count 1 and sampler absence completed on the successful loader route; this reviewer performed no live checks.

At reserved offset `0xa0000`, the first bytes are `EHLC`, with recorded length word `0x910` fitting inside the observed 4 KiB extent. The corresponding preboot 4 KiB bytes were zero. The full DATA sample differs from preboot in 70,107 bytes across 21 pages of 16 KiB each. Structured exception decoding is left to the separate native/crash reports.

Normal sampler exit releases its private copy, kobject and sysfs file. It does not release the unchanged owner's 174 backing pages, alter its consumed intents or reset the GPU. No B20 reply, second202, CPU stop, paired OFF, PMput or fresh physical OFF observation was added. Firmware private-cache freshness and atomicity remain unproved.
