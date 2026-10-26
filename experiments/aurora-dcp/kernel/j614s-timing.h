/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Parse the actual T604x timing catalog. Never substitute the J713 panel. */
static inline int j614s_timing_u32(const struct dcp_m4_timing_parser *p,
		unsigned int dict, const char *key, u32 *out)
{
	int index = dcp_m4_timing_field(p, dict, key, 4);

	if (index < 0 || p->token[index].value > U32_MAX)
		return -EINVAL;
	*out = p->token[index].value;
	return 0;
}

static inline int j614s_timing_axis(const struct dcp_m4_timing_parser *p,
		unsigned int dict, const char *key, u32 expected, u32 values[6])
{
	static const char * const fields[] = {
		"Active", "Total", "FrontPorch", "SyncWidth", "BackPorch", "PreciseSyncRate",
	};
	int axis = dcp_m4_timing_field(p, dict, key, 1);

	if (axis < 0)
		return -EINVAL;
	for (unsigned int i = 0; i < 6; i++)
		if (j614s_timing_u32(p, axis, fields[i], &values[i]))
			return -EINVAL;
	if (values[0] != expected || values[1] > 65535 ||
	    !values[3] || values[3] > 4096 || values[2] > 4096 || values[4] > 4096 ||
	    values[1] != (u64)values[0] + values[2] + values[3] + values[4] ||
	    !dcp_m4_timing_equals(p, axis, "SyncPolarity", 4, 1) ||
	    !dcp_m4_timing_equals(p, axis, "PixelRepetition", 4, 0))
		return -EINVAL;
	return 0;
}

static inline int j614s_parse_timing(const struct dcp_m4_timing_parser *p,
		struct dcp_m4_timing *out)
{
	u64 best = U64_MAX;
	unsigned int mode = 1;
	bool found = false;

	if (p->token[0].type != 2 || !p->token[0].count || p->token[0].count > 128)
		return -EINVAL;
	for (; mode < p->token[0].next; mode = p->token[mode].next) {
		u32 h[6], v[6], id, color_id = 0, chosen_depth = 0;
		u64 clock, score;
		int colors;

		if (p->token[mode].type != 1 ||
		    !dcp_m4_timing_equals(p, mode, "IsVirtual", 11, 0) ||
		    !dcp_m4_timing_equals(p, mode, "IsInterlaced", 11, 0) ||
		    !dcp_m4_timing_equals(p, mode, "IsSplit", 11, 0) ||
		    j614s_timing_u32(p, mode, "ID", &id) ||
		    j614s_timing_axis(p, mode, "HorizontalAttributes", 3024, h) ||
		    j614s_timing_axis(p, mode, "VerticalAttributes", 1964, v) ||
		    v[5] < 20U * 65536 || v[5] > 121U * 65536)
			continue;
		/* Horizontal is 16.16 kHz; vertical is 16.16 Hz. The donor's
		 * 6877358 / 3932166 pair independently establishes this factor.
		 */
		if ((u64)h[5] * 1000 > (u64)v[5] * v[1] + 65536 ||
		    (u64)h[5] * 1000 + 65536 < (u64)v[5] * v[1])
			continue;
		colors = dcp_m4_timing_field(p, mode, "ColorModes", 2);
		if (colors < 0 || !p->token[colors].count)
			continue;
		for (unsigned int c = colors + 1; c < p->token[colors].next; c = p->token[c].next) {
			u32 depth, candidate;

			if (p->token[c].type != 1 || j614s_timing_u32(p, c, "Depth", &depth) ||
			    j614s_timing_u32(p, c, "ID", &candidate) ||
			    (depth != 8 && depth != 10) ||
			    !dcp_m4_timing_equals(p, c, "PixelEncoding", 4, 0) ||
			    !dcp_m4_timing_equals(p, c, "DynamicRange", 4, 0) ||
			    !dcp_m4_timing_equals(p, c, "EOTF", 4, 0))
				continue;
			if (!chosen_depth || depth < chosen_depth) {
				color_id = candidate;
				chosen_depth = depth;
			}
		}
		if (!chosen_depth)
			continue;
		clock = ((u64)h[1] * v[1] * v[5] >> 16) / 1000;
		if (clock < 5000 || clock > 2000000)
			continue;
		/* Prefer the physical 60-Hz SDR mode for the first takeover. */
		score = v[5] > 60U * 65536 ? v[5] - 60U * 65536 : 60U * 65536 - v[5];
		if (score >= best)
			continue;
		best = score;
		found = true;
		*out = (struct dcp_m4_timing) {
			.id = id, .color_id = color_id,
			.hdisplay = h[0], .hsync_start = h[0] + h[2],
			.hsync_end = h[0] + h[2] + h[3], .htotal = h[1],
			.vdisplay = v[0], .vsync_start = v[0] + v[2],
			.vsync_end = v[0] + v[2] + v[3], .vtotal = v[1],
			.clock_khz = clock, .refresh_16_16 = v[5],
		};
	}
	return found ? 0 : -ENOENT;
}
