/* Print only active CRTC color properties and gamma samples, no image data. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <drm_mode.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
int main(void){int fd=open("/dev/dri/card1",O_RDONLY|O_CLOEXEC);if(fd<0){perror("open");return 1;}drmSetClientCap(fd,DRM_CLIENT_CAP_ATOMIC,1);drmModeRes *r=drmModeGetResources(fd);if(!r||r->count_crtcs!=1)return 1;drmModeObjectProperties *p=drmModeObjectGetProperties(fd,r->crtcs[0],DRM_MODE_OBJECT_CRTC);if(!p)return 1;for(uint32_t i=0;i<p->count_props;i++){drmModePropertyRes*q=drmModeGetProperty(fd,p->props[i]);if(!q)continue;if(!strcmp(q->name,"GAMMA_LUT")||!strcmp(q->name,"CTM"))printf("%s=%llu\n",q->name,(unsigned long long)p->prop_values[i]);if(!strcmp(q->name,"GAMMA_LUT")&&p->prop_values[i]){drmModePropertyBlobRes*b=drmModeGetPropertyBlob(fd,p->prop_values[i]);if(!b||b->length!=257*sizeof(struct drm_color_lut))return 1;struct drm_color_lut*l=b->data;for(int j=0;j<=256;j+=16)printf("%d %u %u %u\n",j,l[j].red,l[j].green,l[j].blue);drmModeFreePropertyBlob(b);}drmModeFreeProperty(q);}drmModeFreeObjectProperties(p);drmModeFreeResources(r);close(fd);return 0;}
