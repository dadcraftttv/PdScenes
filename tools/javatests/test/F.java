package app.pdscenes;
public class F {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  public static void main(String[] a){
    check(FirstRun.showWalkthrough(false,1000,1000),"a fresh install sees the walkthrough");
    check(!FirstRun.showWalkthrough(true,1000,1000),"...only once");
    check(!FirstRun.showWalkthrough(false,1000,5000),"a tester updating from an older version doesn't");
    check(Params.byId("wet").def==0f,"a new install's echo level is 0 (only the room plays)");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
