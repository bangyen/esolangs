/* fold SEED ITERS [a0..a7]: the stateless fold decoder.  Row r loads a
   constant with low trits a_r, reads its group's three cells by lockstep p,
   and lands in its own 243-cell window at the fold's low trits
   L_r = crz(crz(crz(a_r, v0), v1), v2) mod 243; the window cell prints
   b_r(L_r).  Prints the constants, the fewest distinct joint views over the
   94 residues, then anneals the windows b to cover every (residue, answer
   vector) pair: 94 * 256 = 24,064.  PAR=1 gives each parity its own windows.
   Build: gcc -O2 -o fold fold.c -lm */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "tables.h"
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
static int adm[94][3][8], L[8][94][512];
static unsigned char b[2][8][243]; static int par; static int cnt[94][256], vec[94][512], covered;
static unsigned rng=12345; static unsigned rnd(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
int main(int argc,char**argv){
  par=getenv("PAR")!=0; int seed=argc>1?atoi(argv[1]):1; long iters=argc>2?atol(argv[2]):20000000; rng=seed*2654435761u+1;
  int I[8]; const char*ops="ji*p</vo"; for(int k=0;k<8;k++) I[k]=strchr(XLAT1,ops[k])-XLAT1;
  for(int h=0;h<94;h++) for(int c=0;c<3;c++) for(int k=0;k<8;k++) adm[h][c][k]=33+((I[k]-h-c)%94+188)%94;
  int a[8];
  if(argc>3) for(int r=0;r<8;r++) a[r]=atoi(argv[3+r]); else for(int r=0;r<8;r++) a[r]=rnd()%243;
  for(int r=0;r<8;r++) for(int h=0;h<94;h++) for(int t=0;t<512;t++)
    L[r][h][t]=crz(crz(crz(a[r],adm[h][0][t&7]),adm[h][1][(t>>3)&7]),adm[h][2][t>>6])%243;
  /* upper bound: distinct joint tuples per residue */
  int ub=0, minj=512;
  for(int h=0;h<94;h++){ int d=0; for(int t=0;t<512;t++){ int dup=0; for(int u=0;u<t&&!dup;u++){ int s=1; for(int r=0;r<8&&s;r++) s=L[r][h][t]==L[r][h][u]; dup=s;} if(!dup)d++; }
    ub+= d<256?d:256; if(d<minj)minj=d; }
  printf("a:"); for(int r=0;r<8;r++) printf(" %d",a[r]); printf("  joint-distinct min %d, coverage ub %d/24064\n",minj,ub); fflush(stdout);
  for(int q=0;q<2;q++) for(int r=0;r<8;r++) for(int x=0;x<243;x++) b[q][r][x]=rnd()&1;
  covered=0; memset(cnt,0,sizeof cnt);
  for(int h=0;h<94;h++) for(int t=0;t<512;t++){ int v=0; for(int r=0;r<8;r++) v|=b[par?h&1:0][r][L[r][h][t]]<<r; vec[h][t]=v; if(cnt[h][v]++==0) covered++; }
  int best=covered; double T=2.0;
  /* index: for (r,x) the (h,t) list */
  static int *lst[2][8][243]; static int ln[2][8][243];
  for(int q=0;q<2;q++) for(int r=0;r<8;r++) for(int x=0;x<243;x++){ ln[q][r][x]=0; lst[q][r][x]=malloc(sizeof(int)*94*512); }
  for(int r=0;r<8;r++) for(int h=0;h<94;h++) for(int t=0;t<512;t++){ int x=L[r][h][t], q=par?h&1:0; lst[q][r][x][ln[q][r][x]++]=h*512+t; }
  for(long it=0;it<iters;it++){
    int q=par?rnd()%2:0, r=rnd()%8, x=rnd()%243; int delta=0;
    for(int i=0;i<ln[q][r][x];i++){ int ht=lst[q][r][x][i], h=ht>>9, t=ht&511; int v=vec[h][t], w=v^(1<<r);
      if(--cnt[h][v]==0) delta--; if(cnt[h][w]++==0) delta++; vec[h][t]=w; }
    if(delta>=0 || exp(delta/T) > (rnd()%1000000)/1e6){ covered+=delta; if(covered>best){best=covered;} }
    else { for(int i=0;i<ln[q][r][x];i++){ int ht=lst[q][r][x][i], h=ht>>9, t=ht&511; int w=vec[h][t], v=w^(1<<r);
      if(--cnt[h][w]==0) ; if(cnt[h][v]++==0) ; vec[h][t]=v; } }
    T*=0.9999997; if(T<0.02)T=0.02;
    if(it%2000000==0){ printf("  it %ld covered %d best %d T %.3f\n",it,covered,best,T); fflush(stdout);}
    if(covered==24064){ printf("FOUND\n"); break; }
  }
  printf("final covered %d best %d of 24064\n",covered,best);
}
