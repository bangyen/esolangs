/* trace PROGRAM NBITS [stride]: for each cell touched before a row's first
   output, count rows whose first touch executes it with A%256 in {48,49} (E7),
   executes it otherwise (E6), or reads it as data (D): "cell E6 E7 D". */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "tables.h"
#define W 59049
#define ROT 19683
#define EOFV 59048
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
static int init[W],mem[W],stamp[W]; static long e6[W],e7[W],dd[W];
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb"); int n=0,ch;
  while((ch=fgetc(f))!=EOF){ if(isspace(ch))continue; init[n++]=ch; }
  for(int i=n;i<W;i++) init[i]=crz(init[i-1],init[i-2]);
  int nb=atoi(argv[2]); long stride=argc>3?atol(argv[3]):1; long rows=1L<<nb;
  for(long r=0;r<rows;r+=stride){
    int tag=(int)(r/stride)+1;
    memcpy(mem,init,sizeof mem); int a=0,c=0,d=0,inp=0; long st=0;
    for(;;){
      if(stamp[c]!=tag){stamp[c]=tag; if((a&255)==48||(a&255)==49) e7[c]++; else e6[c]++;}
      int cell=mem[c]; if(cell<33||cell>126)break;
      char op=XLAT1[(cell-33+c)%94];
      if(op=='j'||op=='i'||op=='*'||op=='p'){ if(stamp[d]!=tag){stamp[d]=tag; dd[d]++;} }
      if(op=='j') d=mem[d];
      else if(op=='i') c=mem[d];
      else if(op=='*'){int v=mem[d]; a=mem[d]=v/3+(v%3)*ROT;}
      else if(op=='p'){a=mem[d]=crz(a,mem[d]);}
      else if(op=='<') break;
      else if(op=='/'){ if(inp<nb){a=48+((r>>(nb-1-inp))&1);inp++;} else a=EOFV; }
      else if(op=='v') break;
      int v=mem[c]; if(v>=33&&v<=126) mem[c]=XLAT2[v-33];
      c=(c+1)%W; d=(d+1)%W;
      if(++st>50000000) break;
    }
  }
  for(int i=0;i<W;i++) if(e6[i]||e7[i]||dd[i]) printf("%d %ld %ld %ld\n",i,e6[i],e7[i],dd[i]);
  return 0;
}
