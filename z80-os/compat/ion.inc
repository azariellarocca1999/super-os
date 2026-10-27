; Super-OS flavoured ion.inc: source-level compatible Ion helpers (recompile Ion sources with it).
#include "compat/ti83plus_min.inc"
#define ionFastCopy bcall(_GrBufCpy)
#define ionRandom   bcall(_Random)
