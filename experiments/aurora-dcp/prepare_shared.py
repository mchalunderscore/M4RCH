#!/usr/bin/env python3
"""Use J614s' shared DISP0/PMGR aperture once in its firmware register list."""
import argparse
import difflib
from pathlib import Path


def prepare(root,out):
    out.mkdir(parents=True,exist_ok=True)
    path=root/'drivers/gpu/drm/apple/dcp.c';before=path.read_text()
    anchor='\t/* load pmgr bandwidth scratch resource and offset */'
    new='''\t/* J614s' sixth ADT resource is already the bandwidth PMGR aperture.
\t * It is firmware display register 4, not a sixth register to append.
\t * Keep the physical resource in the DT and prove the alias exactly.
\t */
\tif (dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP &&
\t    j614s_display_board()) {
\t\tstruct resource *shared;

\t\tif (count != 5 ||
\t\t    of_property_present(dcp->dev->of_node, "apple,bw-doorbell"))
\t\t\treturn -EINVAL;
\t\tshared = dcp->disp_registers[4];
\t\tret = dcp_get_bw_scratch_reg(dcp, 4);
\t\tif (ret)
\t\t\treturn ret;
\t\tif (shared->start != dcp->disp_bw_scratch_res.start ||
\t\t    resource_size(shared) != resource_size(&dcp->disp_bw_scratch_res))
\t\t\treturn dev_err_probe(dcp->dev, -EINVAL,
\t\t\t\t"J614s shared DISP0 and bandwidth apertures differ\\n");
\t\tdcp->nr_disp_registers = count;
\t\tdev_info(dcp->dev, "J614s DISP0 register 4 supplies bandwidth scratch; five firmware registers\\n");
\t\treturn 0;
\t}

'''+anchor
    assert before.count(anchor)==1;after=before.replace(anchor,new)
    anchor='static int dcp_pin_live_session(struct apple_dcp *dcp)'
    helper='''static bool dcp_j614s_desktop_live(const struct apple_dcp *dcp)
{
\treturn dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP &&
\t       j614s_display_board() &&
\t       of_property_read_bool(dcp->dev->of_node, "apple,j614s-inherited-mappings");
}

static void dcp_j614s_adopt_hw(struct apple_dcp *dcp)
{
\tif (dcp_j614s_desktop_live(dcp))
\t\tdcp->hw.adopt_live_session = true;
}

'''
    assert after.count(anchor)==1;after=after.replace(anchor,helper+anchor)
    old='''\tif ((!dcp->hw.adopt_live_session &&
\t     dcp->hw.iomfb_method_profile !=
\t     DCP_IOMFB_METHODS_H17P_EXTERNAL) ||
\t    !dcp_fail_stop(dcp) ||
\t    dcp->hw.iomfb_method_profile == DCP_IOMFB_METHODS_H17G || dcp->retain_dma)
\t\treturn 0;'''
    new='''\tif (dcp->retain_dma)
\t\treturn 0;
\tif (!dcp_j614s_desktop_live(dcp) &&
\t    ((!dcp->hw.adopt_live_session &&
\t      dcp->hw.iomfb_method_profile != DCP_IOMFB_METHODS_H17P_EXTERNAL) ||
\t     !dcp_fail_stop(dcp) ||
\t     dcp->hw.iomfb_method_profile == DCP_IOMFB_METHODS_H17G))
\t\treturn 0;'''
    assert after.count(old)==1;after=after.replace(old,new)
    old='\tdcp->hw = *(struct apple_dcp_hw_data *)of_device_get_match_data(dev);'
    assert after.count(old)==1;after=after.replace(old,old+'\n\tdcp_j614s_adopt_hw(dcp);')
    old='\tif (offset > resource_size(&dcp->disp_bw_scratch_res) - 4) {'
    assert after.count(old)==1
    after=after.replace(old,'\tif (resource_size(&dcp->disp_bw_scratch_res) < 4 ||\n\t    offset > resource_size(&dcp->disp_bw_scratch_res) - 4) {')
    (out/'dcp.before.c').write_text(before);(out/'dcp.c').write_text(after)
    (out/'kernel-shared.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/drivers/gpu/drm/apple/dcp.c',tofile='b/drivers/gpu/drm/apple/dcp.c')))
    path.write_text(after)
    print('Prepared exact native shared-window alias; no index guard bypass or added firmware register')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();prepare(a.root,a.out)
