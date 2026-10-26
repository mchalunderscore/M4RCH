/* Allocate a permanent handle for an existing live provider. Caller owns np.
 * Unlike adding a phandle property alone, update the lookup field under the
 * same lock used by of_find_node_by_phandle(). No resources are changed.
 */
int of_m4rch_ensure_phandle(struct device_node *np, u32 *handle)
{
	struct property *prop;
	struct device_node *iter;
	unsigned long flags;
	u32 max = 0;
	int ret = 0;
	bool added = false;
	if (!np || !handle)
		return -EINVAL;
	prop = kzalloc(sizeof(*prop), GFP_KERNEL);
	if (!prop)
		return -ENOMEM;
	prop->name = kstrdup("phandle", GFP_KERNEL);
	prop->value = kzalloc(sizeof(__be32), GFP_KERNEL);
	prop->length = sizeof(__be32);
	if (!prop->name || !prop->value) {
		ret = -ENOMEM;
		goto free;
	}
	mutex_lock(&of_mutex);
	raw_spin_lock_irqsave(&devtree_lock, flags);
	if (of_node_check_flag(np, OF_DETACHED)) {
		ret = -ENODEV;
	} else if (np->phandle) {
		*handle = np->phandle;
	} else {
		for_each_of_allnodes(iter)
			max = max_t(u32, max, iter->phandle);
		if (max >= 0xfffffffe) {
			ret = -EINVAL;
		} else {
			*(__be32 *)prop->value = cpu_to_be32(max + 1);
			raw_spin_unlock_irqrestore(&devtree_lock, flags);
			ret = __of_add_property(np, prop);
			raw_spin_lock_irqsave(&devtree_lock, flags);
			if (!ret) {
				*handle = np->phandle = max + 1;
				added = true;
			}
		}
	}
	raw_spin_unlock_irqrestore(&devtree_lock, flags);
	mutex_unlock(&of_mutex);
	if (added) {
		of_property_notify(OF_RECONFIG_ADD_PROPERTY, np, prop, NULL);
		return 0; /* property permanently owned by live node */
	}
free:
	kfree(prop->value);
	kfree(prop->name);
	kfree(prop);
	return ret;
}
EXPORT_SYMBOL_GPL(of_m4rch_ensure_phandle);
