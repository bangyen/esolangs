/* readers: for every residue h and every way of reading a three-cell group
   h, h+1, h+2 in consecutive steps (each cell by p, * or not at all), then
   printing, the max over all 59049 starting A of the admissible triples whose
   printed byte is 0 or 1.  Plain operands are below 243, so under p the top
   five trits evolve without them: only the reachable top halves matter.
   Build: gcc -O2 -o readers readers.c */
#include <stdio.h>
#include <string.h>
#include "tables.h"
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
static int rot(int v){return v/3+(v%3)*19683;}
int main(void){
  int I[8]; const char*ops="ji*p</vo"; for(int k=0;k<8;k++) I[k]=strchr(XLAT1,ops[k])-XLAT1;
  int overall=0;
  for(int pat=0;pat<27;pat++){ int o[3],t=pat; for(int k=0;k<3;k++){o[k]=t%3;t/=3;} /* 0=p 1=* 2=o */
    int last=-1,star=-1; for(int k=0;k<3;k++){ if(o[k]!=2) last=k; if(o[k]==1) star=k; }
    if(last<0||o[last]==1){ printf("pattern %c%c%c: 0 (ends on * of a plain char or reads nothing)\n","p*o"[o[0]],"p*o"[o[1]],"p*o"[o[2]]); continue; }
    int best=0;
    for(int h=0;h<94;h++){
      int adm[3][8]; for(int c=0;c<3;c++) for(int k=0;k<8;k++) adm[c][k]=33+((I[k]-h-c)%94+188)%94;
      if(star>=0){ int n=0;  /* A irrelevant */
        for(int a=0;a<512;a++){ int v[3]={adm[0][a&7],adm[1][(a>>3)&7],adm[2][a>>6]}, x=0;
          for(int k=0;k<3;k++){ if(o[k]==0) x=crz(x,v[k]); else if(o[k]==1) x=rot(v[k]); }
          int y=x&255; if(y==48||y==49) n++; }
        if(n>best) best=n; continue; }
      static int ylo[243][512]; int nread=0; for(int k=0;k<3;k++) if(o[k]==0) nread++;
      for(int lo=0;lo<243;lo++) for(int a=0;a<512;a++){ int v[3]={adm[0][a&7],adm[1][(a>>3)&7],adm[2][a>>6]}, x=lo;
        for(int k=0;k<3;k++) if(o[k]==0) x=crz(x,v[k]);
        ylo[lo][a]=x%243; }
      static int seen[243]; memset(seen,0,sizeof seen);
      for(int hi=0;hi<243;hi++){ int x=hi*243; for(int k=0;k<nread;k++) x=crz(x,0); seen[x/243]=1; }
      for(int H=0;H<243;H++) if(seen[H]) for(int lo=0;lo<243;lo++){ int n=0;
        for(int a=0;a<512;a++){ int y=(243*H+ylo[lo][a])&255; if(y==48||y==49) n++; }
        if(n>best) best=n; }
    }
    printf("pattern %c%c%c: max clean triples %d of 512\n","p*o"[o[0]],"p*o"[o[1]],"p*o"[o[2]],best); fflush(stdout);
    if(best>overall) overall=best;
  }
  printf("overall %d\n",overall);
}
