#include <assert.h>
#include "g16-model.h"
int main(void) {
 assert(agx_g16_select('G',1,10)==AGX_G16_G);
 assert(agx_g16_select('S',2,20)==AGX_G16_S);
 assert(agx_g16_select('S',1,10)==AGX_G16_UNKNOWN);
 assert(agx_g16_layout_qualified(AGX_G16_G));
 assert(!agx_g16_layout_qualified(AGX_G16_S));
 return 0;
}
