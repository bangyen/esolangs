/* slack PROGRAM NBITS CELLFILE [full]: for each listed cell and each other
   character valid at its address, run 256 spread rows (and, with a fourth
   argument, then every row); print "cell char newop oldop" for survivors. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "tables.h"
#define W 59049
#define ROT 19683
#define EOFV 59048
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
static int src[W],init[W],mem[W]; static int nb;
static void fill(void){ memcpy(init,src,sizeof src); }
static int run(long r){ /* returns output byte, or -1 none, -2 multiple, -3 timeout */
  memcpy(mem,init,sizeof mem); int a=0,c=0,d=0,inp=0,out=-1; long st=0;
  for(;;){
    int cell=mem[c]; if(cell<33||cell>126)break;
    char op=XLAT1[(cell-33+c)%94];
    if(op=='j') d=mem[d];
    else if(op=='i') c=mem[d];
    else if(op=='*'){int v=mem[d]; a=mem[d]=v/3+(v%3)*ROT;}
    else if(op=='p'){a=mem[d]=crz(a,mem[d]);}
    else if(op=='<'){ if(out!=-1) return -2; out=a&255; }
    else if(op=='/'){ if(inp<nb){a=48+((r>>(nb-1-inp))&1);inp++;} else a=EOFV; }
    else if(op=='v') break;
    int v=mem[c]; if(v>=33&&v<=126) mem[c]=XLAT2[v-33];
    c=(c+1)%W; d=(d+1)%W;
    if(++st>2000000) return -3;
  }
  return out;
}
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb"); int n=0,ch;
  while((ch=fgetc(f))!=EOF){ if(isspace(ch))continue; src[n++]=ch; }
  if(n!=W){fprintf(stderr,"need full source\n");return 2;}
  nb=atoi(argv[2]); int full=argc>4; long rows=1L<<nb;
  fill(); signed char*base=malloc(rows); for(long r=0;r<rows;r++) base[r]=run(r);
  FILE*cf=fopen(argv[3],"r"); int cell;
  long stride=rows/256; if(stride<1)stride=1;
  while(fscanf(cf,"%d",&cell)==1){
    int orig=src[cell];
    for(int ch2=33;ch2<=126;ch2++){ if(ch2==orig)continue;
      char op=XLAT1[(ch2-33+cell)%94]; if(!strchr("ji*p</vo",op))continue;
      src[cell]=ch2; fill(); int ok=1;
      for(long r=(cell*7919L)%stride;r<rows&&ok;r+=stride) if(run(r)!=base[r]) ok=0;
      if(ok&&full) for(long r=0;r<rows&&ok;r++) if(run(r)!=base[r]) ok=0;
      if(ok){ printf("%d %d %c %c\n",cell,ch2,op,XLAT1[(orig-33+cell)%94]); fflush(stdout);}
    }
    src[cell]=orig;
  }
  return 0;
}
