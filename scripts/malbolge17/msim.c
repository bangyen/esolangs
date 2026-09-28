/* Fast Malbolge simulator matching esolangs.interpreters.other.malbolge.
   usage: msim PROGRAM NBITS [stride] [offset]
   Runs rows r = offset, offset+stride, ... < 2^NBITS; row r feeds bits MSB-first
   as lines "0"/"1"; prints one line per row: the output bytes (hex if not 0/1). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "tables.h"
#define W 59049
#define ROT 19683
#define EOFV 59048
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
int main(int argc,char**argv){
  if(argc<3){fprintf(stderr,"usage\n");return 2;}
  FILE*f=fopen(argv[1],"rb"); if(!f){perror("open");return 2;}
  static int init[W],mem[W]; int n=0,ch;
  while((ch=fgetc(f))!=EOF){ if(isspace(ch))continue; if(n>=W){fprintf(stderr,"too long\n");return 2;}
    if(ch<33||ch>126){fprintf(stderr,"bad char at %d\n",n);return 2;}
    char op=XLAT1[(ch-33+n)%94]; if(!strchr("ji*p</vo",op)){fprintf(stderr,"bad decode at %d\n",n);return 2;}
    init[n++]=ch; }
  fclose(f);
  if(n<2){fprintf(stderr,"short\n");return 2;}
  for(int i=n;i<W;i++) init[i]=crz(init[i-1],init[i-2]);
  int nb=atoi(argv[2]); long stride=argc>3?atol(argv[3]):1, off=argc>4?atol(argv[4]):0;
  long rows=1L<<nb; long maxsteps=50000000;
  for(long r=off;r<rows;r+=stride){
    memcpy(mem,init,sizeof mem); int a=0,c=0,d=0,inp=0; unsigned char out[16]; int no=0; long st=0;
    for(;;){
      int cell=mem[c]; if(cell<33||cell>126)break;
      char op=XLAT1[(cell-33+c)%94];
      if(op=='j') d=mem[d];
      else if(op=='i') c=mem[d];
      else if(op=='*'){int v=mem[d]; a=mem[d]=v/3+(v%3)*ROT;}
      else if(op=='p'){a=mem[d]=crz(a,mem[d]);}
      else if(op=='<'){ if(no<16) out[no]=a&0xFF; no++; }
      else if(op=='/'){ if(inp<nb){a=48+((r>>(nb-1-inp))&1);inp++;} else a=EOFV; }
      else if(op=='v') break;
      int v=mem[c]; if(v>=33&&v<=126) mem[c]=XLAT2[v-33];
      c=(c+1)%W; d=(d+1)%W;
      if(++st>maxsteps){no=-1;break;}
    }
    printf("%ld ",r);
    if(no<0) printf("TIMEOUT"); else for(int k=0;k<no&&k<16;k++){ if(out[k]=='0'||out[k]=='1') putchar(out[k]); else printf("\\x%02x",out[k]); }
    putchar('\n');
  }
  return 0;
}
