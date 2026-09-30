/* fold2s SEED ITERS [a0..a7]: the two-stage fold decoder.  Row r folds its
   group by p p p from constant a_r (words W0, W1, W2); its first window
   labels W2 mod 243 with 0, 1, A or B; A lands on W1 mod 243 and B on
   W0 mod 243, each in a 0/1 window.  Anneals all labels to cover the 24,064
   (residue, answer vector) pairs; best measured 21,427.
   Build: gcc -O2 -o fold2s fold2s.c -lm */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "tables.h"
static int crz(int x,int y){int r=0,p=1;for(int k=0;k<5;k++){r+=CRAZY[(y/p)%9][(x/p)%9]*p;p*=9;}return r;}
static int adm[94][3][8]; static unsigned char w2[8][94][512],w1[8][94][512],w0[8][94][512];
static unsigned char s1[8][243],sa[8][243],sb[8][243];
static int cnt[94][256], vec[94][512];
static unsigned rng; static unsigned rnd(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static int bit(int r,int h,int t){ int l=s1[r][w2[r][h][t]]; if(l<2) return l; if(l==2) return sa[r][w1[r][h][t]]; return sb[r][w0[r][h][t]]; }
int main(int argc,char**argv){
  rng=atoi(argv[1])*2654435761u+7; long iters=atol(argv[2]);
  int I[8]; const char*ops="ji*p</vo"; for(int k=0;k<8;k++) I[k]=strchr(XLAT1,ops[k])-XLAT1;
  for(int h=0;h<94;h++) for(int c=0;c<3;c++) for(int k=0;k<8;k++) adm[h][c][k]=33+((I[k]-h-c)%94+188)%94;
  int a[8]; for(int r=0;r<8;r++) a[r]=argc>3+r?atoi(argv[3+r]):rnd()%243;
  for(int r=0;r<8;r++) for(int h=0;h<94;h++) for(int t=0;t<512;t++){
    int x0=crz(a[r],adm[h][0][t&7]), x1=crz(x0,adm[h][1][(t>>3)&7]), x2=crz(x1,adm[h][2][t>>6]);
    w0[r][h][t]=x0%243; w1[r][h][t]=x1%243; w2[r][h][t]=x2%243; }
  for(int r=0;r<8;r++) for(int x=0;x<243;x++){ s1[r][x]=rnd()%4; sa[r][x]=rnd()&1; sb[r][x]=rnd()&1; }
  int cov=0; memset(cnt,0,sizeof cnt);
  for(int h=0;h<94;h++) for(int t=0;t<512;t++){ int v=0; for(int r=0;r<8;r++) v|=bit(r,h,t)<<r; vec[h][t]=v; if(cnt[h][v]++==0) cov++; }
  int best=cov; double T=1.5;
  for(long it=0;it<iters;it++){
    int r=rnd()%8, which=rnd()%3, x=rnd()%243; unsigned char*tab= which==0?s1[r]:which==1?sa[r]:sb[r];
    int old=tab[x], nv= which==0? rnd()%4 : old^1; if(nv==old) continue; tab[x]=nv;
    /* recompute affected: all (h,t) whose relevant index equals x -- brute force over rows' tables is costly; do full recompute on the row bit */
    int delta=0; static int chg[94*512]; int nc=0;
    unsigned char (*src)[512]= which==0? w2[r] : which==1? w1[r] : w0[r];
    for(int h=0;h<94;h++) for(int t=0;t<512;t++) if(src[h][t]==x){
      int v=vec[h][t], nb=bit(r,h,t), w=(v&~(1<<r))|(nb<<r); if(w==v) continue;
      if(--cnt[h][v]==0) delta--; if(cnt[h][w]++==0) delta++; vec[h][t]=w; chg[nc++]=h*512+t; }
    if(delta>=0 || exp(delta/T) > (rnd()%1000000)/1e6){ cov+=delta; if(cov>best)best=cov; }
    else { tab[x]=old; for(int i=0;i<nc;i++){ int h=chg[i]>>9,t=chg[i]&511; int w=vec[h][t], nb=bit(r,h,t), v=(w&~(1<<r))|(nb<<r);
      if(--cnt[h][w]==0); cnt[h][v]++; vec[h][t]=v; } }
    T*=0.9999996; if(T<0.02)T=0.02;
    if(cov==24064){ printf("FOUND at %ld\n",it); break; }
  }
  printf("a:"); for(int r=0;r<8;r++) printf(" %d",a[r]); printf("  best %d cov %d of 24064\n",best,cov);
}
