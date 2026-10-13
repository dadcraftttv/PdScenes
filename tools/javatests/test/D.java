package app.pdscenes;
public class D {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  public static void main(String[] a){
    ClipWatch w=new ClipWatch();
    check(!w.hasReports() && w.episodes(ClipWatch.IN)==0,"nothing before the first report");
    // one loud clap: 2 stretches once, no warning, one episode
    int s=w.onSecond(2,0,0);
    for(int i=0;i<10;i++) s|=w.onSecond(0,0,0);
    check(s==0 && !w.warning(ClipWatch.IN) && w.episodes(ClipWatch.IN)==1,"one clap: no warning, 1 episode");
    // keeps overloading: starts once, reports the start, holds while it goes on
    int st=w.onSecond(1,0,0); st|=w.onSecond(1,0,0); int third=w.onSecond(1,5,0);
    check(st==0 && third==(1<<ClipWatch.IN|1<<ClipWatch.GAIN) && w.warning(ClipWatch.IN),"steady overloads start the warning on the 3rd ("+third+")");
    check(w.onSecond(1,0,0)==0,"...and report its start only once");
    for(int i=0;i<4;i++) w.onSecond(0,0,0);
    check(w.warning(ClipWatch.IN),"still on 4 quiet seconds later");
    w.onSecond(0,0,0);
    check(!w.warning(ClipWatch.IN) && !w.warning(ClipWatch.GAIN),"off after 5 quiet seconds");
    check(w.episodes(ClipWatch.IN)==2 && w.episodes(ClipWatch.GAIN)==1 && w.episodes(ClipWatch.OUT)==0,"episodes in the minute: in "+w.episodes(0)+" gain "+w.episodes(1));
    for(int i=0;i<60;i++) w.onSecond(0,0,0);
    check(w.episodes(ClipWatch.IN)==0,"a minute later they are forgotten");
    w.reset();
    check(!w.hasReports(),"reset");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
